# -*- coding: utf-8 -*-
import sys
import json
import re
from xml import sax

rec = lambda x: re.compile(x, re.UNICODE)

TITLES = (
    rec(u'Dipl?\.\-?[\w\.-]+(?:\s?\(FH\))?'),
    rec('[a-z]+\.habil\.'),
    rec('(?:Prof\.)?(?:\s?Dr\.(?:\s?h\.c\.)?(?:\s?[a-z]+\.)?)*(?:-Ing\.)?(?:\s?med\.)?'),
    rec('(?:Chef)?[Aa]potheker(?:in)?'),
    rec('Weihbischof'),  # ORLY
    rec('(?:Minister )?a.D.'),
    rec(u'(?:Ober)?[Bb]ürgermeister(?:in)?'),
    rec('Steuerberater(?:in)?/?'),
    rec(u'Fachanw[aä]lt(?:in)? für [\w\.-]+'),
    rec(u'Wirtschaftsprüfer(?:in)?'),
    rec(u'vereidigter? Buchprüfer(?:in)?'),
    rec('RA(?:in)?/?'),
    rec('^Obermeister(?:in)?'),
)


class LobbyTextContentHandler(sax.ContentHandler):
    active = False
    intext = False
    bolded = False
    section = 'undefined'
    data = None
    index = 0
    board_kind = None
    text = ""

    def __init__(self, fileout, start=0, end=0):
        self.page_start = start
        self.page_end = end
        self.fileout = fileout

    def startElement(self, name, attrs):
        if name == "page":
            if int(attrs['number']) == self.page_start:
                self.active = True
            if int(attrs['number']) == self.page_end:
                self.active = False
            return
        if name == "text" and int(attrs['top']) > 30 and int(attrs['top']) < 1200:
            self.intext = True
        if name == "b":
            self.bolded = True
        if not self.intext or not self.active:
            return
        if name == "a":
            href = attrs.get('href', '')
            if href.startswith('mailto:'):
                self.data['locations'][-1]['email'] = href[len('mailto:'):]
            if href.startswith('http'):
                self.data['locations'][-1]['web'] = href

    def endElement(self, name):
        if not self.active:
            return
        if not self.intext:
            return
        text = self.text
        if name == "text":
            self.intext = False
            self.text = ""
            if self.is_next_section(text):
                return
            stripped = text.strip()
            if stripped in ('-', u'\u2013',):
                text = ''
        getattr(self, 'parse_' + self.section)(text)
        if name == "b":
            self.bolded = False
            try:
                temp_index = int(text)
            except ValueError:
                pass
            else:
                assert temp_index == self.index + 1
                self.index = temp_index
                self.flush_data()
                self.data = {
                    'index': temp_index,
                    'locations': [],
                    'interestarea': [],
                    'board': [],
                    'membercount': None,
                    'organizationcount': None,
                    'representatives': []
                }
                self.section = 'name'
                return

    def is_next_section(self, text):
        if 'V o r s t a n d u n d ' in text:
            self.section = 'board'
            return True
        if 'I n t e r e s s e n b e r e i c h' in text:
            self.section = 'interestarea'
            return True
        if 'M i t g l i e d e r z a h l' in text:
            self.section = 'membercount'
            return True
        if 'A n z a h l d e r a n g e s c h l o s s e n e n O r g a n i s a t i o n' in text:
            self.section = 'relatedorganizationscount'
            return True
        if 'V e r b a n d s v e r t r e t e r' in text:
            self.section = 'representatives'
            return True
        if 'A n s c h r i f t a m S i t z v o n B T u n d B R' in text:
            self.section = 'parliamentaddress'
            return True
        return False

    def characters(self, text):
        if self.active and self.intext and text.strip():
            self.text += text

    def endDocument(self):
        self.flush_data(True)

    def flush_data(self, last=False):
        if self.data is None:
            return
        self.data['interestarea'] = '\n'.join(self.data['interestarea']).strip()
        newlocs = []
        for loc in self.data['locations']:
            loc['address'] = '\n'.join(loc['address']).strip()
            if not loc['address'] and len(loc.keys()) <= 2:
                continue
            newlocs.append(loc)
        self.data['locations'] = newlocs

        self.fileout.write(json.dumps(self.data, sort_keys=True, indent=4))
        if not last:
            self.fileout.write(',')

    def parse_undefined(self, text):
        pass

    def parse_name(self, text):
        if self.bolded:
            self.data['name'] = text
            self.section = 'address'

    def parse_address(self, text):
        if not self.data['locations']:
            self.data['locations'] = [{'address': []}]
        if not text:
            return
        if 'W e i t e r e' in text:
            self.data['locations'].append({'address': []})
            return
        if text == 'E-Mail:' or text == 'Internet:':
            return
        if 'Tel.:' in text:
            parts = text.split('Fax:')
            self.data['locations'][-1]['phone'] = parts[0][len('Tel.:'):].strip()
            if len(parts) > 1:
                self.data['locations'][-1]['fax'] = parts[1].strip()
            return
        if 'email' in self.data['locations'][-1] and text == self.data['locations'][-1]['email']:
            return
        if 'web' in self.data['locations'][-1] and text == self.data['locations'][-1]['web']:
            return
        self.data['locations'][-1]['address'].append(text)

    def get_titles(self, name):
        titles = []
        new_name = name
        for title in TITLES:
            matches = title.findall(new_name)
            for match in matches:
                if not match.strip():
                    continue
                try:
                    index = name.index(match)
                except ValueError:
                    print name
                    print match
                    print new_name
                    raise
                new_name = new_name.replace(match, '', 1)
                titles.append((index, match.strip()))
        if titles:
            titles.sort(key=lambda x: x[0])
            titles = ' '.join([x[1] for x in titles])
            titles = titles.replace('/ ', '/')
        else:
            titles = None
        new_name = new_name.strip()
        if not new_name:
            new_name = name.strip()
        return titles, new_name

    def parse_board(self, text):
        if not self.data['board']:
            self.data['board'] = []
        if text.endswith(':'):
            self.board_kind = text[:-1].strip()
            return
        parts = text.rsplit(',', 1)
        if len(parts) > 1:
            titles, name = self.get_titles(parts[0].strip())
            self.data['board'].append((titles, name, parts[1].strip()))
        else:
            titles, name = self.get_titles(text.strip())
            if self.board_kind is not None:
                self.data['board'].append((titles, name, self.board_kind))
            else:
                self.data['board'].append((titles, name, None))

    def parse_interestarea(self, text):
        self.board_kind = None
        if (self.data['interestarea'] and self.data['interestarea'][-1] and
                self.data['interestarea'][-1][-1] == '-'):
            self.data['interestarea'][-1] = self.data['interestarea'][-1][:-1] + text
        else:
            self.data['interestarea'].append(text)

    def parse_membercount(self, text):
        text = text.replace('.', '')
        try:
            self.data['membercount'] = int(text)
        except ValueError:
            self.data['membercount'] = None

    def parse_relatedorganizationscount(self, text):
        text = text.replace('.', '')
        try:
            self.data['organizationcount'] = int(text)
        except ValueError:
            self.data['organizationcount'] = None

    def parse_representatives(self, text):
        if 'Name und Sitz, 1. Adresse' in text:
            self.data['representatives'].append('@address')
            return
        if 'Vorstand und Gesch' in text:
            self.data['representatives'].append('@board')
            return
        if not text:
            return
        title, name = self.get_titles(text.strip())
        self.data['representatives'].append((title, name))

    def parse_parliamentaddress(self, text):
        if self.bolded:
            return
        if not 'parliament' in self.data['locations'][-1]:
            self.data['locations'].append({'address': [], 'parliament': True})
        if 'Name und Sitz, 1. Adresse' in text:
            self.data['locations'][-1]['address'].append('@address')
            return
        if 'Vorstand und Gesch' in text:
            self.data['locations'][-1]['address'].append('@board')
            return
        self.parse_address(text)


def main(filein, fileout, start, end):
    fileout.write('[')
    parser = sax.make_parser()
    handler = LobbyTextContentHandler(fileout, start=start, end=end)
    parser.setFeature(sax.handler.feature_external_ges, False)
    parser.setContentHandler(handler)
    parser.parse(filein)
    fileout.write(']')


if __name__ == '__main__':
    start = 4
    end = 688
    if len(sys.argv) > 1:
        start = int(sys.argv[1])
    if len(sys.argv) > 2:
        end = int(sys.argv[2])
    main(sys.stdin, sys.stdout, start, end)
