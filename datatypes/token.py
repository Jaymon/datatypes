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
from .string import String, ByteString


logger = logging.getLogger(__name__)


class BaseToken(object):
    """The base for the Token and SubToken containing shared functionality"""
    def __str__(self):
        return ByteString(self.__unicode__()) if is_py2 else self.__unicode__()


class SubToken(BaseToken):
    """The subtoken is one of: left-delim, token, right-delim, these are created
    and added to a Token which is returned from the Tokenizer"""
    def __init__(self, tokenizer, text, start, stop):
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

    def __unicode__(self):
        return self.text


class Token(BaseToken):
    """This is what is returned from the Tokenizer and contains 3 subtokens:

        .ldelim - the deliminators to the left of the token
        .token - the actual token that was found
        .rdelim - the deliminators to the right of the token
    """
    def __init__(self, tokenizer, ldelim, token, rdelim):
        self.ldelim = ldelim
        self.token = token
        self.rdelim = rdelim
        self.tokenizer = tokenizer

    def __pout__(self):
        """used by pout python external library

        https://github.com/Jaymon/pout
        """
        tokens = (
            '"{}"'.format(self.ldelim.text) if self.ldelim else None,
            '"{}"'.format(self.token.text),
            '"{}"'.format(self.rdelim.text) if self.rdelim else None,
        )

        return "{}, {}, {}".format(tokens[0], tokens[1], tokens[2])

    def __unicode__(self):
        return self.token.__unicode__()


class StreamTokenizer(io.IOBase):
    """Tokenize a string finding tokens that are divided by pass in deliminators

    https://docs.python.org/3/library/io.html#io.IOBase
    """
    DEFAULT_DELIMS = WHITESPACE + PUNCTUATION
    """IF no deliminators are passed into the constructor then use these"""

    token_class = Token
    """The token class this class will use to create Token instances"""

    subtoken_class = SubToken
    """The subtoken class this class will use to create SubToken instances"""

    def __init__(self, stream, delims=None):
        """
        :param stream: io.IOBase, this is the input that will be tokenized, the stream
            has to be seekable
        :param delims: callback|string, if a callback, it should have the signature:
            callback(char) and return True if the char is a delim, False otherwise.
            If a string then it is a string of chars that will be considered delims
        """
        if not is_py2:
            # python 2 will just raise an error when we try and seek
            if not stream.seekable():
                raise ValueError("Unseekable streams are not supported")

        self.stream = stream

        if callable(delims):
            self.is_delim = delims

        else:
            if not delims:
                delims = self.DEFAULT_DELIMS

            delims = set(delims)
            self.is_delim = lambda ch: ch in delims

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
                    p = 0
                    break

            if p > 0:
                p += 1
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

    def __iter__(self):
        self.stream.seek(0)
        return self

    def peek(self):
        """Return the next token but don't increment the cursor offset"""
        ret = None
        with self.temporary() as t:
            try:
                ret = t.next()
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
            ldelim = self.subtoken_class(self, text, start, stop)
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
            token = self.subtoken_class(self, text, start, stop)
            start = stop

        if ch:
            text = ""
            while self.is_delim(ch):
                text += ch
                ch = self.stream.read(1)

            stop = self.stream.tell() - 1
            rdelim = self.subtoken_class(self, text, start, stop)

        #if not ldelim and not token and not rdelim:
        if not token:
            raise StopIteration()

        return self.token_class(self, ldelim, token, rdelim)

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
            start = token.ldelim.start if token.ldelim else token.token.start
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
                        ret.append(self.next())
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

#         elif whence == SEEK_END:
#             raise NotImplemented()
#             #self.offset = max(0, len(self) - offset)

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
            mixed = StringIO(String(mixed))

        super(Tokenizer, self).__init__(mixed, delims)

