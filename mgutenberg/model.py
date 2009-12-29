"""
Ebook data models

EbookList

    List of all Ebooks stored on the system

GutenbergSearchList

    Result of a Project Gutenberg search

DownloadInfo

    Information on a specific PG download

Config

    Configuration file backend

"""

import re, os, sys, shutil, tempfile
import xml.etree.ElementTree as ET
from xml.parsers.expat import ExpatError

import gtk
import gutenbergweb

from gettext import gettext as _
from guithread import *
from util import *

class OverwriteFileException(Exception): pass


def _is_caps_case(x):
    if len(x) < 1:
        return False
    elif len(x) == 1:
        return x[0] == x[0].upper()
    else:
        return x[0] == x[0].upper() and x[1] == x[1].lower()

def get_valid_basename(base):
    valid_ext = ['.txt',
                 '.html', '.htm',
                 '.fb2',
                 '.chm',
                 '.rtf',
                 '.oeb',
                 '.zip',
                 '.prc', '.pdb', '.mobi',
                 '.orb',
                 '.opf', '.oebzip',
                 '.tcr',
                 '.tgz', '.ipk',
                 ]
    skip_ext = ['.gz', '.bz2', '.tar']

    while True:
        base, ext = os.path.splitext(base)
        if ext in valid_ext:
            return base
        elif ext in skip_ext:
            pass
        else:
            return None

FILE_RES = [
    re.compile(r"^(?P<auth>[^-\[\]]+) - (?P<titl>[^\[\]]+) \[(?P<lang>.*)\]$"),
    re.compile(r"^(?P<auth>[^-]+) - (?P<titl>.+)$"),
    re.compile(r"^(?P<titl>[^\[\]]+) \[(?P<lang>.+)\]$"),
    re.compile(r"^(?P<titl>.+)$")
]

LANGUAGE_CODE_MAP = {
    'english': 'en',
    'german': 'de',
    'finnish': 'fi',
}

class EbookList(gtk.ListStore):
    """
    List of ebooks:

        [(author, title, language, file_name), ...]
    """
    
    def __init__(self, search_dirs):
        gtk.ListStore.__init__(self, str, str, str, str)
        self.search_dirs = search_dirs
    
    def add(self, author=u"", title=u"", language=u"", file_name=""):
        return self.append((author, title, language, file_name))

    def delete_file(self, it):
        entry = self[it]
        fn = entry[3]
        if os.path.isfile(entry[3]):
            os.unlink(entry[3])
        self.remove(it)

    def refresh(self, callback=None):
        self.clear()

        def walk_tree(files, d, author_name=""):
            if not os.path.isdir(d):
                return

            try:
                paths = os.listdir(d)
            except OSError:
                # permission error, etc.
                return
            
            for path in paths:
                full_path = os.path.join(d, path)
                if os.path.isdir(full_path):
                    # recurse into a directory
                    was_author = (',' in author_name)
                    if not author_name or not was_author:
                        walk_tree(files, full_path, path)
                    else:
                        walk_tree(files, full_path, author_name)
                else:
                    base = get_valid_basename(path)
                    if base is None:
                        continue # not a valid file
                    
                    # a file or something like that
                    entry = None
                    for reg in FILE_RES:
                        m = reg.match(base)
                        if m:
                            g = m.groupdict()
                            entry = (g.get('auth', author_name),
                                     g.get('titl', base),
                                     g.get('lang', ''),
                                     full_path)
                            break
                    if entry is None:
                        entry = (author_name, base, "", full_path)
                    files.append(entry)

        def really_add(r):
            for x in r:
                self.append(x)
            if callback:
                callback(True)
        
        def do_walk_tree(dirs):
            files = []
            for d in dirs:
                walk_tree(files, d)
            files.sort()
            run_in_gui_thread(really_add, files)

        start_thread(do_walk_tree, self.search_dirs)

NEXT_ID = -10

