# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import base64
import hashlib
import re
import string
import binascii
import unicodedata

from . import environ
from .compat import *


class ByteString(Bytes):
    """Wrapper around a byte string b"" to make sure we have a byte string that
    will work across python versions and handle the most annoying encoding issues
    automatically

    We treat integers like how py2.7 treats them because this is a Byte STRING and
    not just bytes, so it makes sense to return b'10' instead of 10 \x00 bytes

    :Example:
        # python 3
        s = ByteString("foo)
        str(s) # calls __str__ and returns self.unicode()
        unicode(s) # errors out
        bytes(s) # calls __bytes__ and returns ByteString
        # python 2
        s = ByteString("foo)
        str(s) # calls __str__ and returns ByteString
        unicode(s) # calls __unicode__ and returns String
        bytes(s) # calls __str__ and returns ByteString
    """
    def __new__(cls, val=b"", encoding="", errors=""):
        """
        :param val: mixed, the value you are casting to bytes
        :param encoding: string, the string encoding to use to encode/decode
        :param errors: string, how to handle errors, built-in values are:
            strict,
            ignore,
            replace,
            xmlcharrefreplace,
            backslashreplace
        """
        if isinstance(val, type(None)):
            # we do 3+ functionality even in 2.7
            if is_py2:
                raise TypeError("cannot convert 'NoneType' object to bytes")
            else:
                val = Bytes(val)

        if not encoding:
            encoding = environ.ENCODING

        if not errors:
            errors = environ.ENCODING_ERRORS

        if not isinstance(val, (bytes, bytearray)):
            if is_py2:
                val = unicode(val)
            else:
                val = str(val)
            #val = val.__str__()
            val = bytearray(val, encoding)

        instance = super(ByteString, cls).__new__(cls, val)
        instance.encoding = encoding
        instance.errors = errors
        return instance

    def __str__(self):
        return self if is_py2 else self.unicode()

    def unicode(self):
        s = self.decode(self.encoding, self.errors)
        return String(s, self.encoding, self.errors)
    __unicode__ = unicode

    def bytes(self):
        return self
    __bytes__ = bytes

    def raw(self):
        """because sometimes you need a vanilla bytes()"""
        return b"" + self

    def md5(self):
        """32 character md5 hash of string"""
        # http://stackoverflow.com/a/5297483/5006
        return hashlib.md5(self).hexdigest()

    def sha256(self):
        """64 character sh256 hash of the string"""
        return hashlib.sha256(self).hexdigest()


