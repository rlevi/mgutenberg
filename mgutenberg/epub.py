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
        container = f.open("META-INF/container.xml", 'r')
	self.opfname = ET.parse(container).getroot()[0][0].attrib["full-path"]
	container.close()

    def get_toc(self, f, opfname):
        NS = '{http://www.idpf.org/2007/opf}'

	content = f.open(opfname, 'r')
	pkg = ET.parse(content).getroot()

	metadata = pkg.find(NS + 'metadata')
	manifest = pkg.find(NS + 'manifest')
	spine = pkg.find(NS + 'spine')

	href = dict()

	for child in manifest.findall(NS + 'item'):
	    href[child.attrib['id']] = child.attrib['href']

	self.toc = collections.OrderedDict()
	for child in spine.findall(NS + 'itemref'):
	    idref = child.attrib['idref']
	    self.toc[idref] = href[idref]
	    #print idref, " -> ", self.toc[idref], " -> ",  href[idref]

	content.close()

	return self.toc

    def close(self):
	self.zf.close()

if __name__ == "__main__":
    f = EpubFile('test.epub')
    import time
    start = time.time()

    for (_, href) in f.toc.items():
        print href
	ch = f.zf.open('OPS/'+href, 'r')
	for line in ch:
		print line
	ch.close()

    print time.time() - start
