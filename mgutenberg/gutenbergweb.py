"""
Python interface to Project Gutenberg web catalog.

This may break at any time if they change page layout.

Routines
--------

- search(author, title, etextnr)

  Returns [(etext_id, authors, title, language, category), ...]

          authors = [(name, real_name, date, role), ...]

- etext_info(etext_id)

  Returns [(url, format, encoding, compression), ...]
"""
import urllib as _urllib, re as _re
import xml.etree.ElementTree as _xml

"""
python2.5 hack here:
"""
try:
	    import json as _json
except ImportError:
	    import simplejson as _json

from gettext import gettext as _

from util import *

readable_formats = [ 'Text', 'HTML', 'XML', 'ZIP', 'PalmOS Plucker', #'Single Book Page Text',
                     #'EPUB', 'Text PDF', 'DjVuTXT', 'Rich Text Format', 'TGZiped Text Files', #TODO add decoder
		     #'PDF', 'DjVu', 'Standard LuraTech PDF', # i want to belive
		     #'Word Document',
		     #'JPEG', 'TIFF', 'Single Page Processed TIFF ZIP', 'MARC', 'Image Container PDF',
		   ]

#------------------------------------------------------------------------------
# Interface routines
#------------------------------------------------------------------------------

class SearchFailure(RuntimeError): pass

def search(author=None, title=None, etextnr=None, subject=None, pageno=0):
    """
    Search for an etext in the Project Gutenberg catalog

    :Returns:
        [(etext_id, authors, title, language, category), ...]

        authors = [(name, real_name, date, role), ...]
    """

    q = []

    if title:
        q.append(('title:(' + title + ')'))
    if author:
        q.append(('creator:(' + author + ')'))
    if subject:
        q.append(('subject:(' + subject + ')'))
    #q.append(('collection:(' + 'gutenberg' + ')'))
    q.append(('format:(' + ' OR '.join(fmt for fmt in readable_formats) + ')'))
    query = ' AND '.join(cond for cond in q)

    data = _urllib.urlencode([('q', unicode(query))])

    info = [	'collection', 'identifier',
                'creator', 'title', 'language', 'subject',
		'format',
                'source']
    url = _SEARCH_URL + '?' + data + '&output=json&fl[]=' + '&fl[]='.join(x for x in info)
    url = url + '&mediatype=texts'
    url = url + '&rows=' + str(_SEARCH_RESULT_ROWS) + '&page=' + str(pageno+1)
    #url = url + '&indent=yes'
    
    output = _fetch_page(url)
    entries = _parse_archive_json(output)
    
    # NB. Gutenberg search sometimes return duplicate entries
    return unique(entries, key=lambda x: x[0])

def etext_info(identifier):
    """
    parse entry
    """
    info = []
	
    xml = _fetch_page(_DOWNLOAD_FILES % dict(id=identifier))
    files = _xml.fromstring(xml)
    for f in files:
		format = f.find('format').text
		name = f.get('name')

		if format != 'Metadata':
			url = _DOWNLOAD_FILE % dict(id=identifier, f=name)
			info.append(( url, format ))

    category = 'Text'

    return info, dict(category=category)
#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------


def _fetch_page(url):
    h = myurlopen(url)
    try:
        return h.read()
    finally:
        h.close()

def _parse_archive_json(json):
	"""
	Parse json reply into entries
	"""

	entries = []
	j = _json.loads(json)

	docs = j['response']['docs']
	for book in docs:
		"""
		check for missing fields
		"""
		for key in 'creator', 'language':
			try:
				book[key]
			except KeyError:
				book[key] = []

		for key in 'title', 'mediatype':
			try:
				book[key]
			except KeyError:
				book[key] = u''

		"""
		fill book entry
		"""
		authors = _parse_archive_authors(book['creator'])

		for fmt in readable_formats:
			if fmt in book['format']:
				entries.append((
						book['identifier'],
						authors,
						book['title'],
						','.join(x for x in book['language']),
						_(book['mediatype'])
						))
				continue

	return entries


def _parse_archive_authors(aut):
	authors = []

	for author in aut:
		name = real_name = date = u''
		role = u'author'

		t = author.split(',')
		if len(t)>0:
			name = t[0]
		if len(t)>1:
			name = name + ',' + t[1]
		if len(t)>2:
			date = t[2]
		if len(t)>3:
			real_name = t[3]
		if len(t)>4:
			role = t[4]

		authors.append((name, real_name, date, role))

	return authors

#------------------------------------------------------------------------------
# Urls
#------------------------------------------------------------------------------

_SEARCH_URL = "http://archive.org/advancedsearch.php"
_DOWNLOAD_URL_BASE = "http://archive.org/download"
_DOWNLOAD_FILE = _DOWNLOAD_URL_BASE+"/%(id)s/%(f)s"
_DOWNLOAD_FILES_SUFFIX = "_files.xml"
_DOWNLOAD_FILES = _DOWNLOAD_URL_BASE+"/%(id)s/%(id)s"+_DOWNLOAD_FILES_SUFFIX
_SEARCH_RESULT_ROWS = 256