class String(Str):
    """Wrapper around a unicode string "" to make sure we have a unicode string that
    will work across python versions and handle the most annoying encoding issues
    automatically
    :Example:
        # python 3
        s = String("foo)
        str(s) # calls __str__ and returns String
        unicode(s) # errors out
        bytes(s) # calls __bytes__ and returns ByteString
        # python 2
        s = String("foo)
        str(s) # calls __str__ and returns ByteString
        unicode(s) # calls __unicode__ and returns String
        bytes(s) # calls __str__ and returns ByteString

    https://en.wikipedia.org/wiki/Base64
    """

    # constants from string module https://docs.python.org/3/library/string.html
    ASCII_LETTERS = string.ascii_letters
    ASCII_LOWERCASE = string.ascii_lowercase
    ASCII_UPPERCASE = string.ascii_uppercase
    DIGITS = string.digits
    HEXDIGITS = string.hexdigits
    OCTDIGITS = string.octdigits
    PUNCTUATION = string.punctuation
    PRINTABLE = string.printable
    WHITESPACE = string.whitespace

    def __new__(cls, val="", encoding="", errors=""):
        """
        :param val: mixed, the value you are casting to a string
        :param encoding: string, the string encoding to use to encode/decode
        :param errors: string, how to handle errors, built-in values are:
            strict,
            ignore,
            replace,
            xmlcharrefreplace,
            backslashreplace
        """
        if isinstance(val, type(None)):
            val = Str(val)

        if not encoding:
            encoding = environ.ENCODING

        if not errors:
            errors = environ.ENCODING_ERRORS

        if not isinstance(val, (Str, int)):
            val = ByteString(val, encoding, errors).unicode()

        instance = super(String, cls).__new__(cls, val)
        instance.encoding = encoding
        instance.errors = errors
        return instance

    def __str__(self):
        return self.bytes() if is_py2 else self

    def unicode(self):
        return self
    __unicode__ = unicode

    def bytes(self):
        s = self.encode(self.encoding)
        return ByteString(s, self.encoding, self.errors)
    __bytes__ = bytes

    def raw(self):
        """because sometimes you need a vanilla str() (or unicode() in py2)"""
        return "" + self

    def md5(self):
        """32 character md5 hash of string"""
        # http://stackoverflow.com/a/5297483/5006
        return hashlib.md5(self.bytes()).hexdigest()

    def sha256(self):
        """64 character sh256 hash of the string"""
        return hashlib.sha256(self.bytes()).hexdigest()

    def hash(self, key, name="sha256", nonce="", rounds=100000):
        """hash self with key and return the 64 byte hash

        This will produce the same hash if given the same key, it is designed to
        hash values with a dedicated key (password) and always produce the same
        hashed value if the same key (password) is always used.

        IMPORTANT In order to have the same value the same value, key, name, and
        nonce needs to be used, if you change any of these values then the hashes
        will no longer be equivalent

        :param key: string, the key/salt/password for the hash
        :param name: string, the hash to use, not required
        :param nonce: string, the nonce to use for the value, not required
        :param rounds: int, the number of rounds to hash
        :returns: string, 64 byte hex string
        """
        nonce = ByteString(nonce) if nonce else b""

        # do the actual hashing
        h = hashlib.pbkdf2_hmac(
            name,
            nonce + self.bytes(),
            String(key).bytes(), # we cast to string first, then bytes, in case key is an int
            rounds
        )
        r = binascii.hexlify(h) # convert hash to easier to consume hex
        return String(r)

    def truncate(self, size, postfix='...'):
        """similar to a normal string slice but it actually will split on a word boundary

        :Example:
            s = "foo barche"
            print s[0:5] # "foo b"
            s2 = String(s)
            print s2.truncate(5) # "foo"

        truncate a string by word breaks instead of just length
        this will guarrantee that the string is not longer than length, but it could be shorter

        http://stackoverflow.com/questions/250357/smart-truncate-in-python/250373#250373

        This was originally a method called word_truncate by Cahlan Sharp for Undrip

        :param size: int, the size you want to truncate to at max
        :param postfix: string, what you would like to be appended to the truncated
            string
        :returns: string, a new string, truncated
        """
        if len(self) < size: return self

        # our algo is pretty easy here, it truncates the string to size - postfix size
        # then right splits the string on any whitespace for a maximum of one time
        # and returns the first item of that split right stripped of whitespace
        # (just in case)
        postfix = type(self)(postfix)
        ret = self[0:size - len(postfix)]
        # if rsplit sep is None, any whitespace string is a separator
        ret = ret[:-1].rsplit(None, 1)[0].rstrip()
        return type(self)(ret + postfix)

    def indent(self, indent, count=1):
        """add whitespace to the beginning of each line of val

        http://code.activestate.com/recipes/66055-changing-the-indentation-of-a-multi-line-string/

        :param indent: string, what you want the prefix of each line to be
        :param count: int, how many times to apply indent to each line
        :returns: string, string with prefix at the beginning of each line
        """
        if not indent: return self

        s = ((indent * count) + line for line in self.splitlines(False))
        s = "\n".join(s)
        return type(self)(s)

    def stripall(self, chars):
        """Similar to the builtin .strip() but will strip chars from anywhere in the
        string

        :Example:
            s = "foo bar che.  "
            s2 = s.stripall(" .")
            print(s2) # "foobarche"
        """
        ret = ""
        for ch in self:
            if ch not in chars:
                ret += ch
        return ret

    def astrip(self, chars):
        return self.stripall(chars)

    def re(self, pattern, flags=0):
        """Provides a fluid regex interface

        :Example:
            s = 'foo##bar##che'
            parts = s.re(r'#+').split()
            print(parts) # ['foo', 'bar', 'che']
        """
        return Regex(pattern, self, flags)

    def regex(self, pattern, flags=0):
        return self.re(pattern, flags)

    def ispunc(self):
        """Returns True if all characters in string are punctuation characters"""
        for ch in self:
            if ch not in string.punctuation:
                return False
        return True

    def ispunctuation(self):
        return self.ispunc()

    def capwords(self, sep=None):
        """passthrough for string module capwords

        https://docs.python.org/3/library/string.html#string.capwords
        """
        return String(string.capwords(self, sep=sep))

    def isascii(self):
        """Return True if the string is empty or all characters in the string are
        ASCII, False otherwise.

        ASCII characters have code points in the range U+0000-U+007F.

        https://docs.python.org/3/library/stdtypes.html#str.isascii
        """
        try:
            ret = super(String, self).isascii()

        except AttributeError:
            ret = True
            a = Ascii()
            for ch in self:
                if ch not in a:
                    ret = False
                    break

        return ret


