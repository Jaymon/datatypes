# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.string import (
    String,
    ByteString,
    Base64,
    HTMLCleaner,
    HTMLParser,
    Character,
    Codepoint,
)

from . import TestCase, testdata


class Base64Test(TestCase):
    def test_encode_decode(self):
        s = testdata.get_words()

        b = Base64.encode(s)
        self.assertTrue(isinstance(b, unicode))
        self.assertNotEqual(b, s)

        s2 = Base64.decode(b)
        self.assertTrue(isinstance(s2, unicode))
        self.assertNotEqual(b, s2)
        self.assertEqual(s, s2)


class StringTest(TestCase):
    def test_xmlescape(self):
        s = String("<&")
        se = s.xmlescape()
        self.assertEqual("&lt;&amp;", se)

    def test_regex(self):
        s = String("foo bar foo")
        r = s.regex(r"foo").count()
        self.assertEqual(2, r)
        self.assertEqual(2, len(s.regex(r"foo")))
        self.assertEqual(1, len(s.regex(r"bar")))

    def test_string_int(self):
        i = testdata.get_int(0, 1000)
        s = String(i)
        self.assertEqual(str(i), String(i))

    def test_unicode_1(self):
        s = String(testdata.get_unicode())
        s2 = ByteString(s)
        s3 = String(s2)
        self.assertEqual(s, s3)

    def test_unicode_2(self):
        d = {"foo": testdata.get_unicode()}
        s2 = String(d)
        s3 = ByteString(s2)
        s4 = String(s3)
        self.assertEqual(s2, s4)

    def test_string(self):
        s = String(1)
        self.assertEqual("1", s)

        s = String(b"foo")
        self.assertEqual("foo", s)

        s = String({"foo": 1})
        self.assertEqual("{u'foo': 1}" if is_py2 else "{'foo': 1}", s)

        s = String((1, 2))
        self.assertEqual("(1, 2)", s)

        s = String([1, 2])
        self.assertEqual("[1, 2]", s)

        s = String(True)
        self.assertEqual("True", s)

        s = String(None)
        self.assertEqual("None", s)

        s = String("foo")
        self.assertEqual("foo", s)

        su = testdata.get_unicode()
        s = String(su)
        sb = bytes(s)
        s2 = String(sb)
        self.assertEqual(s, s2)

    def test_truncate(self):
        """tests that we can truncate a string on a word boundary"""
        s = String("foo bar bang bing")
        self.assertEqual("foo", s.truncate(5, ""))
        self.assertEqual("foo bar", s.truncate(10, ""))
        self.assertEqual("foo bar bang", s.truncate(15, ""))
        self.assertEqual("foo...", s.truncate(8))
        self.assertEqual("foo bar...", s.truncate(14))
        self.assertEqual("foop", s.truncate(5, "p"))
        self.assertEqual(s, s.truncate(len(s) + 100, "..."))

    def test_indent_simple(self):
        s = String("foo\nbar\nche")

        s2 = s.indent("  ")
        self.assertNotEqual(s, s2)
        for line in s2.splitlines():
            self.assertTrue(line.startswith("  "))

    def test_indent_issue37(self):
        #s = String("\nFOO\n").indent(1, "...")
        s = String("\nFOO\n").indent("...")
        self.assertEqual("...\n...FOO\n", s)

    def test_indent_count(self):
        s = String("foo")
        self.assertTrue(s.indent(".", 3).startswith("..."))
        self.assertFalse(s.indent(".", 2).startswith("..."))

    def test_wrap(self):
        s = String("foo bar che").wrap(5)
        self.assertEqual("foo\nbar\nche", s)

    def test_ispunc(self):
        s = String("{.}")
        self.assertTrue(s.ispunc())

        s = String(".A.")
        self.assertFalse(s.ispunc())

    def test_hash(self):
        h1 = String("4356").hash("YYYY-MM-DD")
        h2 = String("4356").hash("YYYY-MM-DD")
        h3 = String("4356").hash("YYYZ-MM-DD")
        h4 = String("4356").hash("YYYY-MM-DD", nonce="foobar")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h1, h4)
        self.assertNotEqual(h3, h4)

    def test_camelcase(self):
        s = String("foo_bar").camelcase()
        self.assertEqual("FooBar", s)

        s = String("foo BAR").camelcase()
        self.assertEqual("FooBar", s)

    def test_snakecase(self):
        s = String("FooBar").snakecase()
        self.assertEqual("foo_bar", s)


