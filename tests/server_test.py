# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.config.environ import environ
from datatypes.url import Url
from datatypes.server import (
    ServerThread,
    PathServer,
    CallbackServer,
    WSGIServer,
)
from . import TestCase, testdata


class ServerTestCase(TestCase):
    def create_server(self, v=None, **kwargs):
        s = self.server_class(v, **kwargs)
        return ServerThread(s)


class PathServerTest(ServerTestCase):

    server_class = PathServer

    def test_crud(self):
        path = testdata.create_files({
            "foo.txt": testdata.get_unicode_words(),
            "bar/che.txt": testdata.get_unicode_words(),
            "baz/image.png": lambda p: testdata.create_png(path=p),
        })

        s = self.create_server(path)

        with s:
            r = testdata.fetch(s.child(path="/foo.txt"))
            self.assertEqual(path.file_text("foo.txt"), r.content)
            self.assertEqual(path.file_bytes("foo.txt"), r._body)

            r = testdata.fetch(s.child(path="/baz/image.png"))
            self.assertEqual(path.file_bytes("baz/image.png"), r._body)

    def test_url(self):
        path = testdata.create_files({
            "foo.txt": testdata.get_unicode_words(),
        })

        s = self.create_server(path)

        with s:
            r = testdata.fetch(s.child(path="/foo.txt?bar=1&che=2"))
            self.assertEqual(path.file_text("foo.txt"), r.content)

    def test_serve(self):
        """Moved and refactored from testdata on 1-24-2023"""
        s = self.create_server(testdata.create_files({
            "foo.txt": ["foo"],
            "bar.txt": ["bar"],
        }))

        with s:
            res = testdata.fetch(s.child(path="foo.txt"))
            self.assertEqual("foo", res.content)

            res = testdata.fetch(s.child(path="bar.txt"))
            self.assertEqual("bar", res.content)

    def test_server_encoding(self):
        """Moved from testdata on 1-24-2023"""
        name = testdata.get_filename(ext="txt")
        content = testdata.get_unicode_words()
        s = self.create_server(testdata.create_files({
            name: content,
        }))

        with s:
            res = testdata.fetch(s.child(path=name))
            self.assertEqual(environ.ENCODING.upper(), res.encoding.upper())
            self.assertEqual(content, res.content)

        s = self.create_server(testdata.create_files({
            name: content,
        }, encoding="UTF-16"), encoding="UTF-16")

        with s:
            res = testdata.fetch(s.child(path=name))
            self.assertNotEqual("UTF-8", res.encoding.upper())
            self.assertEqual(content, res.content)


class CallbackServerTest(ServerTestCase):

    server_class = CallbackServer

    def test_crud(self):
        s = self.create_server({
            "GET": lambda *args, **kwargs: "GET",
            "POST": lambda *args, **kwargs: "POST",
        })

        with s:
            r = testdata.fetch(s.child(path="foo/bar"))
            self.assertEqual("GET", r.body)

            r = testdata.fetch(s.child(path="foo/bar"), body={"foo": 1})
            self.assertEqual("POST", r.body)

    def test_callback(self):
        """Moved from testdata on 1-24-2023"""
        def do_GET(handler):
            return None

        def do_POST(handler):
            return handler.body

        def do_ERROR(handler):
            raise ValueError()

        s = self.create_server({
            "GET": do_GET,
            "POST": do_POST,
            "HEAD": do_ERROR,
        })

        with s:
            res = testdata.fetch(s.child(path="/foo/bar/get?foo=1"))
            self.assertEqual(204, res.status_code)

            res = testdata.fetch(s.child(path="/foo/bar/post"), {"foo": 1})
            self.assertEqual(200, res.status_code)

            res = testdata.fetch(
                s.child(path="/foo/bar/bogus"),
                method="BOGUS"
            )
            self.assertEqual(501, res.status_code)

            res = testdata.fetch(s.child(path="/foo/bar/head"), method="HEAD")
            self.assertEqual(400, res.status_code)

    def test_multi_start_stop(self):
        s = self.create_server({
            "GET": lambda handler: "get"
        })

        s.start()
        r = testdata.fetch(s)
        self.assertEqual(200, r.status_code)
        s.stop()

        with s:
            r = testdata.fetch(s)
            self.assertEqual(200, r.status_code)

        s.start()
        r = testdata.fetch(s)
        self.assertEqual(200, r.status_code)
        s.stop()

    def test_head(self):
        s = self.create_server({
            "GET": lambda handler: "get"
        })

        with s:
            rg = self.fetch(s, method="GET")
            rh = self.fetch(s, method="HEAD")

            self.assertEqual(rg.status_code, rh.status_code)
            self.assertEqual("", rh.body)
            self.assertNotEqual(rg.body, rh.body)


class WSGIServerTest(ServerTestCase):

    server_class = WSGIServer

    def test_crud(self):
        s = self.create_server(wsgipath=testdata.create_file([
            "def application(environ, start_response):",
            "   start_response('200 OK', [])",
            "   return [b'GET']",
        ], path="wsgi.py"))

        with s:
            r = testdata.fetch(s.child(path="/foo/bar?foo=1"))
            self.assertEqual(200, r.code)
            self.assertEqual("GET", r.content)

