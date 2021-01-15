# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from wsgiref.headers import Headers as BaseHeaders
import itertools

from .compat import *
from .copy import Deepcopy
from .string import String, ByteString


class Headers(BaseHeaders, Mapping):
    """handles headers, see wsgiref.Headers link for method and use information

    Handles normalizing of header names, the problem with headers is they can
    be in many different forms and cases and stuff (eg, CONTENT_TYPE and Content-Type),
    so this handles normalizing the header names so you can request Content-Type
    or CONTENT_TYPE and get the same value.

    This has the same interface as Python's built-in wsgiref.Headers class but
    makes it even more dict-like and will return titled header names when iterated
    or anything (eg, Content-Type instead of all lowercase content-type)

    http headers spec:
        https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html


    wsgiref class docs:
        https://docs.python.org/2/library/wsgiref.html#module-wsgiref.headers
        https://hg.python.org/cpython/file/2.7/Lib/wsgiref/headers.py
    actual python3 code:
        https://github.com/python/cpython/blob/master/Lib/wsgiref/headers.py
    """
    encoding = "iso-8859-1"
    """From rfc2616:

        The default language is English and the default character set is ISO-8859-1.

        If a character set other than ISO-8859-1 is used, it MUST be encoded in the
        warn-text using the method described in RFC 2047"""

    def __init__(self, headers=None, **kwargs):
        super(Headers, self).__init__([])
        self.update(headers, **kwargs)

    def _convert_string_part(self, bit):
        """each part of a header will go through this method, this allows further
        normalization of each part, so a header like FOO_BAR would call this method
        twice, once with foo and again with bar

        :param bit: string, a part of a header all lowercase
        :returns: string, the normalized bit
        """
        if bit == "websocket":
            bit = "WebSocket"
        else:
            bit = bit.title()
        return bit

    def _convert_string_name(self, k):
        """converts things like FOO_BAR to Foo-Bar which is the normal form"""
        k = String(k, self.encoding)
        bits = k.lower().replace('_', '-').split('-')
        return "-".join((self._convert_string_part(bit) for bit in bits))

    def _convert_string_type(self, v):
        """Override the internal method wsgiref.headers.Headers uses to check values
        to make sure they are strings"""
        # wsgiref.headers.Headers expects a str() (py3) or unicode (py2), it
        # does not accept even a child of str, so we need to convert the String
        # instance to the actual str, as does the python wsgi methods, so even
        # though we override this method we still return raw() strings so we get
        # passed all the type(v) == "str" checks
        # sadly, this method is missing in 2.7
        # https://github.com/python/cpython/blob/2.7/Lib/wsgiref/headers.py
        return String(v).raw()

    def get_all(self, name):
        name = self._convert_string_name(name)
        return super(Headers, self).get_all(name)

    def get(self, name, default=None):
        name = self._convert_string_name(name)
        return super(Headers, self).get(name, default)

    def __delitem__(self, name):
        name = self._convert_string_name(name)
        return super(Headers, self).__delitem__(name)

    def __setitem__(self, name, val):
        name = self._convert_string_name(name)
        if is_py2:
            val = self._convert_string_type(val)
        return super(Headers, self).__setitem__(name, val)

    def setdefault(self, name, val):
        name = self._convert_string_name(name)
        if is_py2:
            val = self._convert_string_type(val)
        return super(Headers, self).setdefault(name, val)

    def add_header(self, name, val, **params):
        name = self._convert_string_name(name)
        if is_py2:
            val = self._convert_string_type(val)
        return super(Headers, self).add_header(name, val, **params)

    def keys(self):
        return [k for k, v in self._headers]

    def items(self):
        for k, v in self._headers:
            yield k, v

    def iteritems(self):
        return self.items()

    def iterkeys(self):
        for k in self.keys():
            yield k

    def __iter__(self):
        for k, v in self._headers:
            yield k

    def pop(self, name, *args, **kwargs):
        """remove and return the value at name if it is in the dict

        This uses *args and **kwargs instead of default because this will raise
        a KeyError if default is not supplied, and if it had a definition like
        (name, default=None) you wouldn't be able to know if default was provided
        or not

        :param name: string, the key we're looking for
        :param default: mixed, the value that would be returned if name is not in
            dict
        :returns: the value at name if it's there
        """
        val = self.get(name)
        if val is None:
            if args:
                val = args[0]
            elif "default" in kwargs:
                val = kwargs["default"]
            else:
                raise KeyError(name)

        else:
            del self[name]

        return val

    def update(self, headers, **kwargs):
        if not headers: headers = {}
        if isinstance(headers, Mapping):
            headers.update(kwargs)
            headers = headers.items()

        else:
            if kwargs:
                headers = itertools.chain(
                    headers,
                    kwargs.items()
                )

        for k, v in headers:
            self[k] = v

    def copy(self):
        return Deepcopy().copy(self)

    def list(self):
        """Return all the headers as a list of headers instead of a dict"""
        return [": ".join(h) for h in self.items() if h[1]]


class Environ(Headers):
    """just like Headers but allows any values (headers converts everything to unicode
    string)"""
    def _convert_string_type(self, v):
        return v


