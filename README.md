Verbaendeliste-Bundestag Extractor
==================================

Use `pdftohtml` to get an XML file from the pdf.

    pdftohtml -xml input.pdf output.xml

Then use the extractor with first and last relevant page number to convert to parsed JSON:

	python extract_lobby.py 4 690 < lobbylist.xml > lobbylist.json

Here is [extracted JSON (15th of June 2012)](http://stefanwehrmeyer.com/projects/verbaendeliste/20120615.json).

License: MIT-License
