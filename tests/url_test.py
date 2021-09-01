# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.url import (
    Url,
    Host,
    Urlpath,
)

from . import TestCase, testdata


class UrlTest(TestCase):
    def test_query_parsing_bool(self):
        qkw = Url.parse_query("che&foo&bar=1")
        self.assertEqual("True", qkw["che"])
        self.assertEqual("True", qkw["foo"])
        self.assertEqual("1", qkw["bar"])

        qkw = Url.parse_query("che/")
        self.assertEqual("True", qkw["che/"])

    def test_scheme_with_path(self):
        u = Url("scheme:///foo/bar?query=val")
        self.assertEqual("", u.hostloc)
        self.assertEqual("foo/bar", u.path)
        self.assertEqual("scheme", u.scheme)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))

        u = Url("scheme:///foo/bar")
        self.assertEqual("", u.hostloc)
        self.assertEqual("foo/bar", u.path)
        self.assertEqual("scheme", u.scheme)

    def test_host_trailing_slash(self):
        u = Url("example.com/foo/bar")
        self.assertEqual("example.com", u.hostloc)
        self.assertEqual("foo/bar", u.path)

        u = Url("example.com/")
        self.assertEqual("example.com", u.hostloc)
        self.assertEqual("", u.path)

    def test_normalize_query_kwargs(self):
        d = {b'foo': [b'bar'], b'baz': [b'che']}
        r = Url.normalize_query_kwargs(d)
        self.assertEqual({'foo': b'bar', 'baz': b'che'}, r)

    def test_parent(self):
        u = Url("http://example.com/foo/bar/che")

        u2 = u.parent(che=4)
        self.assertEqual("http://example.com/foo/bar?che=4", u2)

        u2 = u.parent("baz", che=4)
        self.assertEqual("http://example.com/foo/bar/baz?che=4", u2)

        u = Url("http://example.com/")
        u2 = u.parent("baz", che=5)
        self.assertEqual("http://example.com/baz?che=5", u2)

    def test_no_scheme_localhost(self):
        h = Url("//localhost:8080/foo/bar?che=1")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)
        self.assertEqual("foo/bar", h.path)
        self.assertEqual("che=1", h.query)
        self.assertEqual("http", h.scheme)

        h = Url("localhost:8080/foo/bar?che=1")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)
        self.assertEqual("foo/bar", h.path)
        self.assertEqual("che=1", h.query)
        self.assertEqual("http", h.scheme)

        h = Url("http://localhost:8080/foo/bar?che=1")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)
        self.assertEqual("foo/bar", h.path)
        self.assertEqual("che=1", h.query)
        self.assertEqual("http", h.scheme)

        h = Url("n://localhost:8080/foo/bar?che=1")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)
        self.assertEqual("foo/bar", h.path)
        self.assertEqual("che=1", h.query)
        self.assertEqual("n", h.scheme)

        h = Url("localhost:8080/foo/bar")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)

        h = Url("localhost:8080")
        self.assertEqual(8080, h.port)
        self.assertEqual("localhost", h.hostname)

        h = Url("localhost")
        self.assertEqual(80, h.port)
        self.assertEqual("localhost", h.hostname)

    def test_no_scheme_domain(self):
        u = Url("example.com:8080?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(8080, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("//example.com:8080?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(8080, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("example.com?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(80, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("example.com/foo/bar")
        self.assertEqual("http", u.scheme)
        self.assertEqual(80, u.port)
        self.assertEqual({}, u.query_kwargs)
        self.assertEqual("foo/bar", u.path)

        u = Url("example.com/foo/bar?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(80, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("foo/bar", u.path)

        u = Url("/foo/bar?query=val")
        self.assertEqual("http", u.scheme)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))

    def test_no_scheme_ip(self):
        u = Url("127.0.0.1:8080?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(8080, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("//127.0.0.1:8080?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(8080, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("127.0.0.1:8080/foo/bar?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(8080, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("foo/bar", u.path)

        u = Url("127.0.0.1?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(80, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("", u.path)

        u = Url("127.0.0.1/foo/bar?query=val")
        self.assertEqual("http", u.scheme)
        self.assertEqual(80, u.port)
        self.assertTrue("query" in u.query_kwargs)
        self.assertEqual(1, len(u.query_kwargs))
        self.assertEqual("foo/bar", u.path)

    def test_base(self):
        u = Url("http://example.com/path/part")
        u2 = u.base(che=4)
        self.assertEqual("http://example.com/path/part?che=4", u2)

        u = Url("http://example.com/path/part/?che=3")
        u2 = u.base("foo", "bar", che=4)
        self.assertEqual("http://example.com/path/part/foo/bar?che=4", u2)

        u = Url("http://example.com/")
        u2 = u.base("foo", "bar", che=4)
        self.assertEqual("http://example.com/foo/bar?che=4", u2)

    def test_host(self):
        u = Url("http://example.com/path/part/?che=3")
        u2 = u.host("foo", "bar", che=4)
        self.assertEqual("http://example.com/foo/bar?che=4", u2)
        self.assertEqual(u2.host(), u.host())

    def test_copy(self):
        u = Url("http://example.com/path/part/?che=3")
        u2 = u.copy()
        self.assertEqual(u, u2)

    def test_query(self):
        h = Url(query="foo=bar")
        self.assertEqual({"foo": "bar"}, h.query_kwargs)

    def test_query_kwargs(self):
        u = Url("http://example.com/path/part/?che=3", query="baz=4&bang=5", query_kwargs={"foo": 1, "bar": 2})
        self.assertEqual({"foo": 1, "bar": 2, "che": "3", "baz": "4", "bang": "5"}, u.query_kwargs)

        u = Url("http://example.com/path/part/?che=3", query_kwargs={"foo": 1, "bar": 2})
        self.assertEqual({"foo": 1, "bar": 2, "che": "3"}, u.query_kwargs)

        u = Url("http://example.com/path/part/", query_kwargs={"foo": 1, "bar": 2})
        self.assertEqual({"foo": 1, "bar": 2}, u.query_kwargs)

    def test_create(self):
        u = Url("http://example.com/path/part/?query1=val1")
        self.assertEqual("http://example.com/path/part", u.base())
        self.assertEqual({"query1": "val1"}, u.query_kwargs)

        u2 = u.host("/foo/bar", query1="val2")
        self.assertEqual("http://example.com/foo/bar?query1=val2", u2)

    def test_port_override(self):
        u = Url("http://example.com:1000", port=22)
        self.assertEqual("example.com:22", u.netloc)

        scheme = "http"
        host = "localhost:9000"
        path = "/path/part"
        query = "query1=val1"
        port = "9000"
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual("http://localhost:9000/path/part?query1=val1", u)

        port = "1000"
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual("http://localhost:1000/path/part?query1=val1", u)
        self.assertEqual("localhost:1000", u.netloc)

        host = "localhost"
        port = "2000"
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual("http://localhost:2000/path/part?query1=val1", u)

        host = "localhost"
        port = "80"
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual("http://localhost/path/part?query1=val1", u)

        scheme = "https"
        host = "localhost:443"
        port = None
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual("https://localhost/path/part?query1=val1", u)

    def test_port_standard(self):
        h = Url("localhost:80")
        self.assertEqual("http://localhost", h)
        self.assertEqual(80, h.port)

        h = Url("http://localhost:80")
        self.assertEqual("http://localhost", h)
        self.assertEqual(80, h.port)

        h = Url("http://example.com:80")
        self.assertEqual("http://example.com", h)
        self.assertEqual(80, h.port)

        h = Url("http://user:pass@foo.com:80")
        self.assertEqual("http://user:pass@foo.com", h)
        self.assertEqual(80, h.port)

        h = Url("https://user:pass@bar.com:443")
        self.assertEqual("https://user:pass@bar.com", h)
        self.assertEqual(443, h.port)

        h = Url("http://localhost:8000")
        self.assertEqual("http://localhost:8000", h)
        self.assertEqual(8000, h.port)

        h = Url("http://localhost:4436")
        self.assertEqual("http://localhost:4436", h)
        self.assertEqual(4436, h.port)

        h = Url("http://localhost")
        self.assertEqual("http://localhost", h)
        self.assertEqual(80, h.port)

    def test_override(self):
        host = "0.0.0.0:4000"
        u = Url(host, hostname=Host(host).client())
        self.assertFalse(host in u)

        host = "https://0.0.0.0:4000"
        u = Url(host, hostname=Host(host).client())
        self.assertFalse(host in u)
        self.assertTrue("https://" in u)

    def test_merge(self):
        us = "http://foo.com/path?arg1=1&arg2=2#fragment"
        parts = Url.merge(us, query="foo3=3")
        self.assertTrue("foo3=3" in parts["urlstring"])

        us1 = "http://foo.com/path?arg1=1&arg2=2#fragment"
        parts1 = Url.merge(us, username="john", password="doe")
        us2 = "http://john:doe@foo.com/path?arg1=1&arg2=2#fragment"
        parts2 = Url.merge(us2)
        self.assertEqual(parts1, parts2)

    def test___add__(self):

        h = Url("http://localhost")

        h2 = h + {"arg1": 1}
        self.assertEqual("{}?arg1=1".format(h), h2)

        h2 = h + ("foo", "bar")
        self.assertEqual("{}/foo/bar".format(h), h2)

        h2 = h + "/foo/bar"
        self.assertEqual("{}/foo/bar".format(h), h2)

        h2 = h + b"/foo/bar"
        self.assertEqual("{}/foo/bar".format(h), h2)

        h2 = h + ["foo", "bar"]
        self.assertEqual("{}/foo/bar".format(h), h2)

        h = Url("http://localhost/1/2")

        h2 = h + "/foo/bar"
        self.assertEqual("{}/foo/bar".format(h.root), h2)

        h2 = h + b"/foo/bar"
        self.assertEqual("{}/foo/bar".format(h.root), h2)

        h2 = h + ["foo", "bar"]
        self.assertEqual("{}/foo/bar".format(h), h2)

        h2 = h + ["/foo", "bar"]
        self.assertEqual("{}/foo/bar".format(h.root), h2)

    def test___sub__(self):
        h = Url("http://foo.com/1/2/3?arg1=1&arg2=2#fragment")

        h2 = h - "2/3"
        self.assertFalse("2/3" in h2)

        h2 = h - ["2", "3"]
        self.assertFalse("2/3" in h2)

        h2 = h - ("2", "3")
        self.assertFalse("2/3" in h2)

        h2 = h - {"arg1": 1}
        self.assertFalse("arg1" in h2)

    def test___isub__(self):
        h = Url("http://foo.com/1/2/3?arg1=1&arg2=2#fragment")

        h -= "2/3"
        self.assertFalse("2/3" in h)

        h -= ["2", "3"]
        self.assertFalse("2/3" in h)

        h -= ("2", "3")
        self.assertFalse("2/3" in h)

        h -= {"arg1": 1}
        self.assertFalse("arg1" in h)

    def test_add(self):
        u = Url("http://example.com/path/part/?che=3")
        u2 = u.add(query_kwargs={"foo": 1})
        self.assertEqual({"foo": 1, "che": "3"}, u2.query_kwargs)
        self.assertEqual("http://example.com/path/part", u2.base())

    def test_subtract(self):
        h = Url("http://foo.com/1/2/3?arg1=1&arg2=2#fragment")

        h2 = h.subtract("2", "3")
        self.assertFalse("2/3" in h2)

        h2 = h.subtract(query_kwargs={"arg1": 1})
        self.assertFalse("arg1" in h2)

    def test_hostloc_netloc(self):
        scheme = "http"
        host = "localhost"
        path = "/path/part"
        query = "query1=val1"
        port = "80"
        u = Url(scheme=scheme, hostname=host, path=path, query=query, port=port)
        self.assertEqual(host, u.netloc)
        self.assertEqual(host, u.hostloc)

        u = Url("http://username:password@example.com:1000", port=8080)
        self.assertEqual("username:password@example.com:8080", u.netloc)
        self.assertEqual("example.com:8080", u.hostloc)

    def test_default_port(self):
        u = Url("http://example.com:1000", default_port=22)
        self.assertEqual(1000, u.port)

        u = Url("http://example.com", default_port=22)
        self.assertEqual(22, u.port)

        u = Url("http://example.com", port=8080, default_port=22)
        self.assertEqual(8080, u.port)

        u = Url("http://example.com:1000", port=8080, default_port=22)
        self.assertEqual(8080, u.port)

    def test_keys(self):
        class MyUrl(Url):
            foo = {}
            bar = ""
            che = None

        u = MyUrl()
        ks = u.keys()
        dvs = MyUrl.default_values()

        for k in ["foo", "bar", "che", "port", "scheme"]:
            self.assertTrue(k in ks)
            self.assertTrue(k in dvs)


class HostTest(TestCase):
    def test___new__(self):
        h = Host("http://example.com:1000", 22)
        self.assertEqual(1000, h.port)
        self.assertEqual("example.com", h.hostname)
        self.assertEqual("example.com:1000", h.hostloc)

        h = Host("http://example.com", 22)
        self.assertEqual(22, h.port)
        self.assertEqual("example.com", h.hostname)
        self.assertEqual("example.com:22", h.hostloc)

        h = Host("example.com:1000")
        self.assertEqual(1000, h.port)
        self.assertEqual("example.com", h.hostname)
        self.assertEqual("example.com:1000", h.hostloc)

        h = Host("0.0.0.0:4000")
        self.assertEqual(4000, h.port)
        self.assertEqual("0.0.0.0", h.hostname)
        self.assertEqual("0.0.0.0:4000", h.hostloc)

    def test_client(self):
        h = Host("0.0.0.0:546")
        self.assertFalse("0.0.0.0:" in h.client())
        self.assertTrue("0.0.0.0:546" in h.hostloc)

        h = Host("0.0.0.0", 22)
        self.assertFalse("0.0.0.0:" in h.client())
        self.assertTrue("0.0.0.0:22" in h.hostloc)

    def test_port(self):
        h = Host("localhost:8080")
        self.assertEqual(8080, h.port)

        h = Host("localhost")
        self.assertEqual(0, h.port)

        h = Host("localhost:")
        self.assertEqual(0, h.port)


class UrlpathTest(TestCase):
    def test_path_set(self):
        url = testdata.get_url()
        path = testdata.get_file("pathset.ext")
        up = Urlpath(url, path)
        self.assertEqual(url, up.url)
        self.assertEqual(path, up.path)

    def test_read(self):
        self.skip_test("functionality has not been added yet")