class Character(String):
    @property
    def hexes(self):
        return [cp.hex for cp in self.codepoints]

    @property
    def hex(self):
        return self.unified("")

    @classmethod
    def normalize(cls, v, encoding, errors):
        codepoints = []

        if isinstance(v, bytes):
            v = v.decode(encoding, errors)

        if isinstance(v, basestring):
            if re.search(r"&[a-zA-Z0-9]{2,};?", v):
                # https://en.wikipedia.org/wiki/Character_encodings_in_HTML
                # we have a string that contains something like &ZZZZ;
                v = html.unescape(v)

            if re.match(r"^(?:[uU]\+)?[a-fA-F0-9]{4,}(?:[\s_-](?:[uU]\+)?[a-fA-F0-9]{4,})*$", v):
                # split strings like ZZZZ-ZZZZ-ZZZZ or U+ZZZZ u+zzzz etc.
                codepoints = re.split(r"[\s_-]+", v)

            else:
                # we have actual unicode codepoints (eg, sequence of \UZZZZZZZZ or \uZZZZ)
                codepoints = v

        elif isinstance(v, (list, tuple, Sequence)):
            for cp in v:
                codepoints.extend(cls.normalize(cp, encoding, errors))

        else:
            codepoints = [v]

        return codepoints

    def __new__(cls, v, encoding="", errors=""):
        if not encoding:
            encoding = environ.ENCODING

        if not errors:
            errors = environ.ENCODING_ERRORS

        codepoints = [Codepoint(cp, encoding, errors) for cp in cls.normalize(v, encoding, errors)]

        instance = super(Character, cls).__new__(cls, "".join(codepoints), encoding, errors)
        instance.codepoints = codepoints
        return instance

    def unified(self, separator=" "):
        """return the unified codepoints joined by separator

        this is just a handy way to get the codepoints with some separator, name
        comes from emojitracker

        https://medium.com/@mroth/how-i-built-emojitracker-179cfd8238ac

        :param separator: string, usually space or dash
        :returns: string, the codepoints joined by separator
        """
        cps = []
        for cp in self.codepoints:
            cps.append(cp.hex)
        return separator.join(cps)
    ligature = unified

    def graphemes(self):
        return self.codepoints

    def names(self):
        names = []
        for cp in self.codepoints:
            names.append(unicodedata.name(cp, 'UNKNOWN'))
        return names

    def __repr__(self):
        return "{} ({})".format(self, self.hex)

    def integers(self):
        """Return the codepoints as integers"""
        return list(map(int, self.codepoints))

    def __iter__(self):
        for cp in self.codepoints:
            yield cp

    def repr_string(self):
        ret = ""
        for cp in self.codepoints:
            if len(cp.hex) <= 4:
                ret += '\\u{}'.format(cp.hex)
            else:
                ret += '\\U{}'.format(cp.hex)
        return ret

    def repr_bytes(self):
        ret = ""
        if is_py2:
            for cp in self.encode(self.encoding):
                ret += "\\x{:0>2x}".format(ord(cp))

        else:
            # and to think I thought I was starting to understand unicode!
            # https://stackoverflow.com/a/54549874/5006
            s = self.encode("utf-16", "surrogatepass").decode("utf-16")
            for cp in s.encode(self.encoding):
                ret += "\\x{:0>2x}".format(cp)

        return ret

    def width(self):
        return sum(cp.width() for cp in self.codepoints)

    def __len__(self):
        return self.width()

    def eawidth(self):
        """Return the east asian width of the character

        In a broad sense, wide characters include W, F, and A (when in East Asian context),
        and narrow characters include N, Na, H, and A (when not in East Asian context)

        http://www.unicode.org/reports/tr11/tr11-36.html
        http://www.unicode.org/Public/UNIDATA/EastAsianWidth.txt

        :returns: string, a wide character: W, F, A or narrow char: N, Na, H, A
        """
        # https://docs.python.org/3/library/unicodedata.html#unicodedata.east_asian_width
        return unicodedata.east_asian_width(self)


