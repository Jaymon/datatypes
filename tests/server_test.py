# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from threading import Thread
import weakref

from datatypes.compat import *
from datatypes import environ
from datatypes.url import Url
from datatypes.server import (
    ServerThread,
    PathServer,
    CallbackServer,
    WSGIServer,
)
from . import TestCase, testdata


class ServerTestCase(TestCase):
    def create_server(self, v, **kwargs):
        s = self.server_class(v, **kwargs)

        return ServerThread(s)




        if start:
            self.start_server(s)

        return s

    def start_server(self, server):
        """Start the server"""
        def target():
            server.serve_forever(poll_interval=0.1)

        #from threading import Thread
        thread = Thread(target=target)
        thread.daemon = True
        thread.start()

        # enables cleanup of open sockets even if the object isn't correctly
        # garbage collected
        # https://stackoverflow.com/a/42907819
        # https://docs.python.org/3.6/library/weakref.html#finalizer-objects
#         weakref.finalize(server, self.stop_server, server)

        self.servers = getattr(self, "servers", [])
        self.servers.append((server, thread))

    def tearDown(self):
        servers = getattr(self, "servers", [])
        while servers:
            server, thread = servers.pop()
            server.shutdown()
            server.server_close()
            #server.socket.close()
            thread.join()

#     def stop_server(self, server):
#         server.shutdown()

    def get_url(self, s, **kwargs):
        return s.get_url(**kwargs)


class PathServerTest(ServerTestCase):

    server_class = PathServer

    def test_crud(self):
        path = testdata.create_files({
            "foo.txt": testdata.get_unicode_words(),
            "bar/che.txt": testdata.get_unicode_words(),
            "baz/image.png": lambda p: testdata.create_png(path=p),
        })

        s = self.create_server(path)

        r = testdata.fetch(s.get_url(path="/foo.txt"))
        self.assertEqual(path.file_text("foo.txt"), r.content)
        self.assertEqual(path.file_bytes("foo.txt"), r._body)

        r = testdata.fetch(s.get_url(path="/baz/image.png"))
        self.assertEqual(path.file_bytes("baz/image.png"), r._body)

    def test_url(self):
        path = testdata.create_files({
            "foo.txt": testdata.get_unicode_words(),
        })

        s = self.create_server(path)

        r = testdata.fetch(s.get_url(path="/foo.txt?bar=1&che=2"))
        self.assertEqual(path.file_text("foo.txt"), r.content)

    def test_serve(self):
        """Moved and refactored from testdata on 1-24-2023"""
        server = self.create_server(testdata.create_files({
            "foo.txt": ["foo"],
            "bar.txt": ["bar"],
        }))

        res = testdata.fetch(self.get_url(server, path="foo.txt"))
        self.assertEqual("foo", res.content)

        res = testdata.fetch(self.get_url(server, path="bar.txt"))
        self.assertEqual("bar", res.content)

    def test_server_encoding(self):
        """Moved from testdata on 1-24-2023"""
        name = testdata.get_filename(ext="txt")
        content = testdata.get_unicode_words()
        server = self.create_server(testdata.create_files({
            name: content,
        }))

        res = testdata.fetch(self.get_url(server, path=name))
        self.assertEqual(environ.ENCODING.upper(), res.encoding.upper())
        self.assertEqual(content, res.content)

        server = self.create_server(testdata.create_files({
            name: content,
        }, encoding="UTF-16"), encoding="UTF-16")

        res = testdata.fetch(self.get_url(server, path=name))
        self.assertNotEqual("UTF-8", res.encoding.upper())
        self.assertEqual(content, res.content)


class CallbackServerTest(ServerTestCase):

    server_class = CallbackServer

    def test_crud(self):
        s = self.create_server({
            "GET": lambda *args, **kwargs: "GET",
            "POST": lambda *args, **kwargs: "POST",
        })

        r = testdata.fetch(self.get_url(s, path="foo/bar"))
        self.assertEqual("GET", r.body)

        r = testdata.fetch(self.get_url(s, path="foo/bar"), body={"foo": 1})
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

        res = testdata.fetch(self.get_url(s, path="/foo/bar/get?foo=1"))
        self.assertEqual(204, res.status_code)

        res = testdata.fetch(self.get_url(s, path="/foo/bar/post"), {"foo": 1})
        self.assertEqual(200, res.status_code)

        res = testdata.fetch(self.get_url(s, path="/foo/bar/bogus"), method="BOGUS")
        self.assertEqual(501, res.status_code)

        res = testdata.fetch(self.get_url(s, path="/foo/bar/head"), method="HEAD")
        self.assertEqual(500, res.status_code)


class WSGIServerTest(ServerTestCase):

    server_class = WSGIServer

    def test_crud(self):
        s = self.create_server(testdata.create_file([
            "def application(environ, start_response):",
            "   start_response('200 OK', [])",
            "   return [b'GET']",
        ], path="wsgi.py"))

        r = testdata.fetch(self.get_url(s, path="/foo/bar?foo=1"))
        self.assertEqual(200, r.code)
        self.assertEqual("GET", r.content)

