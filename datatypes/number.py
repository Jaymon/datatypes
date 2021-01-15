# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import re

from .compat import *
from .string import String


class Shorten(object):
    """Converts an integer to a base58-like string and vice versa

    This code was used in Undrip for its link shortener and was originally written
    by Cahlan Sharp and Ryan Johnson (I believe) and based off of this:

        https://stackoverflow.com/a/2549514/5006

    any ambiguous characters were removed from BASE_LIST (notice no I, 1, or l) to
    make it easier for humans to copy the url by hand

    this is a version of base58 that takes strings:
        https://github.com/keis/base58
    """
    BASE_LIST = '23456789' + 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ' + '_-'
    BASE_DICT = dict((c, i) for i, c in enumerate(BASE_LIST))

    def __new__(cls, val):
        if isinstance(val, basestring):
            ret = cls.decode(val)

        elif isinstance(val, int):
            ret = cls.encode(val)

        else:
            raise TypeError("Unknown type {}".format(type(val)))

        return ret

    @classmethod
    def encode(cls, integer, encoding=""):
        base = cls.BASE_LIST
        length = len(base)
        ret = ''
        while integer != 0:
            ret = base[integer % length] + ret
            integer //= length
        return String(ret)

    @classmethod
    def decode(cls, s, encoding=""):
        reverse_base = cls.BASE_DICT
        length = len(reverse_base)
        ret = 0
        for i, c in enumerate(s[::-1]):
            ret += (length ** i) * reverse_base[c]
        return ret


class Integer(int):
    def hex(self, length=0, prefix=""):
        format_str = "{}{{:0>{}X}}".format(prefix, length) if length else "{}{{:X}}".format(prefix)
        return format_str.format(self)

    def binary(self, length=0, prefix=""):
        format_str = "{}{{:0>{}b}}".format(prefix, length) if length else "{}{{:b}}".format(prefix)
        return format_str.format(self)

    def range(self, start=0):
        """iterate from 0 to self, if self is negative it goes from self to 0

        I honestly have no idea why this is useful but it was in my notes for this
        module, so here it is
        """
        if self > start:
            r = range(0, self)
        else:
            r = range(self, start)

        for i in r:
            yield i

    def __new__(cls, v, base=None):
        if not isinstance(v, int):
            if base is None and isinstance(v, basestring):
                # NOTE: if you have an ambiguous value like "0001" or "0010" this
                # will assume it is binary
                if re.match(r"^[-+]?0b", v) or re.search(r"[01]+$", v):
                    # https://stackoverflow.com/questions/8928240/convert-base-2-binary-number-string-to-int
                    base = 2

                elif re.match(r"^[-+]?0x", v) or re.search(r"[a-fA-F0-9]+$", v):
                    base = 16

            v = int(v, base)

        return super(Integer, cls).__new__(cls, v)


class Hex(Integer):
    def __new__(cls, v):
        return super(Hex, cls).__new__(cls, v, 16)


class Binary(Integer):
    def __new__(cls, v):
        return super(Binary, cls).__new__(cls, v, 2)

