# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import base64
import hashlib
import re
import string
import binascii
import unicodedata
from distutils.fancy_getopt import wrap_text

from . import environ
from .compat import *
from .compat import HTMLParser as BaseHTMLParser
from .utils import make_list


class StringMixin(object):
    def chunk(self, chunk_size):
        """Return chunk_size chunks of the string until it is exhausted

        :param chunk_size: int, the size of the chunk
        :returns: generator, yields chunks of the string until the end
        """
        if chunk_size:
            start = 0
            total = len(self)
            while start < total:
                yield self[start:start + chunk_size]
                start += chunk_size

        else:
            yield self


class ByteString(Bytes, StringMixin):
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


class String(Str, StringMixin):
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

    ASCII_VOWELS_LOWERCASE = "aeiou"
    ASCII_VOWELS_UPPERCASE = "AEIOU"
    ASCII_VOWELS = ASCII_VOWELS_LOWERCASE + ASCII_VOWELS_UPPERCASE

    ASCII_CONSONANTS_LOWERCASE = "bcdfghjklmnpqrstvwxyz"
    ASCII_CONSONANTS_UPPERCASE = "BCDFGHJKLMNPQRSTVWXYZ"
    ASCII_CONSONANTS = ASCII_CONSONANTS_LOWERCASE + ASCII_CONSONANTS_UPPERCASE

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

        s = ((indent * count) + line for line in self.splitlines(True))
        s = "".join(s)
        return type(self)(s)

    def wrap(self, size):
        """Wraps text to less than width wide

        https://docs.python.org/3/distutils/apiref.html#distutils.fancy_getopt.wrap_text

        :param size: int, the width you want
        :returns: str, all text wrapped to no more than size, if there isn't a space
            or linebreak then the middle of the word will get broken on
        """
        s = "\n".join(wrap_text(self, size))
        return type(self)(s)

    def stripall(self, chars):
        """Similar to the builtin .strip() but will strip chars from anywhere in the
        string

        :Example:
            s = "foo bar che.  "
            s2 = s.stripall(" .")
            print(s2) # "foobarche"

        :param chars: str|callable, either the characters to strip, or a callback
            that takes a character and returns True if that character should be stripped
        """
        ret = ""
        if callable(chars):
            for ch in self:
                if not chars(ch):
                    ret += ch

        else:
            for ch in self:
                if ch not in chars:
                    ret += ch

        return type(self)(ret)

    def astrip(self, chars):
        """alias of .stripall"""
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

        Split the argument into words using str.split(), capitalize each word using
        str.capitalize(), and join the capitalized words using str.join(). If the
        optional second argument sep is absent or None, runs of whitespace
        characters are replaced by a single space and leading and trailing whitespace
        are removed, otherwise sep is used to split and join the words.

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

    def tokenize(self, delims=None, tokenizer_class=None):
        """Wraps the tokenizer functionality to easily tokenize a string

        :param delims: same as token.Tokenizer delims argument
        :param tokenizer_class: Tokenizer, custom class for customized functionality
        :returns: generator of String instance, each token that will also have a 
            .token that contains the raw token
        """
        if not tokenizer_class:
            from .token import Tokenizer # avoid circular dep
            tokenizer_class = Tokenizer

        tokenizer = tokenizer_class(self, delims)
        for t in tokenizer:
            st = String(t.text)
            st.token = t
            yield st

    def xmlescape(self):
        """Perform xml/html escaping (eg, & becomes &amp;) of the current string

        :returns: string, the same string but XML escaped
        """
        from xml.sax.saxutils import escape
        return escape(self, entities={
            "'": "&apos;",
            "\"": "&quot;"
        })


