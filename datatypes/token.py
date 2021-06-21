# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from io import SEEK_SET, SEEK_CUR, SEEK_END
import re
import itertools
import logging
from contextlib import contextmanager
from string import whitespace as WHITESPACE, punctuation as PUNCTUATION
import io

from .compat import *
from .string import String, ByteString, HTMLParser


logger = logging.getLogger(__name__)


class Token(object):
    """The base for the Token and SubToken containing shared functionality"""
    def __init__(self, tokenizer, text, start=-1, stop=-1):
        """
        :param tokenizer: StreamTokenizer, the tokenizer creating this subtoken
        :param text: string, the text of this subtoken
        :param start: int, the cursor offset this subtoken starts at in the tokenizer
        :param stop: int, the cursor offset this subtoken ends at in the tokenizer
        """
        self.text = text
        self.start = start
        self.stop = stop
        self.tokenizer = tokenizer

    def __str__(self):
        return ByteString(self.__unicode__()) if is_py2 else self.__unicode__()

    def __unicode__(self):
        return self.text


class StreamToken(Token):
    """This is what is returned from the Tokenizer and contains pointers to the
    left deliminator and the right deliminator, and also the actual token

        .ldelim - the deliminators to the left of the token
        .text - the actual token value that was found
        .rdelim - the deliminators to the right of the token
    """
    def __init__(self, tokenizer, text, start, stop, ldelim=None, rdelim=None):
        super(StreamToken, self).__init__(tokenizer, text, start, stop)
        self.ldelim = ldelim
        self.rdelim = rdelim

    def __pout__(self):
        """used by pout python external library

        https://github.com/Jaymon/pout
        """
        tokens = (
            '"{}"'.format(self.ldelim.text) if self.ldelim else None,
            '"{}"'.format(self.text),
            '"{}"'.format(self.rdelim.text) if self.rdelim else None,
        )

        return "{}, {}, {}".format(tokens[0], tokens[1], tokens[2])


