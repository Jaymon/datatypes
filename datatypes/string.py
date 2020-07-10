# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import base64

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
    def __new__(cls, val=b"", encoding="", errors="replace"):
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
        # http://stackoverflow.com/a/5297483/5006
        return hashlib.md5(self).hexdigest()

    def sha256(self):
        return hashlib.sha256(self).digest()


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
    def __new__(cls, val="", encoding="", errors="replace"):
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
        # http://stackoverflow.com/a/5297483/5006
        return hashlib.md5(self.bytes()).hexdigest()

    def sha256(self):
        return hashlib.sha256(self.bytes()).digest()

    def truncate(self, size, postfix='...'):
        """similar to a normal string split but it actually will split on a word boundary

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

    def indent(self, indent):
        """add whitespace to the beginning of each line of val

        http://code.activestate.com/recipes/66055-changing-the-indentation-of-a-multi-line-string/

        :param indent: string, what you want the prefix of each line to be
        :returns: string, string with prefix at the beginning of each line
        """
        if not indent: return self

        s = (indent + line for line in self.splitlines(False))
        s = "\n".join(s)
        return type(self)(s)
Unicode = String


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
    def unescape(cls, html):
        """unescapes html entities (eg, &gt;) to plain text (eg, &gt; becomes >)"""
        # https://stackoverflow.com/a/2087433/5006
        return unescape(html)

