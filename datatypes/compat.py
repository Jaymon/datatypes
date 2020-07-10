# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys
import hashlib

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

    import Queue as queue
    import thread as _thread
    try:
        from cStringIO import StringIO
    except ImportError:
        from StringIO import StringIO

    from SimpleHTTPServer import SimpleHTTPRequestHandler
    from BaseHTTPServer import HTTPServer
    import Cookie as cookies
    import __builtin__ as builtins

    from HTMLParser import HTMLParser
    from urllib import urlencode
    unescape = HTMLParser().unescape
    import urlparse as parse

    import itertools
    zip = itertools.izip
    zip_longest = itertools.izip_longest
    from collections import Iterable, Mapping, Callable


    # NOTE -- getargspace isn't a full mapping of getfullargspec
    from inspect import getargspec as getfullargspec


    exec("""def reraise(exception_class, e, traceback=None):
        try:
            raise exception_class, e, traceback
        finally:
            traceback = None
    """)


elif is_py3:
    basestring = (str, bytes)
    unicode = str
    long = int
    input = input

    import queue
    import _thread
    from io import StringIO
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    from http import cookies
    from urllib import parse as urlparse
    import builtins

    from html.parser import HTMLParser
    from urllib import parse
    from urllib.parse import urlencode
    try:
        from html import unescape
    except ImportError:
        unescape = HTMLParser.unescape

    from inspect import getfullargspec
    from itertools import zip_longest
    from collections.abc import Iterable, Mapping, Callable


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


Str = unicode if is_py2 else str
Bytes = str if is_py2 else bytes

