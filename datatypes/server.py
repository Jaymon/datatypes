# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import json
import logging
from wsgiref.simple_server import WSGIServer as WSGIHTTPServer, WSGIRequestHandler
import runpy
from threading import Thread
import weakref

from .compat import *
from . import environ
from .url import Host, Url
#from .string import String
from .path import Dirpath
from .decorators import property as cachedproperty


logger = logging.getLogger(__name__)


class ServerThread(Url):
    """This makes it easy to run a Server in another thread, it masquerades as a
    Url instance whose value is the url scheme://hostname:port but adds helper
    methods to start/stop the passed in Server instance and clean up after it

    Moved from testdata.server on 1-24-2023

    :Example:
        s = ServerThread(PathServer("/some/path"))
        with s:
            # make an http request to <SERVER-HOST>/foo/bar.txt
            requests.get(s.child("foo", "bar.txt"))
    """
    @property
    def started(self):
        """Returns True if the webserver has been started"""
        try:
            ret = True if self.thread else False
        except AttributeError:
            ret = False
        return ret

    def __new__(cls, server, **kwargs):
        instance = super().__new__(cls, server.get_url())

        instance.server = server
        instance.server_address = server.server_address
        instance.poll_interval = kwargs.get("poll_interval", 0.5)

        # enables cleanup of open sockets even if the object isn't correctly
        # garbage collected
        # https://stackoverflow.com/a/42907819
        # https://docs.python.org/3.6/library/weakref.html#finalizer-objects
        weakref.finalize(instance, instance.__del__)

        return instance

    def __del__(self):
        self.stop()
        self.server.server_close()

    def __enter__(self):
        """Allows webserver to be used with "with" keyword"""
        self.start()
        return self

    def __exit__(self, esc_type, esc_val, traceback):
        """Allows webserver to be used with "with" keyword"""
        self.stop()

    def target(self):
        self.server.serve_forever(poll_interval=self.poll_interval)

    def start(self):
        """Start the webserver"""
        if self.started: return

#         server = self.server
# 
#         def target():
#             server.serve_forever(poll_interval=self.poll_interval)

        #from multiprocessing import Process
        #from threading import Thread
        #thread = Process(target=self.target)
        thread = Thread(target=self.target)
        thread.daemon = True
        thread.start()
        self.thread = thread

    def stop(self):
        """stop the webserver"""
        if self.started:
            self.server.shutdown()
            self.thread.join()
            self.thread = None


class BaseServer(HTTPServer):
    """Base class for all the other servers that contains common functionality"""
    def __init__(self, server_address=None, encoding="", **kwargs):
        """
        :param server_address: tuple, (hostname, port), if None this will use ("", None)
            which will cause the parent to use 0.0.0.0 and to find an available free
            port
        :param encoding: str, if empty then environment setting will be used
        :param **kwargs: passed to parent
            RequestHandlerClass: will be set to children's handler_class param
        """
        if server_address:
            server_address = Host(*server_address)
        else:
            server_address = Host("", None)

        self.encoding = encoding or environ.ENCODING
        kwargs.setdefault("RequestHandlerClass", self.handler_class)
        super().__init__(server_address, **kwargs)

    def get_url(self, *args, **kwargs):
        """Create a url using the server's server_address information

        :example:
            s = BaseServer()
            print(s.get_url("foo.txt")) # http://localhost:PORT/foo.txt

        :param *args: passed through to Url
        :param **kwargs: passed throught to Url, scheme, hostname, and port will
            be set if not overridden
        :returns: Url instance
        """
        hostname = self.server_address[0]
        if hostname == "0.0.0.0":
            hostname = "localhost"

        kwargs.update(dict(
            hostname=hostname,
            port=self.server_port
        ))
        kwargs.setdefault("scheme", "http")

        return Url(*args, **kwargs)

    def serve_forever(self, *args, **kwargs):
        # wrapped to call server close to avoid unclosed socket warnings
        try:
            super().serve_forever()

        finally:
            self.server_close()


class PathHandler(SimpleHTTPRequestHandler):
    """Handler for PathServer

    the parent classes:
        https://github.com/python/cpython/blob/3.9/Lib/http/server.py
        https://github.com/python/cpython/blob/3.9/Lib/socketserver.py
        https://docs.python.org/3/library/http.server.html
    """
    def __init__(self, *args, encoding=None, **kwargs):
        self.encoding = encoding
        super().__init__(*args, **kwargs)

    def guess_type(self, path):
        """Guess the MIME type of the file at path

        This will also set encoding for text based mime types and not set the
        encoding for binary files

        :param path: str, the path to the file
        :returns: a string suitable to be passed as the value to the HTTP Content-Type
            header. It can have charset set
        """
        t = super().guess_type(path)
        if self.encoding:
            if "plain" in t or "text" in t:
                t += "; charset={}".format(self.encoding)
        return t


