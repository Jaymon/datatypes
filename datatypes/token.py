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
        :param start: int, the cursor offset this subtoken starts at in the
            tokenizer
        :param stop: int, the cursor offset this subtoken ends at in the
            tokenizer
        """
        self.text = text
        self.start = start
        self.stop = stop
        self.tokenizer = tokenizer

    def __str__(self):
        return self.text

    def __unicode__(self):
        return self.text


class TokenizerABC(io.IOBase):
    def set_buffer(self, buffer):
        raise NotImplementedError()

    def next(self):
        raise NotImplementedError()

    def prev(self):
        raise io.UnsupportedOperation()


class Tokenizer(io.IOBase):
    """The base class for building a tokenizer

    A Tokenizer class acts like an IO object but returns tokens instead of
    strings and all read operations return Token isntances and all setting
    operations manipulate positions according to tokens

    Summarized from https://stackoverflow.com/a/380487
        A tokenizer breaks a stream of text into tokens, usually by breaking it
        up by some deliminator, a common deliminator is whitespace (eg, tabs,
        spaces, new lines)

        A lexer is basically a tokenizer, but it usually attaches extra context
        to the tokens (eg this token is a number or a string or a boolean)

        A parser takes the stream of tokens from the lexer and gives it some
        sort of structure that was represented by the original text

    https://docs.python.org/3/library/io.html#io.IOBase
    """
    token_class = Token
    """The token class this class will use to create Token instances"""

    def __init__(self, buffer):
        """
        :param buffer: str|io.IOBase, this is the input that will be tokenized,
            the buffer has to be seekable
        """
        self.set_buffer(buffer)

    def __iter__(self):
        self.seek(0)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        return False if exception_value else True

    def set_buffer(self, buffer):
        if isinstance(buffer, basestring):
            buffer = io.StringIO(String(buffer))

        self.buffer = buffer

        if not self.seekable():
            raise ValueError("Unseekable streams are not supported")

        self.seek(0)

    def peek(self):
        """Return the next token but don't increment the cursor offset"""
        with self.temporary() as it:
            try:
                return it.next()

            except StopIteration:
                pass

    def tell(self):
        """Return the starting position of the current token but don't increment
        the cursor offset"""
        t = self.peek()
        return t.start if t else self.buffer.tell() 

    def __next__(self):
        return self.next()

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
        return self.buffer.fileno()

    def readable(self):
        return self.buffer.readable()

    def writeable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.writable"""
        return False

    def seek(self, offset, whence=SEEK_SET):
        """Change to the token given by offset and calculated according to the
        whence value

        Change the token position to the given offset. offset is
        interpreted relative to the position indicated by whence.

        The default value for whence is SEEK_SET. Values for whence are:

            * SEEK_SET or 0 – start of the tokens (the default); offset should
                be zero or positive
            * SEEK_CUR or 1 – current token position; offset may be negative
            * SEEK_END or 2 – end of the tokens; offset is usually negative

        Return the new absolute buffer position.

        https://docs.python.org/3/library/io.html#io.IOBase.seek

        :param offset: int, the token to seek to
        :returns: int, the starting position in the buffer of the token
        """
        offset = int(offset)

        if whence == SEEK_SET:
            offset = max(0, offset)

        elif whence == SEEK_CUR:
            if offset:
                for _ in range(abs(offset)):
                    t = self.prev()
                    offset = t.start

            else:
                offset = self.buffer.tell()

        elif whence == SEEK_END:
            total = len(self)
            total = max(total, total - abs(offset))
            with self.temporary() as it:
                it.seek(0)
                for _ in range(total):
                    t = it.next()

                offset = t.start

        else:
            raise ValueError(f"Unknown or unsupported whence value: {whence}")

        self.buffer.seek(offset)
        return offset

    def seekable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.seekable"""
        return self.buffer.seekable()

    @contextmanager
    def transaction(self):
        """If an error is raised reset the cursor back to where the transaction
        was started"""
        start = self.buffer.tell()
        try:
            yield self

        except Exception as e:
            self.buffer.seek(start)
            raise

    @contextmanager
    def temporary(self):
        """similar to .transaction() but will always discard anything read and
        reset the cursor back to where it started, you use this because you want
        to check some tokens ephemerally"""
        start = self.buffer.tell()
        try:
            yield self

        finally:
            self.buffer.seek(start)

    def count(self):
        """This is a terrible way to do this, but sometimes you just want to
        know how many tokens you have left

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

    def __len__(self):
        """Returns the total number of tokens no matter where offset is positioned

        WARNING -- don't use this if you can avoid it because it will parse the
            entire buffer and then reset it so it is not efficient in any way

        :returns: int, the total tokens, irrespective of current offset
        """
        with self.temporary() as it:
            it.seek(0)
            total = it.count()
        return total

    def close(self, *args, **kwargs):
        raise io.UnsupportedOperation()

    def closed(self, *args, **kwargs):
        return self.buffer.closed()

    def readline(self, size=-1):
        raise io.UnsupportedOperation()

    def readlines(self, hint=-1):
        raise io.UnsupportedOperation()


class WordToken(Token):
    """This is what is returned from the Tokenizer and contains pointers to the
    left deliminator and the right deliminator, and also the actual token

        .ldelim - the deliminators to the left of the token
        .text - the actual token value that was found
        .rdelim - the deliminators to the right of the token
    """
    def __init__(self, tokenizer, text, start, stop, ldelim=None, rdelim=None):
        super().__init__(tokenizer, text, start, stop)
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


class WordTokenizer(Tokenizer):
    """Tokenize a string finding tokens that are divided by passed in
    characters
    """
    DEFAULT_CHARS = WHITESPACE + PUNCTUATION
    """IF no deliminators are passed into the constructor then use these"""

    token_class = WordToken
    """The token class this class will use to create Token instances"""

    def __init__(self, buffer, chars=None):
        """
        :param buffer: str|io.IOBase, passed through to parent
        :param chars: callable|str|set, if a callback, it should have the
            signature: callback(char) and return True if the char is a delim,
            False otherwise. If a string then it is a string of chars that will
            be considered delims
        """
        if not chars:
            chars = self.DEFAULT_CHARS

        if chars and not callable(chars):
            chars = set(chars)

        self.chars = chars

        super().__init__(buffer)

    def is_delim_char(self, ch):
        ret = False
        chars = self.chars
        if chars:
            if callable(chars):
                ret = chars(ch)

            else:
                ret = ch in chars

        return ret

    def tell_ldelim(self):
        """Tell the current ldelim start position, this is mainly used internally

        :returns: int, the cursor position of the start of the left deliminator of
            the current token
        """
        pos = self.buffer.tell()
        ch = self.buffer.read(1)
#         pout.v(pos, ch)
        if not ch:
            # EOF, stream is exhausted
            raise StopIteration()

        if self.is_delim_char(ch):
            p = pos
            while self.is_delim_char(ch):
                p -= 1
                if p >= 0:
                    self.buffer.seek(p)
                    ch = self.buffer.read(1)

                else:
                    break

            if p >= 0:
                p += 1
            else:
                p = 0
            pos = p

        else:
            p = pos
            while not self.is_delim_char(ch):
                p -= 1
                if p >= 0:
                    self.buffer.seek(p)
                    ch = self.buffer.read(1)

                else:
                    break

            if p >= 0:
                self.buffer.seek(p)
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
            self.buffer.seek(start)
            ch = self.buffer.read(1)

            while self.is_delim_char(ch):
                text += ch
                ch = self.buffer.read(1)

            stop = self.buffer.tell() - 1
            ldelim = self.token_class(self, text, start, stop)
            start = stop

        else:
            start = 0
            self.buffer.seek(start)
            ch = self.buffer.read(1)

        # find the actual token
        if ch:
            text = ""
            while ch and not self.is_delim_char(ch):
                text += ch
                ch = self.buffer.read(1)

            stop = self.buffer.tell() - 1
            token = self.token_class(self, text, start, stop)
            start = stop

        # find the right deliminator
        if ch:
            text = ""
            while self.is_delim_char(ch):
                text += ch
                ch = self.buffer.read(1)

            stop = self.buffer.tell() - 1

            # we're one character ahead, so we want to move back one
            self.buffer.seek(stop)

            rdelim = self.token_class(self, text, start, stop)

        if not token:
            raise StopIteration()

        token.ldelim = ldelim
        token.rdelim = rdelim

        return token

    def prev(self):
        """Returns the previous Token

        :returns: Token, the previous token found in the stream, None if there are
            no previous tokens
        """
        token = None
        try:
            start = self.tell_ldelim()

        except StopIteration:
            self.buffer.seek(self.buffer.tell() - 1)
            start = self.tell_ldelim()
            token = self.next()

        else:
            if start > 0:
                self.buffer.seek(start - 1)
                start = self.tell_ldelim()
                token = self.next()

        if token:
            start = token.ldelim.start if token.ldelim else token.start
            self.buffer.seek(start)

        return token


class StopWordTokenizer(WordTokenizer):
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
        word = t.text.lower()
        return word not in self.STOP_WORDS


class Scanner(io.StringIO):
    """Python implementation of an Obj-c Scanner

    This is really handy to build arbitrary parsers and tokenizers

    :Example:
        s = Scanner("before [[che baz]] middle [[foo]] after")
        s.to("[[") # "before "
        s.until("]]") # "[[che baz]]"
        s.to("[[") # " middle "
        s.until("]]") # "[[foo]]"
        s.to("[[") # " after"

    Moved from bang.utils on 1-6-2023

    * https://developer.apple.com/documentation/foundation/nsscanner
    * https://docs.python.org/3/library/io.html#io.StringIO
    """
    def __init__(self, buffer, offset=0):
        #self.text = text
        #self.length = len(self.text)
        super().__init__(buffer)
        if offset > 0:
            self.seek(offset)

    def peek(self):
        return self.getvalue()[self.tell()]

#     def seek(self, offset):
#         self.offset = offset
# 
#     def tell(self):
#         return self.text[self.offset]
# 
#     def close(self):
#         pass
# 
#     def closed(self):
#         return False
# 
#     def 

#     def read(self, limit=None):
#         """Return a segment from self.offset to offset + limit
# 
#         :Example:
#             s = Scanner("foo bar [[che baz]]")
#             s.to("[[") # "foo bar "
#             s.read(5) # "[[che"
# 
#         :param limit: int, how many chars you want to return in the segment
#         :returns: str, the segment of length limit
#         """
#         if limit:
#             offset = self.offset + limit
#             partial = self.text[self.offset:offset]
#             self.offset = offset
# 
#         else:
#             partial = self.text[self.offset:]
#             self.offset = self.length
# 
#         return partial

    def read_thru_chars(self, chars):
        """Read while chars are encountered

        :Example:
            s = Scanner("12345 foo bar")
            s.chars("1234567890") # "12345"

        :param chars: str|Container, the characters that will be read, nothing
            outside of this set of characters will be returned
        :returns: str, a string containing the number of characters in a row
            found in chars
        """
        partial = ""
        offset = self.tell()
        buffer = self.getvalue()
        length = len(self)

        while offset < length:
            ch = buffer[offset]
            if ch in chars:
                partial += ch
                offset += 1

            else:
                break

        self.seek(offset)
        return partial

    def read_to_chars(self, chars):
        return self.read_to(chars=chars)

    def read_until_chars(self, chars):
        return self.read_until(chars=chars)

    def read_thru_whitespace(self):
        return self.read_thru_chars(WHITESPACE)

    def read_to_whitespace(self):
        return self.read_to(chars=WHITESPACE)

    def read_to_newline(self):
        return self.read_to(chars="\n")

    def read_until_newline(self):
        return self.read_to(chars="\n")

    def read_to(self, **kwargs):
        """scans and returns string up to delim

        :Example:
            s = Scanner("foo bar [[che baz]]")
            s.to("[[") # "foo bar "

        :param delim: str, the sentinel we're looking for
        :returns: str, returns self.text from self.offset when this method was
            called to the offset right before delim starts
        """
        partial = ""

        delim = kwargs.get("delim", "")
        chars = set(kwargs.get("chars", ""))
        delim_len = len(delim)

        buffer = self.getvalue()
        offset = self.tell()
        length = len(self)

        while offset < length:
            # escaped characters don't count against our delim
            if buffer[offset] == "\\":
                partial += buffer[offset]

                # record the character and move passed it since it can't
                # be taken into account when checking the delim because it
                # is escaped
                offset += 1
                partial += buffer[offset]

                offset += 1

            if delim:
                st = buffer[offset:offset + delim_len]

                if st == delim:
                    break

            elif chars:
                st = buffer[offset]
                if st in chars:
                    break

            partial += buffer[offset]
            offset += 1

        self.seek(offset)
        return partial

    def read_until(self, **kwargs):
        delim = kwargs.get("delim", "")
        chars = set(kwargs.get("chars", ""))
        count = kwargs.get("count", 1)

        partial = ""
        for _ in range(count):
            if delim:
                partial += self.read_to(delim=delim)
                partial += self.read(len(delim))

            elif chars:
                partial += self.read_to(chars=chars) + self.read(1)

        return partial

    def read_to_delim(self, delim):
        """scans and returns string up to delim

        :Example:
            s = Scanner("foo bar [[che baz]]")
            s.to("[[") # "foo bar "

        :param delim: str, the sentinel we're looking for
        :returns: str, returns self.text from self.offset when this method was
            called to the offset right before delim starts
        """
        return self.read_to(delim=delim)

    def read_until_delim(self, delim, **kwargs):
        """scans and returns string up to and including delim

        :Example:
            s = Scanner("foo bar [[che baz]]")
            s.to("[[") # "foo bar "
            s.until("]]") # "[[che baz]]"

        :param delim: str, the sentinel we're looking for
        :returns: str, returns self.text from self.offset when this method was
            called to the offset right after delim ends
        """
        return self.read_until(delim=delim, **kwargs)

