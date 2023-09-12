# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.http import HTTPHeaders, HTTPEnviron, HTTPClient, HTTPResponse
from datatypes.string import String, ByteString
from datatypes.config.environ import environ


from . import TestCase, testdata


class HTTPEnvironTest(TestCase):
    def test_values(self):
        d = HTTPEnviron()

        d["foo"] = None
        self.assertEqual(None, d["foo"])

        d["bar"] = 1
        self.assertEqual(1, d["bar"])


class HTTPHeadersTest(TestCase):
    def test_midbody_capital_letter(self):
        """Previously, before June 2019, our headers didn't handle WebSocket correctly
        instead lowercasing the S to Websocket"""
        d = HTTPHeaders()
        d["Sec-WebSocket-Key"] = "foobar"
        self.assertTrue("Sec-Websocket-Key" in d)
        d2 = dict(d)
        self.assertFalse("Sec-Websocket-Key" in d2)
        self.assertTrue("Sec-WebSocket-Key" in d2)

    def test_bytes(self):
        d = HTTPHeaders()
        name = testdata.get_unicode()
        val = ByteString(testdata.get_unicode())
        d[name] = val
        self.assertEqual(d[name], String(val))

    def test_different_original_keys(self):
        """when setting headers using 2 different original keys it wouldn't be uniqued"""
        d = HTTPHeaders()
        d['Content-Type'] = "application/json"
        d['content-type'] = "text/plain"
        self.assertEqual(1, len(d))
        self.assertEqual("text/plain", d["CONTENT-TYPE"])

    def test_lifecycle(self):
        d = HTTPHeaders()
        d["foo-bar"] = 1
        self.assertEqual("1", d["Foo-Bar"])
        self.assertEqual("1", d["fOO-bAr"])
        self.assertEqual("1", d["fOO_bAr"])

    def test_pop(self):
        d = HTTPHeaders()
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
        headers = HTTPHeaders(d)

        for k in keys:
            self.assertEqual(v, headers["Content-Type"])

        headers = HTTPHeaders()
        headers["CONTENT_TYPE"] = v

        for k in keys:
            self.assertEqual(v, headers["Content-Type"])

        #with self.assertRaises(KeyError):
        #    headers["foo-bar"]

        for k in keys:
            self.assertTrue(k in headers)

    def test_iteration(self):
        hs = HTTPHeaders()
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
        hs = HTTPHeaders(d)
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual(1, len(hs))

        d = [("foo-bar", "1")]
        hs = HTTPHeaders(d)
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual(1, len(hs))

        d = [("foo-bar", "1")]
        hs = HTTPHeaders(d, bar_foo="2")
        self.assertEqual("1", hs["foo-bar"])
        self.assertEqual("2", hs["bar-foo"])
        self.assertEqual(2, len(hs))

    def test_update(self):
        h = HTTPHeaders()
        h["foo"] = "1"
        self.assertEqual("1", h["foo"])
        h.update({"foo": "2"})
        self.assertEqual("2", h["foo"])

    def test_parse(self):
        h = HTTPHeaders()
        h["foo-bar"] = "application/json; charset=\"utf8\"; che=1; bar=2"
        main, params = h.parse("foo-BAR")
        self.assertEqual("application/json", main)
        self.assertEqual(3, len(params))
        self.assertEqual("1", params["che"])

        h["content-type"] = "application/json; charset=\"utf8\""
        main, params = h.parse("CONTENT_TYPE")
        self.assertEqual("application/json", main)
        self.assertEqual(1, len(params))

        h["content-type"] = "application/json"
        main, params = h.parse("CONTENT_TYPE")
        self.assertEqual("application/json", main)
        self.assertEqual(0, len(params))

        main, params = h.parse("Does-Not-Exist")
        self.assertEqual("", main)
        self.assertEqual(0, len(params))

    def test_is_methods(self):
        h = HTTPHeaders()

        h["Content-Type"] = "application/x-www-form-urlencoded"
        self.assertTrue(h.is_urlencoded())
        self.assertFalse(h.is_multipart())
        self.assertFalse(h.is_plain())
        self.assertFalse(h.is_json())

        h["Content-Type"] = "multipart/form-data; boundary=ab4b2773b"
        self.assertFalse(h.is_urlencoded())
        self.assertTrue(h.is_multipart())
        self.assertFalse(h.is_plain())
        self.assertFalse(h.is_json())

        h["Content-Type"] = "application/json"
        self.assertFalse(h.is_urlencoded())
        self.assertFalse(h.is_multipart())
        self.assertFalse(h.is_plain())
        self.assertTrue(h.is_json())

        h["Content-Type"] = "text/plain"
        self.assertFalse(h.is_urlencoded())
        self.assertFalse(h.is_multipart())
        self.assertTrue(h.is_plain())
        self.assertFalse(h.is_json())


class HTTPClientTest(TestCase):
    def test_alternative_method(self):
        def do_PUT(handler):
            return "PUT"

        server = testdata.create_callbackserver({
            "PUT": do_PUT,
        })
        with server:
            c = HTTPClient(server)
            res = c.put(server)
            self.assertEqual(200, res.code)
            self.assertEqual("PUT", res.body)

    def test_get_fetch_user_agent(self):
        c = HTTPClient()

        ua = c.get_fetch_user_agent()
        self.assertTrue("datatypes.HTTPClient/" in ua)

        with testdata.modify(environ, USER_AGENT="foobar"):
            ua = c.get_fetch_user_agent()
            self.assertEqual("foobar", ua)

    def test_get_fetch_headers(self):
        c = HTTPClient()

        headers = c.get_fetch_headers("GET", {}, {})
        self.assertTrue("user-agent" in headers)

        headers = c.get_fetch_headers("GET", {"user-agent": "foo"}, {})
        self.assertEqual(headers["user-agent"], "foo")

    def test_iter_content(self):
        content = testdata.get_ascii(2000)
        r = HTTPResponse(200, ByteString(content), {}, None, None)
        rc = ""
        for rch in r.iter_content(100):
            rc += rch
        self.assertEqual(content, rc)