class NamingConvention(String):
    """Class that makes it easy to handle the different types of names that can
    be defined and passed in.

    For example, python convention for variables is snake case (lower case with
    underscores between words: foo_bar), but class names are camel case (title case
    words scrunched together: FooBar) and you would want to pass in values on the
    commandline using dashes, so this class makes it easy to go from `foo-bar`
    to `foo_bar` to `FooBar`

    Moved here from Captain.reflection.Name on 12-19-2022, also moved all the case
    methods from String into here

    https://en.wikipedia.org/wiki/Naming_convention_(programming)
    """
    def splitcamel(self):
        """Split self on camel casing boundaries (capital letters)

        :Example:
            NamingConvention("FooBar").splitcamel() # ["Foo", "Bar"]

        :returns: list, a list of parts
        """
        # https://stackoverflow.com/a/37697078/5006
        return re.sub('([A-Z][a-z]+)', r' \1', re.sub('([A-Z]+)', r' \1', self)).split()

    def splitdash(self):
        """Split self on dashes

        :Example:
            NamingConvention("foo-bar").splitdash() # ["foo", "bar"]

        :returns: list, a list of parts
        """
        return self.split("-")

    def splitunderscore(self):
        """Split self on underscores

        :Example:
            NamingConvention("foo_bar").splitunderscore() # ["foo", "bar"]

        :returns: list, a list of parts
        """
        return self.split("_")

    def split(self, *args, **kwargs):
        """Overrides the normal string split to also split on camelcasing, dashes,
        or underscores. If you pass in a value then it will act like the normal
        split
        """
        if args or kwargs:
            ret = super().split(*args, **kwargs)

        else:
            ret = []
            for p in re.split(r"[\s_-]", self):
                ret.extend(type(self)(p).splitcamel())

        return ret

    def underscore(self):
        """changes the separators to underscore

        :Example:
            NamingConvention("foo-bar").underscore() # foo_bar
        """
        return "_".join(self.split())

    def dash(self):
        """changes the separators to dashes

        :Example:
            NamingConvention("foo_bar").underscore() # foo-bar
        """
        return "-".join(self.split())

    def variations(self):
        """Returns python naming convention variations in self

        :Example:
            NamingConvention("foo-bar").variations() # ["foo-bar", "foo_bar"]

        :returns: list, all the python specific naming variations of self
        """
        s = set()
        for n in [self, self.underscore(), self.dash()]:
            s.add(n)
            s.add(n.lower())
        return s
    def aliases(self): return self.variations()

    def varname(self):
        """Return the typical python variable name for self

        :Example:
            NamingConvention("FooBar").varname() # foo_bar
        """
        return self.snakecase()
    variable_name = varname
    variable = varname
    var_name = varname

    def classname(self):
        """Return the typical python class name for self

        :Example:
            NamingConvention("foo_bar").classname() # FooBar
        """
        return self.camelcase()
    class_name = classname

    def constantname(self):
        """Return the typical constant name for self

        :Example:
            NamingConvention("foo_bar").constantname() # FOO_BAR
        """
        return self.screaming_snakecase()
    constant = constantname

    def keyname(self):
        """Return the typical key name for self

        :Example:
            NamingConvention("FooBar").keyname() # foo-bar
        """
        return self.kebabcase()

    def camelcase(self):
        """Convert a string to use camel case (spaces removed and capital letters)

        CamelCase

        :Example:
            NamingConvention("foo-bar").camelcase() # FooBar

        this method and snakecase come from pout.utils.String, they were moved
        here on March 8, 2022

        https://en.wikipedia.org/wiki/Camel_case
        https://stackoverflow.com/questions/17326185/what-are-the-different-kinds-of-cases
        https://en.wikipedia.org/wiki/Naming_convention_(programming)#Examples_of_multiple-word_identifier_formats
        """
        return "".join(map(lambda s: s.title(), self.split()))
    def upper_camelcase(self):
        """aliase of camel case"""
        return self.camelcase()
    def pascalcase(self):
        """alias of camel casee"""
        return self.camelcase()
    def studlycase(self):
        """alias of camel case"""
        return self.camelcase()
    def CamelCase(self):
        return self.camelcase()

    def lower_camelcase(self):
        """camel case but first letter is lowercase (eg camelCase)

        :Example:
            NamingConvention("foo-bar").lower_camelcase() # fooBar
        """
        cc = self.camelcase()
        return cc[0].lower() + cc[1:]
    def dromedarycase(self):
        """camel case but first letter is lowercase"""
        return self.lower_camelcase()
    def camelCase(self):
        return self.lower_camelcase()

    def snakecase(self):
        """Convert a string to use snake case (lowercase with underscores in place
        of spaces: snake_case)

        :Example:
            NamingConvention("FooBar").snakecase() # foo_bar

        https://en.wikipedia.org/wiki/Snake_case
        """
        s = []
        prev_ch_was_lower = False

        for i, ch in enumerate(self):
            if ch.isupper():
                if i and prev_ch_was_lower:
                    s.append("_")
                s.append(ch)

            elif ch.islower():
                prev_ch_was_lower = True
                s.append(ch)

            elif ch.isspace():
                s.append("_")
                prev_ch_was_lower = False

            elif ch == "-":
                s.append("_")
                prev_ch_was_lower = False

            else:
                prev_ch_was_lower = False
                s.append(ch)

        return "".join(s).lower()
        #return re.sub(r"[\s-]+", "_", "".join(s)).lower()
    def snake_case(self):
        return self.snakecase()

    def screaming_snakecase(self):
        """snake case but all capital letters instead of lowercase (eg, SCREAMING_SNAKE_CASE)

        :Example:
            NamingConvention("FooBar").screaming_snakecase() # FOO_BAR
        """
        return self.snakecase().upper()

    def kebabcase(self):
        """snake case but with dashes instead of underscores (eg kebab-case)

        https://en.wikipedia.org/wiki/Letter_case#Kebab_case
        """
        return self.snakecase().replace("_", "-")

    def screaming_kebabcase(self):
        """snake case but with dashes and all caps (eg SCREAMING-KEBAB-CASE)
        """
        return self.kebabcase().upper()

    def camel_snakecase(self):
        """two_Words

        https://en.wikipedia.org/wiki/Naming_convention_(programming)#Examples_of_multiple-word_identifier_formats
        """
        raise NotImplementedError()

    def pascal_snakecase(self):
        """Two_Words

        https://en.wikipedia.org/wiki/Naming_convention_(programming)#Examples_of_multiple-word_identifier_formats
        """
        raise NotImplementedError()