class StreamTokenizer(io.IOBase):
    """Tokenize a string finding tokens that are divided by pass in deliminators

    https://docs.python.org/3/library/io.html#io.IOBase
    """
    DEFAULT_DELIMS = WHITESPACE + PUNCTUATION
    """IF no deliminators are passed into the constructor then use these"""

    token_class = Token
    """The token class this class will use to create Token instances"""

    def __init__(self, stream, delims=None):
        """
        :param stream: io.IOBase, this is the input that will be tokenized, the stream
            has to be seekable
        :param delims: callback|string|set, if a callback, it should have the signature:
            callback(char) and return True if the char is a delim, False otherwise.
            If a string then it is a string of chars that will be considered delims
        """
        self.delims = delims
        self.stream = stream

        if not is_py2:
            # python 2 will just raise an error when we try and seek
            if not self.seekable():
                raise ValueError("Unseekable streams are not supported")

        self.reset()

    def is_delim(self, ch):
        ret = False
        delims = self.delims
        if delims:
            if callable(delims):
                ret = delims(ch)

            else:
                ret = ch in delims
        return ret

    def tell_ldelim(self):
        """Tell the current ldelim start position, this is mainly used internally

        :returns: int, the cursor position of the start of the left deliminator of
            the current token
        """
        pos = self.stream.tell()
        ch = self.stream.read(1)
        if not ch:
            # EOF, stream is exhausted
            raise StopIteration()

        if self.is_delim(ch):
            p = pos
            while self.is_delim(ch):
                p -= 1
                if p >= 0:
                    self.stream.seek(p)
                    ch = self.stream.read(1)

                else:
                    break

            if p >= 0:
                p += 1
            else:
                p = 0
            pos = p

        else:
            p = pos
            while not self.is_delim(ch):
                p -= 1
                if p >= 0:
                    self.stream.seek(p)
                    ch = self.stream.read(1)

                else:
                    break

            if p >= 0:
                self.stream.seek(p)
                pos = self.tell_ldelim()

            else:
                pos = -1

        return pos

    def reset(self):
        delims = self.delims
        if not delims:
            delims = self.DEFAULT_DELIMS
        if delims and not callable(delims):
            delims = set(delims)
        self.delims = delims

        self.stream.seek(0)

    def __iter__(self):
        self.reset()
        return self

    def peek(self):
        """Return the next token but don't increment the cursor offset"""
        ret = None
        with self.temporary() as it:
            try:
                ret = it.next()
            except StopIteration:
                pass
        return ret

    def next(self):
        """Get the next Token

        :returns: Token, the next token found in .stream
        """
        ldelim = token = rdelim = None

        start = self.tell_ldelim()

        if start >= 0:
            text = ""
            self.stream.seek(start)
            ch = self.stream.read(1)

            while self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1
            ldelim = self.token_class(self, text, start, stop)
            start = stop

        else:
            start = 0
            self.stream.seek(start)
            ch = self.stream.read(1)

        if ch:
            text = ""
            while ch and not self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1
            token = self.token_class(self, text, start, stop)
            start = stop

        if ch:
            text = ""
            while self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1
            rdelim = self.token_class(self, text, start, stop)

        #if not ldelim and not token and not rdelim:
        if not token:
            raise StopIteration()

        token.ldelim = ldelim
        token.rdelim = rdelim
        return token

    def __next__(self):
        return self.next()

    def prev(self):
        """Returns the previous Token

        :returns: Token, the previous token found in the stream
        """
        token = None
        try:
            start = self.tell_ldelim()

        except StopIteration:
            self.seek(self.tell() - 1)
            start = self.tell_ldelim()
            token = self.next()

        else:
            if start > 0:
                self.seek(start - 1)
                start = self.tell_ldelim()
                token = self.next()

        if token:
            start = token.ldelim.start if token.ldelim else token.start
            self.seek(start)
        return token

    def read(self, count=-1):
        """Read count tokens and return them

        :param count: int, if >0 then return count tokens, if -1 then return all
            remaining tokens
        :returns: list, the read Token instances
        """
        ret = []
        if count:
            if count > 0:
                while count > 0:
                    try:
                        ret.append(self.next())
                    except StopIteration:
                        break

                    else:
                        count -= 1

            else:
                while True:
                    try:
                        token = self.next()
                        ret.append(token)
                    except StopIteration:
                        break

        return ret

    def readall(self):
        """Read and return all remaining tokens"""
        return self.read()

    def fileno(self):
        return self.stream.fileno()

    def readable(self):
        return self.stream.readable()

    def writeable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.writable"""
        return False

    def tell(self):
        """Return the current stream position"""
        return self.stream.tell()

    def seek(self, offset, whence=SEEK_SET):
        """Change the stream position to the given byte offset. offset is interpreted
        relative to the position indicated by whence.

        The default value for whence is SEEK_SET. Values for whence are:

            * SEEK_SET or 0 – start of the stream (the default); offset should be zero or positive
            * SEEK_CUR or 1 – current stream position; offset may be negative

        Return the new absolute position.
        """
        offset = int(offset)

        if whence == SEEK_SET:
            self.stream.seek(max(0, offset))

        elif whence == SEEK_CUR:
            self.stream.seek(max(0, self.tell() + offset))

        elif whence == SEEK_END:
            self.offset = max(0, self.total() - offset)

        else:
            raise ValueError("Unknown or unsupported whence value: {}".format(whence))

        return self.tell()

    def seekable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.seekable"""
        return self.stream.seekable()

    @contextmanager
    def transaction(self):
        """If an error is raised reset the cursor back to where the transaction
        was started"""
        start = self.tell()
        try:
            yield self

        except Exception as e:
            self.seek(start)
            raise

    @contextmanager
    def temporary(self):
        """similar to .transaction() but will always discard anything read and
        reset the cursor back to where it started, you use this because you want
        to check some tokens ephemerally"""
        start = self.tell()
        try:
            yield self

        finally:
            self.seek(start)

    def count(self):
        """This is a terrible way to do this, but sometimes you just want to know
        how many tokens you have left

        :returns: int, how many tokens you have left
        """
        count = 0
        with self.temporary() as it:
            try:
                while it.next():
                    count += 1
            except StopIteration:
                pass

        return count

    def total(self):
        """Returns the total number of tokens no matter where offset is positioned

        :returns: int, the total tokens, irrespective of .offset
        """
        with self.temporary() as it:
            it.seek(0)
            total = it.count()
        return total

    def __len__(self):
        """WARNING -- don't use this if you can, at all, avoid it"""
        return self.total()

    def close(self, *args, **kwargs):
        raise NotImplementedError()

    def closed(self, *args, **kwargs):
        raise NotImplementedError()

    def flush(self, *args, **kwargs):
        raise NotImplementedError()

    def readline(self, size=-1):
        raise NotImplementedError()

    def readline(self, hint=-1):
        raise NotImplementedError()