class Codepoint(String):
    """Grapheme - a grapheme is the smallest unit of a writing system of any given language

    https://en.wikipedia.org/wiki/Grapheme
    https://docs.python.org/3/howto/unicode.html
    """
    def __new__(cls, codepoint, encoding="", errors=""):

        if not encoding:
            encoding = environ.ENCODING

        if not errors:
            errors = environ.ENCODING_ERRORS

        if isinstance(codepoint, bytes):
            codepoint = codepoint.decode(encoding, errors)

        elif isinstance(codepoint, int):
            if codepoint < 256:
                codepoint = chr(codepoint)

            else:
                codepoint = '{:X}'.format(codepoint)

        if "&" in codepoint:
            # we have a string like &ZZZZ;
            codepoint = html.unescape(codepoint)

        elif re.match(r"^[Uu]\+[a-fA-F0-9]+$", codepoint):
            # we have a string like U+ZZZZ or u+ZZZZ
            codepoint = codepoint.replace("U+", "").replace("u+", "")

        if len(codepoint) == 1:
            s = codepoint
            h = "{:0>4X}".format(ord(codepoint))

        elif len(codepoint) <= 4:
            s = '\\u{:0>4X}'.format(int(codepoint, 16)).encode(encoding).decode('unicode-escape')
            h = '{:0>4X}'.format(int(codepoint, 16)).upper()

        elif len(codepoint) <= 8:
            s = "\\U{:0>8x}".format(int(codepoint, 16)).encode(encoding).decode('unicode-escape')
            h = '{:0>4x}'.format(int(codepoint, 16)).upper()

        else:
            raise ValueError("codepoint is bigger than 8")

        instance = super(Codepoint, cls).__new__(cls, s)
        instance.hex = h
        return instance

    def __int__(self):
        return int(self.hex, 16)

    def is_wide(self):
        """Is this a wide unicode codepoint? A wide ucs4 codepoint is greater than
        4 hex digits"""
        return not self.is_narrow()

    def is_narrow(self):
        """is this a narrow unicode codepoint? A narrow ucs2 codepoint is 4 or less
        hex digits"""
        return int(self) <= 65535

    def repr_string(self):
        ret = ""
        if len(self.hex) <= 4:
            ret += '\\u{}'.format(self.hex)
        else:
            ret += '\\U{}'.format(self.hex)
        return ret

    def repr_bytes(self):
        ret = ""
        for cp in self.encode(self.encoding):
            ret += "\\x{:0>2x}".format(ord(cp))
        return ret

    def width(self):
        """A naive simple unicode width method based off of:

            https://www.cl.cam.ac.uk/~mgk25/ucs/wcwidth.c

        if you need a more intelligent solution, this SO has suggestions:

            https://stackoverflow.com/questions/30881811/how-do-you-get-the-display-width-of-combined-unicode-characters-in-python-3

        This is a really good summary of the rules for determining width:

            https://stackoverflow.com/a/9145712/5006

        search:
            * python find out width of unicode characters
            * get width of unicode character

        :returns: int, the width of the character
        """
        ucs = int(self)

        combining = [
            [ 0x0300, 0x036F ], [ 0x0483, 0x0486 ], [ 0x0488, 0x0489 ],
            [ 0x0591, 0x05BD ], [ 0x05BF, 0x05BF ], [ 0x05C1, 0x05C2 ],
            [ 0x05C4, 0x05C5 ], [ 0x05C7, 0x05C7 ], [ 0x0600, 0x0603 ],
            [ 0x0610, 0x0615 ], [ 0x064B, 0x065E ], [ 0x0670, 0x0670 ],
            [ 0x06D6, 0x06E4 ], [ 0x06E7, 0x06E8 ], [ 0x06EA, 0x06ED ],
            [ 0x070F, 0x070F ], [ 0x0711, 0x0711 ], [ 0x0730, 0x074A ],
            [ 0x07A6, 0x07B0 ], [ 0x07EB, 0x07F3 ], [ 0x0901, 0x0902 ],
            [ 0x093C, 0x093C ], [ 0x0941, 0x0948 ], [ 0x094D, 0x094D ],
            [ 0x0951, 0x0954 ], [ 0x0962, 0x0963 ], [ 0x0981, 0x0981 ],
            [ 0x09BC, 0x09BC ], [ 0x09C1, 0x09C4 ], [ 0x09CD, 0x09CD ],
            [ 0x09E2, 0x09E3 ], [ 0x0A01, 0x0A02 ], [ 0x0A3C, 0x0A3C ],
            [ 0x0A41, 0x0A42 ], [ 0x0A47, 0x0A48 ], [ 0x0A4B, 0x0A4D ],
            [ 0x0A70, 0x0A71 ], [ 0x0A81, 0x0A82 ], [ 0x0ABC, 0x0ABC ],
            [ 0x0AC1, 0x0AC5 ], [ 0x0AC7, 0x0AC8 ], [ 0x0ACD, 0x0ACD ],
            [ 0x0AE2, 0x0AE3 ], [ 0x0B01, 0x0B01 ], [ 0x0B3C, 0x0B3C ],
            [ 0x0B3F, 0x0B3F ], [ 0x0B41, 0x0B43 ], [ 0x0B4D, 0x0B4D ],
            [ 0x0B56, 0x0B56 ], [ 0x0B82, 0x0B82 ], [ 0x0BC0, 0x0BC0 ],
            [ 0x0BCD, 0x0BCD ], [ 0x0C3E, 0x0C40 ], [ 0x0C46, 0x0C48 ],
            [ 0x0C4A, 0x0C4D ], [ 0x0C55, 0x0C56 ], [ 0x0CBC, 0x0CBC ],
            [ 0x0CBF, 0x0CBF ], [ 0x0CC6, 0x0CC6 ], [ 0x0CCC, 0x0CCD ],
            [ 0x0CE2, 0x0CE3 ], [ 0x0D41, 0x0D43 ], [ 0x0D4D, 0x0D4D ],
            [ 0x0DCA, 0x0DCA ], [ 0x0DD2, 0x0DD4 ], [ 0x0DD6, 0x0DD6 ],
            [ 0x0E31, 0x0E31 ], [ 0x0E34, 0x0E3A ], [ 0x0E47, 0x0E4E ],
            [ 0x0EB1, 0x0EB1 ], [ 0x0EB4, 0x0EB9 ], [ 0x0EBB, 0x0EBC ],
            [ 0x0EC8, 0x0ECD ], [ 0x0F18, 0x0F19 ], [ 0x0F35, 0x0F35 ],
            [ 0x0F37, 0x0F37 ], [ 0x0F39, 0x0F39 ], [ 0x0F71, 0x0F7E ],
            [ 0x0F80, 0x0F84 ], [ 0x0F86, 0x0F87 ], [ 0x0F90, 0x0F97 ],
            [ 0x0F99, 0x0FBC ], [ 0x0FC6, 0x0FC6 ], [ 0x102D, 0x1030 ],
            [ 0x1032, 0x1032 ], [ 0x1036, 0x1037 ], [ 0x1039, 0x1039 ],
            [ 0x1058, 0x1059 ], [ 0x1160, 0x11FF ], [ 0x135F, 0x135F ],
            [ 0x1712, 0x1714 ], [ 0x1732, 0x1734 ], [ 0x1752, 0x1753 ],
            [ 0x1772, 0x1773 ], [ 0x17B4, 0x17B5 ], [ 0x17B7, 0x17BD ],
            [ 0x17C6, 0x17C6 ], [ 0x17C9, 0x17D3 ], [ 0x17DD, 0x17DD ],
            [ 0x180B, 0x180D ], [ 0x18A9, 0x18A9 ], [ 0x1920, 0x1922 ],
            [ 0x1927, 0x1928 ], [ 0x1932, 0x1932 ], [ 0x1939, 0x193B ],
            [ 0x1A17, 0x1A18 ], [ 0x1B00, 0x1B03 ], [ 0x1B34, 0x1B34 ],
            [ 0x1B36, 0x1B3A ], [ 0x1B3C, 0x1B3C ], [ 0x1B42, 0x1B42 ],
            [ 0x1B6B, 0x1B73 ], [ 0x1DC0, 0x1DCA ], [ 0x1DFE, 0x1DFF ],
            [ 0x200B, 0x200F ], [ 0x202A, 0x202E ], [ 0x2060, 0x2063 ],
            [ 0x206A, 0x206F ], [ 0x20D0, 0x20EF ], [ 0x302A, 0x302F ],
            [ 0x3099, 0x309A ], [ 0xA806, 0xA806 ], [ 0xA80B, 0xA80B ],
            [ 0xA825, 0xA826 ], [ 0xFB1E, 0xFB1E ], [ 0xFE00, 0xFE0F ],
            [ 0xFE20, 0xFE23 ], [ 0xFEFF, 0xFEFF ], [ 0xFFF9, 0xFFFB ],
            [ 0x10A01, 0x10A03 ], [ 0x10A05, 0x10A06 ], [ 0x10A0C, 0x10A0F ],
            [ 0x10A38, 0x10A3A ], [ 0x10A3F, 0x10A3F ], [ 0x1D167, 0x1D169 ],
            [ 0x1D173, 0x1D182 ], [ 0x1D185, 0x1D18B ], [ 0x1D1AA, 0x1D1AD ],
            [ 0x1D242, 0x1D244 ], [ 0xE0001, 0xE0001 ], [ 0xE0020, 0xE007F ],
            [ 0xE0100, 0xE01EF ]
        ]

        # test for 8-bit control characters
        if ucs == 0:
            return 0

        if (ucs < 32) or (ucs >= 0x7f and ucs < 0xa0):
            return -1

        # search in table of non-spacing characters
        for start, stop in combining:
            if start <= ucs and ucs <= stop:
                return 0

        # if we arrive here, ucs is not a combining or C0/C1 control character

        return 1 + (ucs >= 0x1100 and
            (ucs <= 0x115f or                    # Hangul Jamo init. consonants
            ucs == 0x2329 or ucs == 0x232a or
            (ucs >= 0x2e80 and ucs <= 0xa4cf and
            ucs != 0x303f) or                  # CJK ... Yi
            (ucs >= 0xac00 and ucs <= 0xd7a3) or # Hangul Syllables
            (ucs >= 0xf900 and ucs <= 0xfaff) or # CJK Compatibility Ideographs
            (ucs >= 0xfe10 and ucs <= 0xfe19) or # Vertical forms
            (ucs >= 0xfe30 and ucs <= 0xfe6f) or # CJK Compatibility Forms
            (ucs >= 0xff00 and ucs <= 0xff60) or # Fullwidth Forms
            (ucs >= 0xffe0 and ucs <= 0xffe6) or
            (ucs >= 0x20000 and ucs <= 0x2fffd) or
            (ucs >= 0x30000 and ucs <= 0x3fffd)))


