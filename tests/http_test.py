# -*- coding: utf-8 -*-
import email

from datatypes.compat import *
from datatypes.http import (
    HTTPHeaders,
    HTTPEnviron,
    HTTPClient,
    HTTPResponse,
    UserAgent,
    Multipart,
)
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
        """Previously, before June 2019, our headers didn't handle WebSocket
        correctly instead lowercasing the S to Websocket"""
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
        """when setting headers using 2 different original keys it wouldn't be
        uniqued"""
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

    def test_multiple(self):
        h = HTTPHeaders()

        h.update({
            "content-type": "application/json",
        })

        h.update({
            "content-type": "application/json+2",
        })

        h.update({
            "content-type": "application/json+3",
        })

        vs = h.get_all("content-type")
        self.assertEqual(1, len(vs))
        self.assertTrue("json+3" in vs[0])

        h.set_header("content-type", "application/json+4")
        vs = h.get_all("content-type")
        self.assertEqual(1, len(vs))
        self.assertTrue("json+4" in vs[0])

        h.add_header("content-type", "application/json+5")
        vs = h.get_all("content-type")
        self.assertEqual(2, len(vs))

        h.set_header("content-type", "application/json+6")
        vs = h.get_all("content-type")
        self.assertEqual(1, len(vs))

    def test_delete_header(self):
        h = HTTPHeaders()

        h.delete_header("content-type")

        h.set_header("content-type", "text/plain")
        self.assertTrue(h.has_header("content-type"))

        h.delete_header("content-type")
        self.assertFalse(h.has_header("content-type"))

    def test_get_cookies(self):
        headers = email.message_from_bytes((
            b"Server: SimpleHTTP/0.6 Python/3.10.14"
            b"\nDate: Tue, 07 Jan 2025 00:48:46 GMT"
            b"\nSet-Cookie: foo=w4D6PIVaDb6Pmmzg"
            b"\nSet-Cookie: bar=weQMzmtGKZb3FMoCk"
            b"\nSet-Cookie: che=1\n\n"
        ))

        hs = HTTPHeaders(headers)
        cs = hs.get_cookies()

        self.assertEqual(3, len(cs))
        for k in ["foo", "bar", "che"]:
            self.assertTrue(k in cs)

    def test_get_media_type(self):
        hs = HTTPHeaders()
        hs["Content-Type"] = "foo/bar;charset=BooBoo"
        self.assertEqual("foo/bar", hs.get_media_type())


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

    def test_get_fetch_url(self):
        """Moved from endpoints.tests.client on 11-15-2024"""
        c = HTTPClient()

        uri = "http://foo.com"
        url = c.get_fetch_url(uri)
        self.assertEqual(uri, url)

        uri = "/foo/bar"
        url = c.get_fetch_url(uri)
        self.assertEqual("{}{}".format(c.base_url, uri), url)

        url = c.get_fetch_url(["foo", "bar"])
        self.assertEqual("{}{}".format(c.base_url, "/foo/bar"), url)

    def test_iter_content(self):
        content = testdata.get_ascii(2000)
        r = HTTPResponse(200, ByteString(content), {}, None, None)
        rc = ""
        for rch in r.iter_content(100):
            rc += rch
        self.assertEqual(content, rc)

    def test_files(self):
        def POST(handler):
            return handler.body["file1"].read().decode(handler.encoding)

        server = self.create_callbackserver({
            "POST": POST,
        })

        data = "this is the file body"
        p = self.create_file(data, ext="txt")

        with server:
            c = HTTPClient(server)
            res = c.post(server, body={"foo": "bar"}, files={"file1": p})
            self.assertEqual(data, res.body)

    def test_basic_auth(self):
        """Adopted from endpoints.tests.client on 11-15-2024"""
        c = HTTPClient("http://localhost")
        c.basic_auth("foo", "bar")
        self.assertTrue(c.headers["Authorization"].startswith("Basic "))
        self.assertRegex(c.headers["authorization"], r"Basic\s+[a-zA-Z0-9=]+")

        c.remove_auth()
        self.assertFalse("Authorization" in c.headers)

    def test_post_json(self):
        server = self.create_callbackserver({
            "POST": lambda handler: handler.body,
        })

        with server:
            c = HTTPClient(server, json=True)
            body = {"foo": 1, "bar": [2, 3], "che": "four"}
            r = c.post("/", body)
            self.assertEqual(body, r.body)

    def test_post_urlencoded(self):
        c = HTTPClient("http://localhost")

        with self.assertRaises(TypeError):
            c.get_request_urlencoded(["1", "2"])

        with self.assertRaises(TypeError):
            c.get_request_urlencoded("foo")

    def test_get_content_type(self):
        server = self.create_callbackserver({
            "GET": lambda handler: str(handler.headers),
        })

        with server:
            c = HTTPClient(server)
            r = c.get("/")
            self.assertFalse("content-type:" in r.body.lower())

    def test_cookies(self):
        server = self.create_callbackserver({
            "GET": lambda handler: None,
        })
        with server:
            c = HTTPClient(server)
            r = c.get("", cookies={"foo": "1"})
            self.assertTrue("Cookie" in r.request.headers)