class Tokenizer(StreamTokenizer):
    """Extends stream tokenizer to accept strings or IO streams"""
    def __init__(self, mixed, delims=None):
        if isinstance(mixed, basestring):
            # you can't use the compat imported StringIO because it uses
            # cStringIO and that fails with unicode strings on python 2.7
            mixed = io.StringIO(String(mixed))

        super(Tokenizer, self).__init__(mixed, delims)


class HTMLToken(Token):
    """This is what is returned from the HTMLTokenizer

        .tagname - the name of the tag
        .text - the body of the tag
    """
    @property
    def text(self):
        text = []
        for d in self.taginfo.get("body", []):
            if "tagname" in d:
                t = type(self)(self.tokenizer, d)
                text.append(t.__unicode__())

            else:
                text.extend(d["body"])

        return "".join(text)

    def __init__(self, tokenizer, taginfo):
        self.tagname = taginfo.get("tagname", "")
        self.start = taginfo.get("start", -1)
        self.stop = taginfo.get("stop", -1)
        self.taginfo = taginfo
        self.tokenizer = tokenizer

    def __getattr__(self, k):
        if k in self.taginfo:
            return self.taginfo[k]

        else:
            ret = None
            for attr_name, attr_val in self.taginfo.get("attrs", []):
                if attr_name == k:
                    return attr_val

        raise AttributeError(k)
        #return super(HTMLToken, self).__getattr__(k)

    def attrs(self):
        ret = {}
        for attr_name, attr_val in self.taginfo.get("attrs", []):
            ret[attr_name] = attr_val
        return ret

    def __pout__(self):
        """used by pout python external library

        https://github.com/Jaymon/pout
        """
        return self.__unicode__()

    def __unicode__(self):
        attrs = ""
        for ak, av in self.attrs().items():
            attrs += ' {}="{}"'.format(ak, av)

        s = "<{}{}>{}</{}>".format(
            self.tagname,
            attrs,
            self.text,
            self.tagname
        )
        return s


class HTMLTokenizer(Tokenizer):
    DEFAULT_DELIMS = None
    token_class = HTMLToken

    def __init__(self, html, tagnames=None):
        """
        :param stream: io.IOBase, this is the input that will be tokenized, the stream
            has to be seekable
        :param delims: callback|string, if a callback, it should have the signature:
            callback(char) and return True if the char is a delim, False otherwise.
            If a string then it is a string of chars that will be considered delims
        """
        stream = HTMLParser(html, tagnames)
        super(HTMLTokenizer, self).__init__(stream)

    def next(self):
        taginfo = self.stream.next()
        return self.token_class(self, taginfo)

    def prev(self):
        ret = None
        pos = self.tell()
        if pos > 0:
            self.seek(pos - 1)
            ret = self.next()
        return ret

    def tell_ldelim(self):
        raise NotImplementedError()


