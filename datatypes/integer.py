# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from .compat import *
from .string import String


class Shorten(object):
    """Converts an integer to a base58-like string and vice versa

    This code was used in Undrip for its link shortener and was originally written
    by Cahlan Sharp and Ryan Johnson (I believe) and based off of this:

        https://stackoverflow.com/a/2549514/5006

    any ambiguous characters were removed from BASE_LIST (notice no I, 1, or l) to
    make it easier for humans to copy the url by hand

    this is a version of base68 that takes strings:
        https://github.com/keis/base58
    """
    BASE_LIST = '23456789' + 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ' + '_'
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
    def __iter__(self):
        """iterate from 0 to self, if self is negative it goes from self to 0

        I honestly have no idea why this is useful but it was in my notes for this
        module, so here it is
        """
        if self > 0:
            r = range(0, self)
        else:
            r = range(self, 0)

        for i in r:
            yield i

