# -*- coding: utf-8 -*-
import re
from configparser import RawConfigParser

from .compat import *
from .string import String


class Shorten(object):
    """Converts an integer to a base58-like string and vice versa

    This code was used in Undrip for its link shortener and was originally
    written by Cahlan Sharp and Ryan Johnson (I believe) and based off of this:

        https://stackoverflow.com/a/2549514/5006

    any ambiguous characters were removed from BASE_LIST (notice no I, 1, or l)
    to make it easier for humans to copy the url by hand

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
    def encode(cls, integer, encoding="", baselist=None):
        base = cls.BASE_LIST
        length = len(base)
        ret = ''
        while integer != 0:
            ret = base[integer % length] + ret
            integer //= length
        return String(ret)

    @classmethod
    def decode(cls, s, encoding="", basedict=None):
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
            if isinstance(v, str):
                sub = True
                if base is None:
                    # NOTE: if you have an ambiguous value like "0001" or "0010" this
                    # will assume it is binary
                    if re.match(r"^[-+]?0b", v) or re.search(r"^[-+]?[01]+$", v):
                        # https://stackoverflow.com/questions/8928240/convert-base-2-binary-number-string-to-int
                        base = 2
                        sub = False

                    elif re.match(r"^[-+]?0x", v) or (re.search(r"[a-fA-F]", v) and re.search(r"[a-fA-F0-9]+$", v)):
                        base = 16
                        sub = False

                    else:
                        base = 10

                else:
                    if base != 10:
                        sub = False

                if sub:
                    subs = [
                        (" ", ""),
                        (",", ""),
                        ("K", "000"),
                        ("k", "000"),
                        ("mn", "000000"),
                        ("M", "000000"),
                        ("m", "000000"),
                        ("bn", "000000000"),
                        ("B", "000000000"),
                        ("b", "000000000"),
                    ]
                    for s in subs:
                        v = v.replace(s[0], s[1])

            try:
                v = int(v, base)

            except TypeError:
                if len(v) == 1:
                    v = ord(v)

                else:
                    raise

        return super().__new__(cls, v)


class Hex(Integer):
    def __new__(cls, v):
        return super().__new__(cls, v, 16)


class Binary(Integer):
    def __new__(cls, v):
        return super().__new__(cls, v, 2)


class Exponential(object):
    """Model exponential growth or decay over a period

    https://math.libretexts.org/Bookshelves/Applied_Mathematics/Applied_Finite_Mathematics_(Sekhon_and_Bloom)/05%3A_Exponential_and_Logarithmic_Functions/5.02%3A_Exponential_Growth_and_Decay_Models
    https://en.wikipedia.org/wiki/Exponential_decay
    """
    def __init__(self, initial, rate):
        """
        :param initial: int|float, the initial value
        :param rate: int|float, the growth rate, if an integer this will be converted
            to a float (eg, 10 would be converted to 0.1)
        """
        self.initial = initial

        if isinstance(rate, int):
            self.rate = rate / 100
        else:
            self.rate = rate

    def growth(self, period):
        """Model exponential growth over period

        :param period: int, how many periods you want to model initial and rate
        :returns: list, the values for each period
        """
        ret = []
        rate = 1.0 + self.rate
        for i in range(period):
            ret.append(self.initial * pow(rate, i))

        return ret

    def decay(self, period):
        """Model exponential decay over period

        :param period: int, how many periods you want to model initial and rate
        :returns: list, the values for each period
        """
        ret = []
        rate = 1.0 - self.rate
        for i in range(period):
            ret.append(self.initial * pow(rate, i))

        return ret


class BooleanMeta(type):
    """This class enables Boolean to quack like a boolean

    Sadly, no matter how hard I try, I don't think it is possible to get
    Boolean to pass `issubclass(Boolean, bool)` because the python C
    implementation of `issubclass` uses ->tp_mro which is what is used to
    originally set the .__mro__ attribute, but that means you can't override
    the functionality anywhere in actual python

    This metaclass isn't strictly necessary, I just find it kind of
    interesting
    """
    @property
    def __base__(self):
        return bool

    @property
    def __bases__(self):
        return (bool,) + bool.__bases__

    @property
    def __mro__(self):
        return (Boolean,) + bool.__mro__


class Boolean(int, metaclass=BooleanMeta):
    """A casting class that allows for more values to be considered True or
    False

    This differs from a normal bool(x) cast in that:

        * Any int/float > 0 will be True and any int/float <= 0 will be False,
            so negative values are False
        * Yes/no, on/off, and things like that evaluate to True/False, see

            https://github.com/python/cpython/blob/3.11/Lib/configparser.py

            RawConfigParser.BOOLEAN_STATES for what string values are True and
            False
        * A string of all whitespace is False

    This isn't a real class but is more akin to a method, the __new__ method
    returns a builtin bool instance because bool can't be subclassed:

        https://stackoverflow.com/questions/2172189/why-i-cant-extend-bool-in-python
    """
    @classmethod
    def isbool(cls, v):
        """Return True if v is considered a valid boolean-ish value"""
        try:
            cls.getbool(v)
            return True

        except TypeError:
            return False

    @classmethod
    def getbool(cls, v):
        """Try and convert v to a bool value, raise TypeError on failure"""
        if not isinstance(v, bool):
            if isinstance(v, (int, float)):
                v = True if v > 0 else False

            elif isinstance(v, str):
                k = v.lower()
                if k in RawConfigParser.BOOLEAN_STATES:
                    v = RawConfigParser.BOOLEAN_STATES[k]

                else:
                    if k.isdigit():
                        v = True if int(v) > 0 else False

                    else:
                        if k == "t":
                            v = True

                        elif k == "f":
                            v = False

                        else:
                            raise TypeError(f"{k} is not a bool")

        return v

    def __new__(cls, v):
        try:
            v = cls.getbool(v)

        except TypeError:
            if isinstance(v, str):
                v = True if v.strip() else False

            else:
                raise

        return bool(v)

