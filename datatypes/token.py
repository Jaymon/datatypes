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
    """Tokenize a string finding tokens that are divided by passed in deliminators

    https://docs.python.org/3/library/io.html#io.IOBase
    """
    DEFAULT_DELIMS = WHITESPACE + PUNCTUATION
    """IF no deliminators are passed into the constructor then use these"""

    token_class = StreamToken
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
#         pout.v(pos, ch)
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

    def next(self):
        """Get the next Token

        :returns: Token, the next token found in .stream
        """
        ldelim = token = rdelim = None

        start = self.tell_ldelim()

        # find the left deliminator
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

        # find the actual token
        if ch:
            text = ""
            while ch and not self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1
            token = self.token_class(self, text, start, stop)
            start = stop

        # find the right deliminator
        if ch:
            text = ""
            while self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1

            # we're one character ahead, so we want to move back one
            self.stream.seek(stop)

            rdelim = self.token_class(self, text, start, stop)

        if not token:
            raise StopIteration()

        token.ldelim = ldelim
        token.rdelim = rdelim

        return token

    def __next__(self):
        return self.next()

    def prev(self):
        """Returns the previous Token

        :returns: Token, the previous token found in the stream, None if there are
            no previous tokens
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
        """WARNING -- don't use this if you can avoid it"""
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


class NormalizeTokenizer(Tokenizer):
    """A tokenizer that calls a .normalize method that can be overridden by a
    child class so you can manipulate the token before returning it"""
    def next(self):
        t = super().next()
        return self.normalize(t)

    def prev(self):
        t = super().prev()
        return self.normalize(t)

    def normalize(self, t):
        """Override this in a child class to customize functionality"""
        return t


class StringTokenizer(NormalizeTokenizer):
    """A tokenizer that returns str instances instead of tokens because sometimes
    that's all you want"""
    def normalize(self, t):
        return t.text


class ValidTokenizer(NormalizeTokenizer):
    """Similar to NormalizeTokenizer but also calls an .is_valid method to check
    the validity of the token, this will allow you to skip tokens that are
    invalid"""
    def next(self):
        while True:
            t = super().next()
            if self.is_valid(t):
                return t

    def prev(self):
        while True:
            t = super().prev()
            if (t is None) or self.is_valid(t):
                return t

    def is_valid(self, t):
        """Return True if the token is valid or False to skip it"""
        return True


class StopWordTokenizer(ValidTokenizer):
    """Strips stop words from a string"""

    # This list comes from Plancast's Formatting.php library (2010-2-4)
    STOP_WORDS = set([
        'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an',
        'and', 'any', 'are', 'as', 'at', 'be', 'because', 'been', 'before',
        'being', 'below', 'between', 'both', 'but', 'by', 'did', 'do', 'does',
        'doing', 'down', 'during', 'each', 'few', 'for', 'from', 'further',
        'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself',
        'him', 'himself', 'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it',
        'its', 'itself', 'me', 'more', 'most', 'my', 'myself', 'no', 'nor',
        'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our', 'ours',
        'ourselves', 'out', 'over', 'own', 'same', 'she', 'so', 'some', 'such',
        'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then',
        'there', 'these', 'they', 'this', 'those', 'through', 'to', 'too',
        'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when',
        'where', 'which', 'while', 'who', 'whom', 'why', 'with', 'you', 'your',
        'yours', 'yourself', 'yourselves',
    ])

    def is_valid(self, t):
        word = t.text.lower()
        return word not in self.STOP_WORDS


class Scanner(object):
    """Python implementation of Obj-c Scanner

    Moved from bang.utils on 1-6-2023

    https://github.com/Jaymon/PlusPlus/blob/master/PlusPlus/NSString%2BPlus.m
    """
    def __init__(self, text):
        self.text = text
        self.offset = 0
        self.length = len(self.text)

    def to(self, char):
        """scans and returns string up to char"""
        partial = ""
        while (self.offset < self.length) and (self.text[self.offset] != char):
            partial += self.text[self.offset]
            self.offset += 1

        return partial

    def until(self, char):
        """similar to to() but includes the char"""
        partial = self.to(char)
        if self.offset < self.length:
            partial += self.text[self.offset]
            self.offset += 1
        return partial

    def __nonzero__(self): return self.__bool__() # py <3
    def __bool__(self):
        return self.offset < self.length