class Regex(object):
    """Provides a passthrough interface to the re module to run pattern against s

    https://docs.python.org/3/library/re.html
    """
    def __init__(self, pattern, s, flags=0):
        self.pattern = pattern
        self.s = s
        self.flags = flags

    def search(self, flags=0):
        flags |= self.flags
        return re.search(self.pattern, self.s, flags)

    def match(self, flags=0):
        flags |= self.flags
        return re.match(self.pattern, self.s, flags)

    def fullmatch(self, flags=0):
        flags |= self.flags
        return re.fullmatch(self.pattern, self.s, flags)

    def split(self, maxsplit=0, flags=0):
        flags |= self.flags
        return re.split(self.pattern, self.s, maxsplit=maxsplit, flags=flags)

    def findall(self, flags=0):
        flags |= self.flags
        return re.findall(self.pattern, self.s, flags=flags)

    def finditer(self, flags=0):
        flags |= self.flags
        return re.finditer(self.pattern, self.s, flags=flags)

    def sub(self, repl, count=0, flags=0):
        flags |= self.flags
        return re.sub(self.pattern, repl, self.s, count=count, flags=flags)

    def subn(self, repl, count=0, flags=0):
        flags |= self.flags
        return re.subn(self.pattern, repl, self.s, count=count, flags=flags)


