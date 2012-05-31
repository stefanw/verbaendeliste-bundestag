Bundestagslobby-Extraktor
=========================

Use `pdftohtml` to get an XML file from the pdf.

Then use the extractor with first and last relevant page number to convert to parsed JSON:

	python extract_lobby.py 4 690 < lobbylist.xml > lobbylist.json

Here is an extract file from the 31st of May 2012.

License: MIT-License
