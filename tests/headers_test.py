# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.headers import Headers, Environ
from datatypes.string import String, ByteString

from . import TestCase, testdata


class EnvironTest(TestCase):
    def test_values(self):
        d = Environ()

        d["foo"] = None
        self.assertEqual(None, d["foo"])

        d["bar"] = 1
        self.assertEqual(1, d["bar"])


class HeadersTest(TestCase):
    def test_midbody_capital_letter(self):
        """Previously, before June 2019, our headers didn't handle WebSocket correctly
        instead lowercasing the S to Websocket"""
        d = Headers()
        d["Sec-WebSocket-Key"] = "foobar"
        self.assertTrue("Sec-Websocket-Key" in d)
        d2 = dict(d)
        self.assertFalse("Sec-Websocket-Key" in d2)
        self.assertTrue("Sec-WebSocket-Key" in d2)

    def test_bytes(self):
        d = Headers()
        name = testdata.get_unicode()
        val = ByteString(testdata.get_unicode())
        d[name] = val
        self.assertEqual(d[name], String(val))

    def test_different_original_keys(self):
        """when setting headers using 2 different original keys it wouldn't be uniqued"""
        d = Headers()
        d['Content-Type'] = "application/json"
        d['content-type'] = "text/plain"
        self.assertEqual(1, len(d))
        self.assertEqual("text/plain", d["CONTENT-TYPE"])

    def test_lifecycle(self):
        d = Headers()
        d["foo-bar"] = 1
        self.assertEqual("1", d["Foo-Bar"])
        self.assertEqual("1", d["fOO-bAr"])
        self.assertEqual("1", d["fOO_bAr"])

    def test_pop(self):
        d = Headers()
        d['FOO'] = 1
        r = d.pop('foo')
        self.assertEqual("1", r)

        with self.assertRaises(KeyError):
            d.pop('foo')

        with self.assertRaises(KeyError):
            d.pop('FOO')

    def test_normalization(self):

        keys = [
            "Content-Type",
            "content-type",
            "content_type",
            "CONTENT_TYPE"
        ]

        v = "foo"
        d = {
            "CONTENT_TYPE": v,
            "CONTENT_LENGTH": 1234
        }
        headers = Headers(d)

        for k in keys:
            self.assertEqual(v, headers["Content-Type"])

        headers = Headers()
        headers["CONTENT_TYPE"] = v

        for k in keys:
            self.assertEqual(v, headers["Content-Type"])

        #with self.assertRaises(KeyError):
        #    headers["foo-bar"]

        for k in keys:
            self.assertTrue(k in headers)

    def test_iteration(self):
        hs = Headers()
        hs['CONTENT_TYPE'] = "application/json"
        hs['CONTENT-LENGTH'] = "1234"
        hs['FOO-bAR'] = "che"
        for k in hs.keys():
            self.assertRegex(k, r"^[A-Z][a-z]+(?:\-[A-Z][a-z]+)*$")
            self.assertTrue(k in hs)

        for k, v in hs.items():
            self.assertRegex(k, r"^[A-Z][a-z]+(?:\-[A-Z][a-z]+)*$")
            self.assertEqual(hs[k], v)

        for k in hs:
            self.assertRegex(k, r"^[A-Z][a-z]+(?:\-[A-Z][a-z]+)*$")
            self.assertTrue(k in hs)

    def test___init__(self):
        d = {"foo-bar": "1"}
        hs = Headers(d)
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual(1, len(hs))

        d = [("foo-bar", "1")]
        hs = Headers(d)
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual(1, len(hs))

        d = [("foo-bar", "1")]
        hs = Headers(d, bar_foo="2")
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual("2", hs["bar-foo"])
        self.assertEqual(2, len(hs))

    def test_update(self):
        h = Headers()
        h["foo"] = "1"
        self.assertEqual("1", h["foo"])
        h.update({"foo": "2"})
        self.assertEqual("2", h["foo"])