class ByteStringTest(TestCase):
    def test_conversion(self):
        s = testdata.get_unicode()
        bs = ByteString(s)
        bs2 = ByteString(bs)

        self.assertEqual(bs, bs2)
        self.assertEqual(s, bs.unicode())
        self.assertEqual(s, bs2.unicode())
        self.assertEqual(s, unicode(bs2))
        # self.assertNotEqual(s, bytes(bs2)) # this prints a UnicodeWarning

    def test_unicode(self):
        s = ByteString(testdata.get_unicode())
        s2 = String(s)
        s3 = ByteString(s2)
        self.assertEqual(s, s3)

    def test_int(self):
        s = ByteString(10)
        self.assertEqual(b'10', s)

    def test_bytestring(self):
        s = ByteString(1)
        self.assertEqual(b"1", s)

        s = ByteString("foo")
        self.assertEqual(b"foo", s)

        s = ByteString(True)
        self.assertEqual(b"True", s)

        with self.assertRaises(TypeError):
            s = ByteString(None)

        su = testdata.get_unicode()
        s = ByteString(su)
        self.assertEqual(su, s.unicode())


class HTMLCleanerTest(TestCase):
    def test_lifecycle(self):
        s = HTMLCleaner.strip_tags("foo<br />bar")
        self.assertEqual("foo\nbar", s)

        s = HTMLCleaner.strip_tags("&lt;:‑|<br />&gt;:)")
        self.assertEqual("<:‑|\n>:)", s)

    def test_images(self):
        html = 'foo <IMG src="bar.jpeg" /> che'
        s_keep = HTMLCleaner.strip_tags(html, keep_img_src=True)
        s = HTMLCleaner.strip_tags(html, keep_img_src=False)
        self.assertNotEqual(s, s_keep)

    def test_whitespace(self):
        html = 'Sideways <a href="/wiki/Latin_1" class="mw-redirect" title="Latin 1">Latin</a>-only emoticons'
        s = HTMLCleaner.strip_tags(html)
        self.assertEqual("Sideways Latin-only emoticons", s)

    def test_unescape(self):
        s = "&lt;:‑|&gt;:)"

        s = HTMLCleaner.unescape(s)
        self.assertEqual("<:‑|>:)", s)

        s = HTMLCleaner.unescape(s)
        self.assertEqual("<:‑|>:)", s)


class HTMLParserTest(TestCase):
    def test_no_end_tag(self):
        html = '<div><h1 class="foo">h1 full</h1><p>this is somethign <b>bold</b> and stuff</p>'
        #html = '<body>body data before <h1 class="foo">h1 data</h1> body data after</body>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual("div", t.next()["tagname"])

    def test_tagnames(self):
        html = "\n".join([
            '<div>',
            '<p>one</p>'
            '<p>two with <a href="#">link</a></p>'
            '<p>three with <img src="foobar.jpg" /></p>'
            '<p>four with <img src="foobar.jpg" /> and <a href="#2">link</a></p>'
            '<p>five</p>'
            '</div>',
        ])
        t = HTMLParser(html, "p")
        self.assertEqual(5, len(t))
        self.assertEqual(2, len(t.tags[1]["body"]))
        self.assertEqual(2, len(t.tags[2]["body"]))
        self.assertEqual(4, len(t.tags[3]["body"]))
        self.assertEqual(1, len(t.tags[4]["body"]))

    def test_notagnames(self):
        html = '<div><h1 class="foo">h1 full</h1><p>this is something <b>bold</b> and stuff</p></div>'
        #html = '<body>body data before <h1 class="foo">h1 data</h1> body data after</body>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual(2, len(t.tags[0]["body"]))

    def test_empty_tags(self):
        html = '<div><span><img src=""><p>p data</p><br></span></div>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual(1, len(t.tags[0]["body"]))
        self.assertEqual(3, len(t.tags[0]["body"][0]["body"]))


