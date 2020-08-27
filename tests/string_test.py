# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.string import (
    String,
    ByteString,
    Base64,
    HTMLCleaner,
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

    def test_indent(self):
        s = String("foo\nbar\nche")

        s2 = s.indent("  ")
        self.assertNotEqual(s, s2)
        for line in s2.splitlines():
            self.assertTrue(line.startswith("  "))

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


class ByteStringTest(TestCase):
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

