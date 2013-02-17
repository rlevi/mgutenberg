"""
Bare-bones support for epub file format.

.. [DB] http://idpf.org/epub

"""

import array
import re
import os
import sys

import collections 
import zipfile
import xml.etree.ElementTree as ET

class EpubFile(object):
    def __init__(self, filename):
	self.zf = zipfile.ZipFile(filename, 'r')
	self.get_opf(self.zf)
	self.get_toc(self.zf, self.opfname)

    def get_opf(self, f):
        container = f.read("META-INF/container.xml")
	self.opfname = ET.fromstring(container)[0][0].attrib["full-path"]

    def get_toc(self, f, opfname):
        NS = '{http://www.idpf.org/2007/opf}'

	content = f.read(opfname)
	pkg = ET.fromstring(content)

	metadata = pkg.find(NS + 'metadata')
	manifest = pkg.find(NS + 'manifest')
	spine = pkg.find(NS + 'spine')

	href = dict()

	for child in manifest.findall(NS + 'item'):
	    if child.attrib['media-type'] == 'application/xhtml+xml':
	        href[child.attrib['id']] = child.attrib['href']

	self.toc = collections.OrderedDict()
	for child in spine.findall(NS + 'itemref'):
	    idref = child.attrib['idref']
	    if idref in href:
	        self.toc[idref] = href[idref]
	    #print idref, " -> ", self.toc[idref], " -> ",  href[idref]

	return self.toc

    def close(self):
	self.zf.close()

if __name__ == "__main__":
    f = EpubFile('test.epub')
    import time
    start = time.time()

    pref = os.path.dirname(f.opfname)
    for (_, href) in f.toc.items():
        print href
	print f.zf.read(pref+'/'+href)

    print time.time() - start