class Base64(String):
    """This exists to normalize base64 encoding between py2 and py3, it assures that
    you always get back a unicode string when you encode or decode and that you can
    pass in a unicode or byte string and it just works
    """
    @classmethod
    def encode(cls, s, encoding=""):
        """converts a plain text string to base64 encoding
        :param s: unicode str|bytes, the base64 encoded string
        :returns: unicode str
        """
        b = ByteString(s, encoding=encoding)
        be = base64.b64encode(b).strip()
        return String(be)

    @classmethod
    def decode(cls, s, encoding=""):
        """decodes a base64 string to plain text
        :param s: unicode str|bytes, the base64 encoded string
        :returns: unicode str
        """
        b = ByteString(s)
        bd = base64.b64decode(b)
        return String(bd, encoding=encoding)


class HTMLCleaner(HTMLParser):
    """strip html tags from a string

    :example:
        html = "this is <b>some html</b>
        text = HTMLCleaner.strip_tags(html)
        print(text) # this is some html

    http://stackoverflow.com/a/925630/5006
    https://docs.python.org/2/library/htmlparser.html
    """
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Block-level_elements
    BLOCK_TAGNAMES = set([
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "canvas",
        "dd",
        "div",
        "dl",
        "fieldset", 
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header", 
        "hgroup", 
        "hr",
        "li",
        "main",
        "nav",
        "noscript",
        "ol",
        "output",
        "p",
        "pre",
        "section",
        "table",
        "tfoot",
        "ul",
        "video",
    ])

    @classmethod
    def strip_tags(cls, html, *args, **kwargs):
        s = cls(*args, **kwargs)
        # convert entities back otherwise stripper will get rid of them
        # http://stackoverflow.com/a/28827374/5006
        #html = s.unescape(html)
        s.feed(html)
        return s.get_data()

    def __init__(self, block_sep="\n", inline_sep="", keep_img_src=False):
        """create an instance and configure it

        :param block_sep: string, strip a block tag and then add this to the end of the
            stripped tag, so if you have <p>foo bar<p> and block_sep=\n, then the stripped
            string would be foo bar\n
        :param inline_sep: string, same as block_sep, but gets added to the end of the
            stripped inline tag
        :param keep_img_src: boolean, if True, the img.src attribute will replace the <img />
            tag
        """
        self.fed = []
        self.block_sep = block_sep
        self.inline_sep = inline_sep
        self.keep_img_src = keep_img_src

        if is_py2:
            HTMLParser.__init__(self)
        else:
            #self.reset()
            super(HTMLCleaner, self).__init__()

    def handle_data(self, d):
        self.fed.append(d)

    def handle_entityref(self, name):
        self.fed.append("&{};".format(name))

    def handle_starttag(self, tag, attrs):
        # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
        if tag == "img" and self.keep_img_src:
            for attr_name, attr_val in attrs:
                if attr_name == "src":
                    self.fed.append("\n{}\n".format(attr_val))

    def handle_endtag(self, tagname):
        if tagname in self.BLOCK_TAGNAMES:
            if self.block_sep:
                self.fed.append(self.block_sep)
        else:
            if self.inline_sep:
                self.fed.append(self.inline_sep)

    def get_data(self):
        return self.unescape("".join(self.fed))

    @classmethod
    def unescape(cls, s):
        """unescapes html entities (eg, &gt;) to plain text (eg, &gt; becomes >)"""
        # https://stackoverflow.com/a/2087433/5006
        return html.unescape(s)