class UserAgentTest(TestCase):
    def test_user_agent(self):
        user_agents = [
            (
                (
                    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/44.0.2403.157 Safari/537.36"
                ),
                {
                    'client_application': "Chrome",
                    'client_version': "44.0.2403.157",
                    'client_device': "Windows NT 6.3"
                }
            ),
            (
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_3) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/44.0.2403.157 Safari/537.36"
                ),
                {
                    'client_application': "Chrome",
                    'client_version': "44.0.2403.157",
                    'client_device': "Macintosh"
                }
            ),
            (
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:40.0) "
                    "Gecko/20100101 Firefox/40.0"
                ),
                {
                    'client_application': "Firefox",
                    'client_version': "40.0",
                    'client_device': "Macintosh"
                }
            ),
            (
                (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) "
                    "AppleWebKit/600.7.12 (KHTML, like Gecko) "
                    "Version/8.0.7 Safari/600.7.12"
                ), # Safari
                {
                    'client_application': "Safari",
                    'client_version': "600.7.12",
                    'client_device': "Macintosh"
                }
            ),
            (
                (
                    "curl/7.24.0 (x86_64-apple-darwin12.0) libcurl/7.24.0 "
                    "OpenSSL/0.9.8x zlib/1.2.5"
                ),
                {
                    'client_application': "curl",
                    'client_version': "7.24.0",
                    'client_device': "x86_64-apple-darwin12.0"
                }
            )
        ]

        for user_agent in user_agents:
            ua = UserAgent(user_agent[0])
            for k, v in user_agent[1].items():
                self.assertEqual(v, getattr(ua, k))


class MultipartTest(TestCase):
    def test_encode_decode(self):
        me = Multipart.encode("form-data")

        fields = {
            "foo": "1",
            "bar": "2"
        }
        me.add_fields(fields)

        p = self.create_file("this is the file body", ext="txt")
        me.add_file(p, name="file1")

        for count, part in enumerate(me, 1):
            continue
        self.assertEqual(3, count)

        md = Multipart.decode(me.headers, me.body)

        p = self.create_file("file body 2", ext="txt")
        md.add_file(p)

        for count, part in enumerate(md, 1):
            continue
        self.assertEqual(4, count)

    def test_boundary(self):
        me = Multipart.encode("form-data")
        me.add_field("foo", 1)

        self.assertIsNone(me.boundary)

        # set cache
        me.body
        boundary = me.boundary

        me.add_field("bar", 2)
        self.assertEqual(boundary, me.boundary)

    def test_encode_io(self):
        mt = Multipart("form-data")
        p = self.create_file("io file body", ext="txt")
        with p.open() as fp:
            mt.add_file(fp)

        for count, part in enumerate(mt, 1):
            self.assertEqual(p.read_bytes(), part.body)
        self.assertEqual(1, count)

    def test_related(self):
        mt = Multipart.encode("related")

        mt.add_field("foo", "bar")

        p = self.create_file("io file body", ext="txt")
        mt.add_file(p)

        self.assertTrue(b"/related" in bytes(mt.headers))
        self.assertTrue(b"io file body" in mt.body)
        self.assertTrue(b"foo" in mt.body)

        for count, part in enumerate(mt, 1):
            continue
        self.assertEqual(2, count)