class GutenbergSearchList(gtk.ListStore):
    """
    List of search results:

        [(author, title, language, category, etext_id, author_other), ...]
    """

    def __init__(self):
        gtk.ListStore.__init__(self, str, str, str, str, int, str)
        self.pages = []
        self.pageno = 0
        self.last_search = None

    def add(self, author=u"", title=u"", language=u"",
            category=u"", etext_id=-1, author_other=u""):
        return self.append((author, title, language, category, etext_id,
                            author_other))

    def new_search(self, author="", title="", subject="", callback=None,
                   pre_callback=None):
        self.pages = []
        self.pageno = 0
        self.last_search = dict(author=author, title=title, subject=subject)

        def on_finish(r):
            if isinstance(r, Exception):
                callback(r)
                return
            if pre_callback:
                pre_callback()
            self._repopulate(r)
            if callback:
                callback(True)

        run_in_background(gutenbergweb.search,
                          author=author, title=title, subject=subject,
                          pageno=0, callback=on_finish)

    def next_page(self, callback=None, pre_callback=None):
        def on_finish(r):
            if isinstance(r, Exception):
                callback(r)
                return
            else:
                self.pageno += 1
            if pre_callback:
                pre_callback()
            self._repopulate(r)
            if callback:
                callback(True)

        run_in_background(gutenbergweb.search, pageno=self.pageno + 1,
                          callback=on_finish, **self.last_search)

    def _repopulate(self, result):
        self.clear()

        if result:
            if self.pageno >= len(self.pages):
                self.pages.extend([None] * (self.pageno+1-len(self.pages)))
            self.pages[self.pageno] = result

        for r in self.pages:
            if not r:
                continue
            for x in r:
                author, author_other = self._format_authors(x[1])
                if x[4].lower().strip() == 'audio book':
                    # XXX: Don't show audio books since we don't handle them
                    #      in a reasonable way yet...
                    continue
                self.add(author, self._format_title(x[2]), x[3], x[4], x[0],
                         ellipsize(author_other, max_length=320))

        if result:
            self.add(_('(More...)'), '', '', '', NEXT_ID, '')

    def _format_title(self, title):
        parts = title.split(u"\n")
        if parts[0].startswith(u"The "):
            parts[0] = parts[0][4:] + u", The"
        return ellipsize(u"\n".join(parts).strip(), max_length=80)

    def _format_authors(self, author_list):
        authors = []
        author_other = []
        for name, real_name, date, role in author_list:
            if role == 'author':
                authors.append(name)
                s = u""
            elif role == 'translator' and len(author_list) == 2:
                authors.append(u"tr. " + name)
                s = u""
            else:
                s = name
            if real_name:
                s += " (%s)" % real_name
            if date:
                s += " " + date
            if role and s:
                s += " [%s]" % role
            author_other.append(s.lstrip())
        return u"\n".join(authors), ellipsize(u"; ".join(author_other),
                                              max_length=160)

    def get_downloads(self, it, callback=None):
        author, title, language, category, etext_id, author_other = self[it]
        info = DownloadInfo(author, title, language, category, etext_id,
                            author_other)

        def on_finish(result):
            if isinstance(result, Exception):
                callback(result)
                return
                
            r, infodict = result
            info.category = infodict['category']
            for url, format, encoding, compression in r:
                msg = [x for x in format, encoding, compression if x]
                info.add(url, ', '.join(msg))
            if callback:
                callback(info)

        run_in_background(gutenbergweb.etext_info, etext_id,
                          callback=on_finish)
        
        return info

def ellipsize(text, max_length=80):
    pieces = text.split(" ")
    size = -1
    for k, piece in enumerate(pieces):
        if size + 1 + len(piece) + 4 > max_length:
            if size > 0:
                return u" ".join(pieces[:k]) + u" ..."
            else:
                return pieces[0][:125] + u"..."
        size += len(piece) + 1
    return u" ".join(pieces)

class DownloadInfo(gtk.ListStore):
    """
    Download choices

        [(url, format info)]
    """
    def __init__(self, author, title, language, category, etext_id,
                 author_other):
        self.author = author
        self.author_other = author_other
        self.title = title
        self.language = language
        self.category = category
        self.etext_id = etext_id

        gtk.ListStore.__init__(self, str, str)

    def add(self, url, format_info):
        return self.append((url, format_info))

    def download(self, it, base_directory, overwrite=False, callback=None):
        """
        :Parameters:
            it : gtk tree iterator
                Which item to download
            base_directory : str
                Directory under which to download
            overwrite : bool
                Allow overwriting existing files
            callback: callable(path)
                Function to call when download finished.
                ``path`` is the name of the new file, if the download was
                successful, and None if it download failed.
        """
        url, format = self[it]

        author = self.author.replace("\n", "; ")
        author = clean_filename(author)

        base_author = "; ".join([x for x in self.author.split("\n")
                                 if not x.startswith('tr. ')])
        base_author = clean_filename(base_author)

        url_base = url.split('/')[-1]
        try:
            ext = url_base.split('.', 1)[1]
        except IndexError:
            ext = ''

        if not ext and 'plucker' in format:
            ext = 'pdb'
            url_base += '.pdb'

        if self.author and self.title and self.language:
            base_name = u"%s - %s [%s]" % (author,
                                           self.title,
                                           self.language.lower())
        elif self.author and self.title:
            base_name = u"%s - %s" % (author, self.title)
        elif self.title:
            base_name = u"%s" % self.title
        else:
            base_name = u"Etext %d" % self.etext_id
        
        if ext:
            if get_valid_basename(url_base) is None:
                # Download audio files w/o renaming
                file_name = clean_filename(url_base)
            else:
                file_name = clean_filename("%s.%s" % (base_name, ext))
        else:
            file_name = clean_filename(base_name)

        if base_author:
            path = os.path.join(base_directory, base_author, file_name)
        else:
            path = os.path.join(base_directory, file_name)

        if os.path.isfile(path) and not overwrite:
            raise OverwriteFileException()
        
        dir_path = os.path.dirname(path)
        if not os.path.isdir(dir_path):
            os.makedirs(dir_path)

        def do_download(url):
            h, f = None, None
            try:
                h = myurlopen(url)
                f = open(path, 'w')
                shutil.copyfileobj(h, f)
            except IOError, e:
                # fetch failed; remove if exists and signal error
                if os.path.isfile(path):
                    os.remove(path)
                
                return e
            finally:
                if h is not None: h.close()
                if f is not None: f.close()
                
            return path
        
        def on_finish(path):
            if callback:
                callback(path)
        
        run_in_background(do_download, url, callback=on_finish)