class Ascii(String):
    """This is just a convenience class so I can get all punctuation characters, 
    but I added other methods in case I need to use this somewhere else"""
    def __new__(cls):
        s = list(chr(x) for x in range(0x00, 0x7F + 1))
        instance = super(Ascii, cls).__new__(cls, s)
        return instance

    def punctuation(self):
        """Return all the ascii punctuation characters"""
        ret = []
        for x in range(0x00, 0x7F + 1): # 0-127
            if x == 96: continue
            if x == 26: continue

            s = chr(x)
            if s.isprintable() and not s.isspace() and not s.isalnum():
                ret.append(s)

        return "".join(ret)

    def alpha(self):
        """Return upper and lower case letters"""
        ret = []
        for x in range(0x00, 0x7F + 1): # 0-127
            s = chr(x)
            if s.isalpha():
            #if s.isalnum():
                ret.append(s)

        return "".join(ret)

    def num(self):
        """Return numbers 0-9"""
        ret = []
        for x in range(0x00, 0x7F + 1): # 0-127
            s = chr(x)
            if s.isnumeric():
            #if s.isalnum():
                ret.append(s)

        return "".join(ret)

    def numeric(self):
        return self.num()

    def alnum(self):
        """Return letters and numbers only"""
        ret = [c for c in self.alpha()]
        ret.update(c for c in self.num())
        return ret

    def alphanumeric(self):
        return self.alnum()

    def alphanum(self):
        return self.alnum()