class EnglishWord(String):
    def plural(self):
        """Pluralize a singular word

        the purpose of this method is not to be right 100% of the time but to be
        good enough for my purposes, for example, it won't return words that
        have the same singular and plural, so it would return sheeps for sheep, this
        is because I usually need the plural to be different. If that isn't the case
        in the future I should pass a flag in to keep that "always different"
        functionality

        teh algo is based off of this:
            https://www.grammarly.com/blog/plural-nouns/

        :returns: string, the plural version of the word
        """
        singular = self
        v = self.lower()

        # http://www.esldesk.com/vocabulary/irregular-nouns
        irregular = {
            "child": "children",
            "goose": "geese",
            "man": "men",
            "woman": "women",
            "tooth": "teeth",
            "foot": "feet",
            "mouse": "mice",
            "person": "people",
        }

        if v in irregular:
            plural = irregular[v]

        elif v[-2:] in set(["ss", "sh", "ch"]):
            plural = singular + "es"

        elif v.endswith("fe"):
            plural = singular[:-2] + "ves"

#         elif v.endswith("us"):
#             if len(self.syllables()) > 1:
#                 plural = singular[:-2] + "i"
#             else:
#                 plural = singular + "es"

        elif v.endswith("is"):
            plural = singular[:-2] + "es"

        elif v.endswith("on") and not v.endswith("ion"):
            plural = singular[:-2] + "a"

        elif v[-1] == "f":
            if v in set(["roof", "belief", "chef", "chief"]):
                plural = singular + "s"
            else:
                plural = singular[:-1] + "ves"

        elif v[-1] == "y" and v[-2:-1] in self.ASCII_CONSONANTS_LOWERCASE:
            plural = singular[:-1] + "ies"

        elif v[-1] == "o":
            if v in set(["photo", "piano", "halo", "volcano"]):
                plural = singular + "s"
            else:
                plural = singular + "es"

        #elif v[-1] in set(["s", "x", "z"]):
        elif v[-1] in set(["s", "x"]):
            plural = singular + "es"

        elif v[-1] in set(["z"]):
            if v[-2:-1] in self.ASCII_VOWELS_LOWERCASE:
                # https://www.dictionary.com/e/word-finder/words-that-end-with-z/
                plural = singular + "zes"

            else:
                plural = singular + "es"

        else:
            plural = singular + "s"

        return plural

    def syllables(self):
        """return the syllables of the word"""
        # https://stackoverflow.com/a/49407494
        return re.findall(r"[^aeiouy]*[aeiouy]+(?:[^aeiouy]*$|[^aeiouy](?=[^aeiouy]))?", self, flags=re.I)