class CharacterTest(TestCase):
    """
    NOTE: some tests will fail with narrow unicode: `sys.maxunicode == 65535`
    """
    def test_repr(self):
        # http://www.fileformat.info/info/unicode/char/267cc/index.htm
        ch = Character("\uD859\uDFCC")
        self.assertEqual("\\xf0\\xa6\\x9f\\x8c", ch.repr_bytes())
        self.assertEqual("\\uD859\\uDFCC", ch.repr_string())

    def test_width(self):
        ch = Character("\uD859\uDFCC")
        self.assertEqual(2, ch.width())

        ch = Character("\uD83D\uDC68\uFE0F")
        self.assertEqual(2, ch.width())

        # wide characters:
        # https://www.reddit.com/r/Unicode/comments/5qa7e7/widestlongest_unicode_characters_list/ 

        # it feels like this one should be 2 characters wide
        # https://unicode-table.com/en/102A/
        # https://www.fileformat.info/info/unicode/char/102a/index.htm
        ch = Character("\u102A")
        self.assertEqual(1, ch.width())

        # it feels like this one should be 3 characters wide
        ch = Character("\uFDFD")
        self.assertEqual(1, ch.width())

    def test_is_complete(self):
        # https://www.fileformat.info/info/unicode/char/fffd/index.htm
        ch = Character("\uFFFD")
        self.assertTrue(ch.is_complete())

        ch = Character("\uDFCC")
        self.assertFalse(ch.is_complete())

        ch = Character("\U0001F642")
        self.assertTrue(ch.is_complete())

        # d859 and dfcc are surrogates
        ch = Character("\uD859\uDFCC")
        self.assertFalse(ch.is_complete())

        ch = Character("\U0001F441\u200D\U0001F5E8")
        self.assertFalse(ch.is_complete())

        ch = Character("\u102A")
        self.assertTrue(ch.is_complete())

    def test_integers(self):
        s = "\U0001F441\u200D\U0001F5E8"
        u = Character(s)
        self.assertEqual([128065, 8205, 128488], u.integers())

        u = Character([128065, 8205, 128488])
        self.assertEqual([128065, 8205, 128488], u.integers())

    def test_create(self):
        s = "\U0001F441\u200D\U0001F5E8"
        codepoints = ["1F441", "200D", "1F5E8"]

        u = Character(s)
        self.assertEqual(s, u)
        self.assertEqual(codepoints, u.hexes)

        u = Character(codepoints)
        self.assertEqual(s, u)
        self.assertEqual(codepoints, u.hexes)

        codepoints = "1F468 1F3FB 200D 1F9B0"
        u = Character(codepoints)
        self.assertEqual(codepoints.split(" "), u.hexes)

        codepoints = "1F468"
        u = Character(codepoints)
        self.assertEqual([codepoints], u.hexes)

        codepoints = "1F468-1F3FB-200D-1F9B0"
        u = Character(codepoints)
        self.assertEqual(codepoints.split("-"), u.hexes)

    def test_names_1(self):
        codepoints = ["200D"]
        u = Character(codepoints)
        self.assertEqual("ZERO WIDTH JOINER", u.names()[0])

    def test_lowercase(self):
        codepoints = '1f44f-1f3ff'
        u = Character(codepoints)
        self.assertEqual(['1F44F', '1F3FF'], u.hexes)

        codepoints = "1F468-1F3FB-200D-1F9B0"
        u = Character(codepoints)
        self.assertEqual(["1F468", "1F3FB", "200D", "1F9B0"], u.hexes)

    def test_html_chars(self):
        u = Character(b'\xf0\x9f\xa4\xa6&zwj;\xe2\x99\x80\xef\xb8\x8f')
        self.assertEqual(["1F926", "200D", "2640", "FE0F"], u.hexes)


class CodepointTest(TestCase):
    def test_character(self):
        c = Codepoint("\U0001F441")
        self.assertEqual("1F441", c.hex)
        self.assertEqual("\U0001F441", c)

        c = Codepoint("\u200D")
        self.assertEqual("200D", c.hex)
        self.assertEqual("\u200D", c)

    def test_int(self):
        c = Codepoint("\U0001F441")
        self.assertEqual(128065, int(c))

        c = Codepoint("\u200D")
        self.assertEqual(8205, int(c))

    def test_create(self):
        c = Codepoint(128065)
        self.assertEqual("1F441", c.hex)

        c = Codepoint(0x1F441)
        self.assertEqual("1F441", c.hex)

        c = Codepoint(b"1F441")
        self.assertEqual("1F441", c.hex)

        c = Codepoint("&zwj;")
        self.assertEqual("200D", c.hex)

        c = Codepoint("U+1F468")
        self.assertEqual("1F468", c.hex)

        c = Codepoint("u+200D")
        self.assertEqual("200D", c.hex)

        c = Codepoint("\u200D")
        self.assertEqual("200D", c.hex)

