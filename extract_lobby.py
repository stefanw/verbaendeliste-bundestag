# -*- coding: utf-8 -*-
import sys
import json
import re
from xml import sax
from StringIO import StringIO

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
    rec('M\.A\.(?:\([^\)]+\))?'),
)

ADDRESS_START = rec(u'\s\d+[a-z]?$|^\s*Geschäftsstelle:?\s*$')


class LobbyTextContentHandler(sax.ContentHandler):
    active = False
    intext = False
    bolded = False
    section = 'undefined'
    data = None
    index = 0
    board_kind = None
    text = ""

    class MARKER:
        # NAME_FIRST_ADDRESS = 'N a m e u n d S i t z , 1 . A d r e s s e'
        NAME_FIRST_ADDRESS = 'Name und Sitz, 1. Adresse'
        # OTHER = 'W e i t e r e'
        OTHER = 'Weitere Adresse'
        # BOARD = 'V o r s t a n d u n d '
        BOARD = u'Vorstand und Geschäftsführung'
        # INTERESTS = 'I n t e r e s s e n b e r e i c h'
        INTERESTS = 'Interessenbereich'
        # MEMBER_COUNT = 'M i t g l i e d e r z a h l'
        MEMBER_COUNT = 'Mitgliederzahl'
        # RELATED_ORGANIZATION_COUNT = 'A n z a h l d e r a n g e s c h l o s s e n e n O r g a n i s a t i o n'
        RELATED_ORGANIZATION_COUNT = 'Anzahl der angeschlossenen Organisationen'
        # REPRESENTATIVES = 'V e r b a n d s v e r t r e t e r'
        REPRESENTATIVES = 'Verbandsvertreter/-innen'
        # PARLIAMENT_ADDRESS = 'A n s c h r i f t a m S i t z v o n B T u n d B R'
        PARLIAMENT_ADDRESS = 'Anschrift am Sitz von BT und BRg'

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
        if attrs.get('font', '') == '35544':
            self.bolded = True
        else:
            self.bolded = False
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
            try:
                if not (self.section == 'parliamentaddress' or
                        self.section == 'undefined'):
                    raise ValueError
                temp_index = int(text)
            except ValueError:
                self.intext = False
                self.text = ""
                if self.is_next_section(text):
                    return
                stripped = text.strip()
                if stripped in ('-', u'\u2013',):
                    text = ''
            else:
                assert temp_index == self.index + 1, (self.index, temp_index)
                self.index = temp_index
                self.flush_data()
                self.data = {
                    'name': '',
                    'index': temp_index,
                    'locations': [],
                    'interestarea': [],
                    'board': [],
                    'membercount': None,
                    'organizationcount': None,
                    'representatives': []
                }
                self.text = ''
                self.section = 'undefined'
                return
        if not self.bolded and self.section == 'name':
            self.section = 'address'
        getattr(self, 'parse_' + self.section)(text)

    def is_next_section(self, text):
        if self.MARKER.NAME_FIRST_ADDRESS == text:
            self.section = 'name'
            return True
        if self.MARKER.BOARD == text:
            self.section = 'board'
            return True
        if self.MARKER.INTERESTS == text:
            self.section = 'interestarea'
            return True
        if self.MARKER.MEMBER_COUNT == text:
            self.section = 'membercount'
            return True
        if self.MARKER.RELATED_ORGANIZATION_COUNT == text:
            self.section = 'relatedorganizationscount'
            return True
        if self.MARKER.REPRESENTATIVES == text:
            self.section = 'representatives'
            return True
        if self.MARKER.PARLIAMENT_ADDRESS == text:
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
            if loc['address'] == u'\u00ad':
                loc['address'] = u''
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
        if self.data['name']:
            self.data['name'] += ' '
        self.data['name'] += text
        self.data['name'] = self.data['name'].strip()

    def parse_address(self, text):
        if not self.data['locations']:
            self.data['locations'] = [{'address': []}]
        if not text:
            return
        if not ADDRESS_START.search(text) and not self.data['locations'][0]['address']:
            # If line doesn't end in house number and
            # no address has been parsed yet, it's still part of the name
            return self.parse_name(text)

        if self.MARKER.OTHER in text:
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
        if 'email' in self.data['locations'][-1] and self.data['locations'][-1]['email'] in text:
            return
        if 'web' in self.data['locations'][-1] and self.data['locations'][-1]['web'] in text:
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
    parser.parse(StringIO(filein.read().replace('<A ', '<a ')))
    fileout.write(']')


if __name__ == '__main__':
    start = 4
    end = 688
    if len(sys.argv) > 1:
        start = int(sys.argv[1])
    if len(sys.argv) > 2:
        end = int(sys.argv[2])
    main(sys.stdin, sys.stdout, start, end)
