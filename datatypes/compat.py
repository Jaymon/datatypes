# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys

try:
    import cPickle as pickle
except ImportError:
    import pickle

# shamelessly ripped from https://github.com/kennethreitz/requests/blob/master/requests/compat.py
# Syntax sugar.
_ver = sys.version_info
is_py2 = _ver[0] == 2
is_py3 = _ver[0] == 3

if is_py2:
    basestring = basestring
    unicode = unicode
    range = xrange # range is now always an iterator
    input = raw_input
    cmp = cmp

    import Queue as queue

    # using _* makes __all__ not export this automatically, so you have to
    # explicitly import htis (from datatypes.compat import _thread), the reason
    # is because the thread module is lowkey deprecated in favor of the
    # threading module
    #
    # https://stackoverflow.com/questions/1141047/why-was-the-thread-module-renamed-to-thread-in-python-3-x
    #
    # I've chosen to keep the _thread syntax to prod me into finding a better
    # way to do something, but I still have access to it explicitely if I need it
    import thread as _thread

    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO

    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from BaseHTTPServer import (
        BaseHTTPRequestHandler,
        HTTPServer,
    )
    import SocketServer as socketserver
    import Cookie as cookies
    import __builtin__ as builtins

    from urllib import urlencode
    from urllib2 import (
        Request,
        urlopen,
        URLError,
        HTTPError,
    )
    import urlparse as parse

    import itertools
    zip = itertools.izip
    zip_longest = itertools.izip_longest

    from collections import (
        Iterable,
        Mapping,
        Callable,
        MutableSequence,
        Sequence,
    )


    from HTMLParser import HTMLParser
    #unescape = HTMLParser().unescape

    import cgi
    class html(object):
        @classmethod
        def escape(cls, *args, **kwargs):
            return cgi.escape(*args, **kwargs)

        @classmethod
        def unescape(cls, *args, **kwargs):
            return HTMLParser().unescape(*args, **kwargs)

    # NOTE -- getargspace isn't a full mapping of getfullargspec
    from inspect import getargspec as getfullargspec


    exec("""def reraise(exception_class, e, traceback=None):
        try:
            raise exception_class, e, traceback
        finally:
            traceback = None
    """)


else:
    basestring = (str, bytes)
    unicode = str
    long = int
    input = input

    import queue
    import _thread
    from io import StringIO
    from http.server import (
        HTTPServer,
        SimpleHTTPRequestHandler,
        BaseHTTPRequestHandler,
    )
    import socketserver
    from http import cookies
    import builtins

    from html.parser import HTMLParser
    from urllib import parse
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    try:
        import html
        #from html import unescape
    except ImportError:
        import cgi
        class html(object):
            @classmethod
            def escape(cls, *args, **kwargs):
                return cgi.escape(*args, **kwargs)

            @classmethod
            def unescape(cls, *args, **kwargs):
                return HTMLParser().unescape(*args, **kwargs)
        #unescape = HTMLParser.unescape

    from inspect import getfullargspec
    from itertools import zip_longest

    from collections.abc import (
        Iterable,
        Mapping,
        Callable,
        MutableSequence,
        Sequence,
    )


    # ripped from six https://github.com/benjaminp/six
    def reraise(exception_class, e, traceback=None):
        """the 3 params correspond to the return value of sys.exc_info()

        https://docs.python.org/3/library/sys.html#sys.exc_info

        :param exception_class: BaseException, the class of the exception to reraise
        :param e: BaseException instance, the actual exception instance
        :param traceback: traceback, the stack trace
        """
        try:
            e = exception_class("" if e is None else e)
            if e.__traceback__ is not traceback:
                raise e.with_traceback(traceback)
            raise e
        finally:
            e = None
            traceback = None


    # py3 has no cmp function for some strange reason
    # https://codegolf.stackexchange.com/a/49779
    def cmp(a, b):
        return (a > b) - (a < b)


Str = unicode if is_py2 else str
Bytes = str if is_py2 else bytes


# TODO using reraise

#             if py_2:
#                 #raise error_info[0].__class__, error_info[0], error_info[1][2]
#                 reraise(*error_info)
#                 #raise error_info[0].__class__, error_info[1], error_info[2]
# 
#             elif py_3:
#                 #e, exc_info = error_info
#                 #et, ei, tb = exc_info
# 
#                 reraise(*error_info)
#                 #et, ei, tb = error_info
#                 #raise ei.with_traceback(tb)


# if not error_info:
#                     exc_info = sys.exc_info()
#                     #raise e.__class__, e, exc_info[2]
#                     #self.error_info = (e, exc_info)
#                     self.error_info = exc_info
# 
# if error_info:
# 
#             reraise(*error_info)

