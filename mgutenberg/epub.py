"""
Bare-bones support for epub file format.

.. [DB] http://idpf.org/epub

"""

import array
import re
import os
import sys

import zipfile
import xml.etree.ElementTree as ET

class EpubFile(object):
    epub_ns = '{http://www.idpf.org/2007/opf}'

    def __init__(self, filename):
	self.zf = zipfile.ZipFile(filename, 'r')
	self.get_opf(self.zf)
	self.get_toc(self.zf, self.opfname)

    def get_opf(self, f):
        container = f.open("META-INF/container.xml", 'r')
	self.opfname = ET.parse(container).getroot()[0][0].attrib["full-path"]
	container.close()

    def get_toc(self, f, opfname):
	content = f.open(opfname, 'r')
	pkg = ET.parse(content).getroot()

	metadata = pkg.find(self.epub_ns + 'metadata')
	manifest = pkg.find(self.epub_ns + 'manifest')
	spine = pkg.find(self.epub_ns + 'spine')

	href = dict()

	for child in manifest.findall(self.epub_ns + 'item'):
	    href[child.attrib['id']] = child.attrib['href']

	self.toc = dict()
	for child in spine.findall(self.epub_ns + 'itemref'):
	    idref = child.attrib['idref']
	    self.toc[idref] = href[idref]

	content.close()

	return self.toc

    def close(self):
	self.zf.close()

if __name__ == "__main__":
    f = EpubFile('test.epub')
    import time
    start = time.time()
    print time.time() - start