def clean_filename(s):
    """
    Encode file name in filesystem charset and remove illegal characters
    """
    s = unicode(s).encode(sys.getfilesystemencoding(), 'replace')
    # cleanup for VFAT and others
    s = re.sub(r'[\x00-\x1f"\*\\/:<>?|]', '', s)
    return s

#------------------------------------------------------------------------------
# Configuration backend
#------------------------------------------------------------------------------

class Config(dict):
    """
    Very simple configuration file with basic-type XML object serialization
    """
    def __init__(self, schema):
        home = os.path.expanduser("~")
        self.file_name = os.path.join(home, '.mgutenbergrc')
        self.schema = schema

    def _toxml(self, o):
        if isinstance(o, list):
            el = ET.Element('list')
            for x in o:
                el.append(self._toxml(x))
            return el
        elif isinstance(o, dict):
            el = ET.Element('dict')
            for k, v in o.iteritems():
                e = self._toxml(v)
                e.attrib['key'] = str(k)
                el.append(e)
            return el
        elif isinstance(o, bool):
            return ET.Element('bool', dict(value=str(int(o))))
        elif isinstance(o, int):
            return ET.Element('int', dict(value=str(o)))
        elif isinstance(o, float):
            return ET.Element('float', dict(value=str(o)))
        elif isinstance(o, str) or isinstance(o, unicode):
            return ET.Element('str', dict(value=o))
        else:
            import warnings
            warnings.warn("Type of element %r not supported" % o)

    def _fromxml(self, el):
        valf = {'int': int, 'str': str, 'float': float,
                'bool': lambda x: bool(int(x))}

        if el.tag == 'list':
            o = []
            for sel in el:
                o.append(self._fromxml(sel))
            return o
        elif el.tag == 'dict':
            o = {}
            for sel in el:
                k = sel.get('key')
                if k is None: continue
                o[k] = self._fromxml(sel)
            return o
        elif el.tag in valf:
            try:
                return valf[el.tag](el.get('value'))
            except ValueError:
                return None
        else:
            return None

    def load(self):
        f = open(self.file_name, 'r')
        try:
            tree = ET.parse(f)
            d = self._fromxml(tree.getroot())
            self._coerce_schema(d)
            self.clear()
            self.update(d)
        except ExpatError:
            pass
        finally:
            f.close()

    def save(self):
        f = open(self.file_name, 'w')
        try:
            root = self._toxml(self)
            tree = ET.ElementTree(root)
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            tree.write(f, encoding='utf-8')
        finally:
            f.close()

    def _coerce_schema(self, d):
        """
        Coerce config to a schema:

            schema = {'key1': (list, str),
                      'key2': (dict, str), ...}

        drop non-valid keys.
        """

        class WalkError(RuntimeError): pass
        
        def walk(x, types):
            if not types:
                raise WalkError()
            
            t = types[0]
            
            if not isinstance(x, t):
                raise WalkError()
            
            if t == dict:
                for k, v in x.iteritems():
                    if not isinstance(k, str):
                        raise WalkError()
                    walk(v, types[1:])
            elif t == list:
                for y in x:
                    walk(y, types[1:])
            elif len(types) > 1:
                raise WalkError()
            else:
                pass # OK

        for k, v in self.iteritems():
            try:
                if k not in self.schema:
                    raise WalkError()

                types = self.schema[k]
                if not hasattr(types, '__iter__'):
                    types = (types,)

                walk(v, types)
            except WalkError:
                del d[k]