class PathServer(BaseServer):
    """A server that serves files from a path

    Moved from testdata.server on 1-24-2023

    :Example:
        basedir = "/some/path/to/directory/containing/files/to/server"
        s = PathServer(basedir)

    https://docs.python.org/3/library/http.server.html
    https://github.com/python/cpython/blob/3.9/Lib/http/server.py
    https://github.com/python/cpython/blob/3.9/Lib/socketserver.py
    """
    handler_class = PathHandler

    def __init__(self, path, *args, **kwargs):
        self.path = Dirpath(path)
        if not self.path.isdir():
            raise ValueError(f"{path} is not a valid directory")

        super().__init__(*args, **kwargs)

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(
            request,
            client_address,
            self,
            directory=self.path,
            encoding=self.encoding,
        )


class CallbackHandler(SimpleHTTPRequestHandler):
    """This is the handler that makes the CallbackServer work"""
    @property
    def uri(self):
        uri = self.path
        i = uri.find("?")
        if i >= 0:
            uri = uri[:i]
        return uri

    @cachedproperty(cached="_query")
    def query(self):
        _query = ""
        i = self.path.find("?")
        if i >= 0:
            _query = self.path[i+1:]
            _query = Url.parse_query(_query)
        return _query

    @cachedproperty(cached="_body")
    def body(self):
        content_len = int(self.headers.get('content-length', 0))
        _body = self.rfile.read(content_len)

        if _body:
            ct = self.headers.get("content-type", "")
            if ct:
                ct = ct.lower()
                if ct.rfind("json") >= 0:
                    _body = json.loads(body)

                else:
                    _body = Url.parse_query(_body)

        return _body

    def __init__(self, callbacks, *args, encoding=None, **kwargs):
        self.encoding = encoding

        if isinstance(callbacks, Mapping):
            self.callbacks = callbacks
        else:
            self.callbacks = {"default": callbacks}

        super().__init__(*args, **kwargs)

    def do_HEAD(self):
        return self.do()

    def do_GET(self):
        return self.do()

    def do(self):
        ret = None
        self.headers_sent = False

        # log request headers
        for h, v in self.headers.items():
            self.log_message("req - %s: %s", h, v)

        try:
            ret = self.callbacks.get(self.command, self.callbacks.get("default"))(self)

        except TypeError:
            if not self.headers_sent:
                self.send_error(501, "Unsupported method {}".format(self.command))

        except Exception as e:
            logger.exception(e)
            if not self.headers_sent:
                self.send_error(500, "{} - {}".format(e.__class__.__name__, e))

        else:
            if ret:
                if not self.headers_sent:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                b = json.dumps(ret)
                self.wfile.write(bytes(b, self.encoding))

            else:
                if not self.headers_sent:
                    self.send_response(204)
                    self.end_headers()

    def __getattr__(self, k):
        """By default, the handler looks for do_<HTTP_METHOD> (eg, do_GET) methods
        on the handler. This routes all those requests to .do() and then uses
        the dict passed in to decide how to route the request"""
        if k.startswith("do_"):
            return self.do
        else:
            raise AttributeError(k)

    def end_headers(self):
        self.headers_sent = True
        return super().end_headers()

    def send_header(self, keyword, value):
        self.log_message("res - %s: %s", keyword, value)
        return super().send_header(keyword, value)


class CallbackServer(BaseServer):
    """A server where you can pass in the handlers for the different HTTP methods

    Moved from testdata.server on 1-24-2023

    :Example:
        def do_GET(handler):
            return "GET REQUEST"

        def do_POST(handler):
            return handler.body

        s = CallbackServer({
            "GET": do_GET,
            "POST": do_POST,
        })
    """
    handler_class = CallbackHandler

    def __init__(self, callbacks, *args, **kwargs):
        self.callbacks = callbacks
        super().__init__(*args, **kwargs)

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(
            self.callbacks,
            request,
            client_address,
            self,
            encoding=self.encoding,
        )


class WSGIServer(BaseServer, WSGIHTTPServer):
    """Starts a wsgi server using a wsgifile, the wsgifile is a python file that
    has an application property

    Moved from testdata.server on 1-24-2023

    https://docs.python.org/3/library/wsgiref.html

    :Example:
        # wsgi.py
        def application(environ, start_response):
            print(environ)
            start_response('200 OK', [])
            return [b"WSGI Request"] # needs to be list<bytes>

        s = WSGIServer("/path/to/wsgi.py")
    """
    handler_class = WSGIRequestHandler

    def __init__(self, wsgipath, *args, **kwargs):
        super().__init__(*args, **kwargs)

        config = runpy.run_path(wsgipath)
        self.set_app(config["application"])
        self.config = config
        self.wsgipath = wsgipath