#         partial = self.read_to_delim(delim)
#         delim_len = len(delim)
#         buffer = self.getvalue()
#         offset = self.tell()
# 
#         if self:
#             partial += buffer[offset:offset + delim_len]
#             offset += delim_len
# 
#         self.seek(offset)
#         return partial

    def __bool__(self):
        return self.tell() < self.__len__()

    def __len__(self):
        return len(self.getvalue())



class ABNFRule(Token):

    def __init__(self, tokenizer, name, definitions, comments, start, stop):
        self.name = name
        self.definitions = definitions
        self.comments = comments

        super().__init__(tokenizer, None, start=start, stop=stop)


class ABNFTokenizer(Tokenizer):

    token_class = ABNFRule

    def set_buffer(self, buffer):
        self.buffer = Scanner(buffer)

    def next(self):
        scanner = self.buffer
        start = scanner.tell()
        comments = []
        definitions = []

        name = scanner.read_to_delim("=").strip()

        # move passed the equal sign and whitespace to the right of the equal
        # sign
        scanner.read_thru_chars("= \t")

        while scanner:
            ch = scanner.peek()

            if ch == "\"":
                literal = scanner.read_until_delim("\"", count=2)
                literal = literal.strip("\"")
                definitions.append(literal)

            elif ch in String.ASCII_LETTERS:
                rule = scanner.read_to_chars(String.WHITESPACE + ";")
                definitions.append(rule)

            elif ch == ";":
                comments.append(scanner.read_to_newline())

            elif ch == "\n":
                scanner.read_thru_chars("\n")
                ch = scanner.peek()
                if not ch.isspace():
                    break

            else:
                scanner.read_thru_chars(" \t")

        stop = scanner.tell() - 1
#         if stop < 0:
#             pout.v(scanner.getvalue())
#             stop = len(scanner.getvalue()) - 1

        return self.token_class(
            self,
            name=name,
            definitions=definitions,
            comments=comments,
            start=start,
            stop=stop
        )





