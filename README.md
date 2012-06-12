Verbaendeliste-Bundestag Extractor
==================================

Use `pdftohtml` to get an XML file from the pdf.

Then use the extractor with first and last relevant page number to convert to parsed JSON:

	python extract_lobby.py 4 690 < lobbylist.xml > lobbylist.json

Here is [extracted JSON (5th of June 2012)](http://stefanwehrmeyer.com/projects/verbaendeliste/20120605.json).

License: MIT-License