class Character(String):
    """Represents a unicode (UTF-8) character, a unicode character is a set of unicode
    codepoints

    :Example:
        ch = Character("A")
        ch.hex # "0041"
    """
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

    def binary(self):
        from .number import Integer # avoid circular dependency
        ret = ""
        for i in self.integers():
            ret += Integer(i).binary(length=8)
        return ret

    def __iter__(self):
        for cp in self.codepoints:
            yield cp

    def repr_string(self):
        ret = ""
        for cp in self.codepoints:
            if len(cp.hex) <= 4:
                ret += '\\u{:0>4}'.format(cp.hex)
            else:
                ret += '\\U{:0>8}'.format(cp.hex)
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

    def is_complete(self):
        """Return True if this character is complete

        I got the unique prefixes from here:
            * https://andysalerno.com/posts/weird-emojis/
            * https://www.reddit.com/r/programming/comments/o0il4b/unicode_weirdness_bear_plus_snowflake_equals/

        :returns: bool, True if this is a complete UTF-8 character, False otherwise
        """
        from .number import Integer # avoid circular dependency

        i = self.integers()[0]
        # https://unicodebook.readthedocs.io/unicode_encodings.html#utf-16-surrogate-pairs
        # U+D800—U+DBFF (1,024 code points): high surrogates
        # U+DC00—U+DFFF (1,024 code points): low surrogates
        # U+10FFFF is the highest code point encodable to UTF-16
        min_surrogate = 0xD800
        max_surrogate = 0xDFFF
        max_rune = 0x10FFFF

        #pout.v(min_surrogate, max_surrogate, max_rune, i)

        # first check is to make sure we are not in an invalid first byte range
        if (min_surrogate <= i <= max_surrogate) or (i > max_rune):
            # https://stackoverflow.com/a/64628756/5006
            ret = False

        else:
            try:
                bts = self.bytes()
                fb = Integer(bts[0]).binary()

                # https://en.wikipedia.org/wiki/UTF-8#Encoding
                # first byte should have one of these prefixes:
                # 0xxxxxxx | one byte
                # 110xxxxx | two bytes
                # 1110xxxx | three bytes
                # 11110xxx | four bytes
                #
                # subsequent bytes should start with 10xxxxxx
                if fb.startswith("10"):
                    ret = False

                else:
                    if fb.startswith("0"):
                        ret = len(bts) == 1

                    else:
                        m = String(fb).regex(r"^1+0").match()
                        if m:
                            ret = len(bts) == len(m.group(0)) - 1

            except UnicodeError as e:
                ret = False

        return ret


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

    :Example:
        r = Regex(r"foo", "foo bar foo")
        r.count() # 2

        # use through strings
        s = String("foo bar foo")
        s.regex(r"foo").count() # 2

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

    def count(self, flags=0):
        return len(self.findall(flags))

    def __len__(self):
        return self.count()


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

