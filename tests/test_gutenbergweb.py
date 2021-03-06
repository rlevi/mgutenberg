import mgutenberg.gutenbergweb as gutenbergweb

def test_search_author():
    r = gutenbergweb.search(author='Nietzsche')
    assert len(r) >= 4, r
    assert any(eid == 19634 for eid,au,tt,lng,c in r), r
    assert all(isinstance(eid, int) and isinstance(au, unicode)
               and isinstance(tt, unicode) and isinstance(lng, unicode)
               for eid,au,tt,lng,c in r), r
    assert all(u'Nietzsche, Friedrich Wilhelm' in au for eid,au,tt,lng,c in r), r
    assert any(u"Thus Spake Zarathustra" in tt for eid,au,tt,lng,c in r), r
    assert any(u"English" == lng for eid,au,tt,lng,c in r), r
    assert any(u"German" == lng for eid,au,tt,lng,c in r), r

def test_search_title():
    r = gutenbergweb.search(title="Beyond Good and Evil")
    assert all(u'Nietzsche, Friedrich Wilhelm' in au for eid,au,tt,lng,c in r), r
    assert all(u"English" == lng for eid,au,tt,lng,c in r), r

def test_search_pageno():
    r = gutenbergweb.search(title="ring")
    assert len(r) >= 50
    r = gutenbergweb.search(title="ring", pageno=200)
    assert r == []

def test_search_etextnr():
    r = gutenbergweb.search(etextnr=1234)
    assert len(r) == 1
    eid, au, tt, lng, c = r[0]
    assert eid == 1234, r
    assert au == u"Conant, James Bryant, 1893-1978 [Editor]", r
    assert tt == u"Organic Syntheses", r
    assert lng == u"English", r

def test_info():
    r, infodict = gutenbergweb.etext_info(19634)
    assert len(r) >= 4, r
    assert any('19634' in url for url,fmt,enc,comp in r), r
    assert any(fmt == 'plain text' for url,fmt,enc,comp in r), r
    assert any(enc == 'us-ascii' for url,fmt,enc,comp in r), r
    assert any(comp == '' for url,fmt,enc,comp in r), r
    assert 'audio book' in infodict['category'].lower()

def test_authors():
    text = u"Cobb, Irvin S. (Irvin Shrewsbury), Sir, 1976- [Author]\nSarg, Tony, 1880-1942 [Illustrator]"
    authors = gutenbergweb._parse_gutenberg_authors(text)
    assert authors == [(u'Cobb, Irvin S.', u'Irvin Shrewsbury, Sir',
                        u'1976-', u'author'),
                       (u'Sarg, Tony', '', u'1880-1942', u'illustrator')], \
                       authors

    text = u"Cobb, Irvin S., -1944 [Author]\nSarg, Tony [Illustrator]"
    authors = gutenbergweb._parse_gutenberg_authors(text)
    assert authors == [(u'Cobb, Irvin S.', u'', u'-1944', u'author'),
                       (u'Sarg, Tony', '', u'', u'illustrator')], \
                       authors
