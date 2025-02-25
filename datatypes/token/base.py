# -*- coding: utf-8 -*-
from io import SEEK_SET, SEEK_CUR, SEEK_END
from contextlib import contextmanager
import io

from ..compat import *
from ..string import String


class Token(object):
    """The base for the Token and SubToken containing shared functionality"""
    def __init__(self, tokenizer, start=-1, stop=-1):
        """
        :param tokenizer: Tokenizer, the tokenizer creating this token
        :param start: int, the cursor offset this token starts at in the
            buffer the tokenizer is tokenizing
        :param stop: int, the cursor offset this token ends at in the buffer
            the tokenizer is tokenizing
        """
        self.start = start
        self.stop = stop
        self.tokenizer = tokenizer


class TokenizerABC(io.IOBase):
    def normalize_buffer(self, buffer):
        """Implemented in Tokenizer and called by Tokenizer.set_buffer,
        this is here because children might want to customize what the
        buffer actually is

        :param buffer: str|IOBase
        :returns: IOBase, it needs to be seekable
        """
        raise NotImplementedError()

    def next(self):
        raise NotImplementedError()

    def prev(self):
        raise io.UnsupportedOperation()


class Tokenizer(io.IOBase):
    """The base class for building a tokenizer

    A Tokenizer class acts like an IO object but returns tokens instead of
    strings and all read operations return Token instances and all setting
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

    def normalize_buffer(self, buffer):
        if isinstance(buffer, basestring):
            buffer = io.StringIO(String(buffer))

        return buffer

    def set_buffer(self, buffer):
        self.buffer = self.normalize_buffer(buffer)

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
        """Return the starting position of the current token but don't
        increment the cursor offset"""
        t = self.peek()
        return t.start if t else self.buffer.tell() 

    def __next__(self):
        return self.next()

    def read(self, count=-1):
        """Read count tokens and return them

        :param count: int, if >0 then return count tokens, if -1 then return
            all remaining tokens
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
        """Returns the total number of tokens no matter where offset is
        positioned

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


class Scanner(io.StringIO):
    """Python implementation of an Obj-c Scanner

    This is really handy to build arbitrary parsers and tokenizers

    There are 3 keywords you need to know to use this class effectively:

        * to - read anything up to the sentinel but don't include the sentinel
        * until - read anything up to and thru the sentinel values, this will
            include the sentinel value at the end that stopped the reading
        * thru - read only the sentinel values and nothing else, the return
            will be empty if no sentinel values were found

    There are 2 main sentinel value types:

        * delims - a list of arbitrary length strings that will be checked
            (ie, ["foo", "bar"] will check for the sentinels "foo" and "bar"
            and will keep going until "foo" or "bar" are encountered in total)
        * chars - a set of single characters to be checked (ie, "abc" will
            check for character "a", "b", and "c" separately and if any one of
            those matches the sentinel is considered found)

    :Example:
        s = Scanner("before [[che baz]] middle [[foo]] after")
        s.read_to_delim("[[") # "before "
        s.read_until_delim("]]") # "[[che baz]]"
        s.read_to_delim("[[") # " middle "
        s.read_until_delim("]]") # "[[foo]]"
        s.readline() # " after"

    Moved from bang.utils on 1-6-2023

    * https://developer.apple.com/documentation/foundation/nsscanner
    * https://docs.python.org/3/library/io.html#io.StringIO
    """
    def __init__(self, buffer, offset=0):
        super().__init__(buffer)
        if offset > 0:
            self.seek(offset)

    @contextmanager
    def transaction(self):
        """If an error is raised reset the cursor back to where the transaction
        was started"""
        index = self.tell()
        try:
            yield self

        except Exception as e:
            self.seek(index)
            raise

    def peek(self, count=1):
        with self.transaction():
            return self.read(count)

    def skip(self, count):
        """Skip ahead count characters"""
        self.seek(self.tell() + count)

#     def read_thru_whitespace(self, **kwargs):
#         """read from the current offset through any whitespace characters,
#         basically read until you encounter a non-whitespace character"""
#         return self.read_thru(chars=String.WHITESPACE, **kwargs)
# 
#     def read_to_whitespace(self, **kwargs):
#         """Read non-whitespace characters until you hit any whitespace"""
#         return self.read_to(chars=String.WHITESPACE, **kwargs)
# 
#     def read_thru_hspace(self, **kwargs):
#         """read through horizontal spaces (ie, space and tab)"""
#         return self.read_thru(chars=String.HORIZONTAL_SPACE, **kwargs)
# 
#     def read_to_hspace(self, **kwargs):
#         """read to horizontal spaces (ie, space and tab)"""
#         return self.read_to(chars=String.HORIZONTAL_SPACE, **kwargs)
# 
#     def read_to_newline(self, **kwargs):
#         """Return all characters up to but not including a newline"""
#         return self.read_to(chars="\n", **kwargs)

#     def read_until_newline(self, **kwargs):
#         """Return all characters up to and including a newline"""
#         return self.read_until(chars="\n", **kwargs)

    def _normalize_delims(self, **kwargs):
        """Internal method that normalizes the kwargs for the three
        semi-internal read methods (to, until, thru) since they all take the
        same kwargs

        :keyword delim: str, the sentinel we're looking for (eg "foo")
        :keyword delims: list, the sentinels we're looking for
            (eg ["foo", "bar"])
        :keyword chars: Container|str, any of the characters in the set will
            cause the reader to exit (eg, {"f", "o", "o"})
        :keyword chrange: Sequence, a range of characters
            (eg range(0x00, 0x7F))
        :keyword whitespace: bool, True for all whitespace delims to be
            included
        :keyword hspace: bool, True for only horizontal (space and tab) spaces
            to be included
        :keyword newline: bool, True for newline to be a delim
        :returns: dict[str, int], the key is the delim and the value is the
            length of the delim
        """
        delims = {}
        prefix = kwargs.get("prefix", "")

        for delim in kwargs.get(f"{prefix}delims", []):
            delims[delim] = len(delim)

        if delim := kwargs.get(f"{prefix}delim", ""):
            delims[delim] = len(delim)

        for char in kwargs.get(f"{prefix}chars", ""):
            delims[char] = len(char)

        if char := kwargs.get(f"{prefix}char", ""):
            delims[char] = len(char)

        for chint in kwargs.get(f"{prefix}chrange", []):
            char = chr(chint)
            delims[char] = len(char)

        if kwargs.get(f"{prefix}whitespace", False):
            for char in String.WHITESPACE:
                delims[char] = len(char)

        if kwargs.get(
            f"{prefix}hspace",
            kwargs.get(f"{prefix}horizontal_space", False)
        ):
            for char in String.HORIZONTAL_SPACE:
                delims[char] = len(char)

        if kwargs.get(f"{prefix}newline", False):
            delims["\n"] = 1
            #delims["\r\n"] = 2

        return delims

    def _normalize_include_delim(self, default=False, **kwargs):
        return kwargs.get(
            "include_delim",
            kwargs.get("include", default)
        )

    def _read_to_delim(self, delims):
        partial = ""

        while True:
            offset = self.tell()
            char = self.read(1)
            delim = ""
            delim_len = 0

            if char == "":
                # we've reached eof
                break

            elif char == "\\":
                # escaped characters don't count against our delim
                partial += char

                # record the character and move passed it since it can't
                # be taken into account when checking the delim because it
                # is escaped
                partial += self.read(1)
                offset = self.tell()
                char = self.read(1)

            found = False

            for delim, delim_len in delims.items():
                token = char + self.read(delim_len - 1)

                self.seek(offset)
                char = self.read(1)

                if token == delim:
                    self.seek(offset)
                    found = True
                    break

            if found:
                break

            else:
                # we are basically re-reading the character so internal
                # offset will increment
                partial += char
                #partial += self.read(1)

        return partial, delim, delim_len

    def _read_thru_delim(self, delims):
        partial = ""
        offset = self.tell()

        found = False

        for delim, delim_len in delims.items():
            partial = self.read(delim_len)
            self.seek(offset)

            if partial == delim:
                found = True
                break

            else:
                partial = ""

        if not found:
            delim = ""
            delim_len = 0

        return partial, delim, delim_len

    def read_to(self, **kwargs):
        """scans and returns string up to but not including delims or chars

        .. Example:
            s = Scanner("foo bar [[che baz]]")
            s.read_to(delim="[[") # "foo bar "

        :param **kwargs: see ._read_kwargs
        :returns: str, returns self.getvalue() from self.tell() when this
            method was called to self.tell() right before the sentinel starts
        """
        delims = self._normalize_delims(**kwargs)
        delims.update(self._normalize_delims(prefix="stop_", **kwargs))
        include_delim = self._normalize_include_delim(**kwargs)

        partial, delim, delim_len = self._read_to_delim(delims)

        if include_delim and delim_len > 0:
            partial += delim
            self.skip(delim_len)
            #self.seek(self.tell() + delim_len)

        return partial

#     def read_to(self, **kwargs):
#         """scans and returns string up to but not including delims or chars
# 
#         .. Example:
#             s = Scanner("foo bar [[che baz]]")
#             s.read_to(delim="[[") # "foo bar "
# 
#         :param **kwargs: see ._read_kwargs
#         :returns: str, returns self.getvalue() from self.tell() when this
#             method was called to self.tell() right before the sentinel starts
#         """
#         partial = ""
# 
#         delims = self._normalize_delims(**kwargs)
#         delims.update(self._normalize_delims(prefix="stop_", **kwargs))
#         include_delim = self._normalize_include_delim(**kwargs)
#         buffer = self.getvalue()
#         offset = self.tell()
#         length = len(self)
# 
#         while offset < length:
#             # escaped characters don't count against our delim
#             if buffer[offset] == "\\":
#                 partial += buffer[offset]
# 
#                 # record the character and move passed it since it can't
#                 # be taken into account when checking the delim because it
#                 # is escaped
#                 offset += 1
#                 partial += buffer[offset]
# 
#                 offset += 1
# 
#             found = False
#             for delim, delim_len in delims.items():
#                 st = buffer[offset:offset + delim_len]
# 
#                 if st == delim:
#                     found = True
# 
#                     if include_delim:
#                         partial += st
#                         offset += delim_len
# 
#                     break
# 
#             if found:
#                 break
# 
#             else:
#                 partial += buffer[offset]
#                 offset += 1
# 
#         self.seek(offset)
#         return partial

#     def read_until(self, **kwargs):
#         """Scans and returns string up to and including delims or chars
# 
#         :param **kwargs: see ._read_kwargs()
#         :returns: str, returns the string that includes the found sentinel value
#         """
#         delims, chars = self._read_kwargs(**kwargs)
#         count = kwargs.get("count", 1)
# 
#         partial = ""
#         for _ in range(count):
#             if delims:
#                 partial += self.read_to(delims=delims)
#                 partial += self.read_thru_delims(delims)
#                 #partial += self.read_to(delim=delim)
#                 #partial += self.read(len(delim))
# 
#             elif chars:
#                 partial += self.read_to(chars=chars) + self.read(1)
# 
#         return partial


    def read_thru(self, **kwargs):
        """Scans and returns string that only include delims or chars

        :param **kwargs: see ._read_kwargs()
        :returns: str, returns the string that only includes the found sentinel
            value
        """
        delims = self._normalize_delims(**kwargs)
        delims.update(self._normalize_delims(prefix="start_", **kwargs))
        include_delim = self._normalize_include_delim(True, **kwargs)

        partial, delim, delim_len = self._read_thru_delim(delims)

        self.skip(delim_len)

        if not include_delim:
            partial = ""

        return partial


#     def read_thru(self, **kwargs):
#         """Scans and returns string that only include delims or chars
# 
#         :param **kwargs: see ._read_kwargs()
#         :returns: str, returns the string that only includes the found sentinel
#             value
#         """
#         partial = ""
# 
#         delims = self._normalize_delims(**kwargs)
#         delims.update(self._normalize_delims(prefix="start_", **kwargs))
#         include_delim = self._normalize_include_delim(True, **kwargs)
# 
#         buffer = self.getvalue()
#         offset = self.tell()
# 
#         start = self.tell()
#         for delim, delim_len in delims.items():
#             stop = offset + delim_len
#             partial = buffer[offset:stop]
#             if partial == delim:
#                 self.seek(stop)
#                 break
# 
#             else:
#                 partial = ""
# 
#         return partial if include_delim else ""

    def _endswith_delim(self, partial, delims):
        for delim in delims:
            if partial.endswith(delim):
                return True

        return False

    def read_between(self, **kwargs):
        """Reads thru start_delim until stop_delim taking into account sub
        strings that also might contain start_delim and stop_delim

        :Example:
            s = Scanner("(foo (bar (che))) baz")
            s.read_balanced_delims("(", ")") # "(foo (bar (che)))"
            s.read_balanced_delims("(", ")", strip=True) # "foo (bar (che))"

        :param start_delim: str, the starting deliminator
        :param stop_delim: str, the ending deliminator
        :param **kwargs:
            * strip: bool, defaults to False and will strip the top level
                delims, so by default only the inside of the read value gets
                returned, the value between start and stop delims
        :returns: str, the found matching sub string
        """
        all_delims = self._normalize_delims(**kwargs)
        start_delims = {
            **all_delims,
            **self._normalize_delims(prefix="start_", **kwargs)
        }
        stop_delims = {
            **all_delims,
            **self._normalize_delims(prefix="stop_", **kwargs)
        }
        include_delim = self._normalize_include_delim(True, **kwargs)

        partial, delim, delim_len = self._read_thru_delim(start_delims)
        self.skip(delim_len)

        if delim:
            if not include_delim:
                partial = ""

            if delim in stop_delims:
                offset = self.tell()
                offset_delim_len = 0

                while delim:
                    p, delim, delim_len = self._read_to_delim(stop_delims)
                    if delim:
                        partial += p
                        partial += delim

                        self.skip(delim_len)

                        offset = self.tell()
                        offset_delim_len = delim_len

                    else:
                        self.seek(offset)

                if not include_delim and offset_delim_len > 0:
                    partial = partial[:-1 * offset_delim_len]

            else:
                all_delims = {**start_delims, **stop_delims}
                count = 1
                while count > 0:
                    p, delim, delim_len = self._read_to_delim(all_delims)
                    if delim:
                        partial += p

                        if delim in start_delims:
                            count += 1
                            partial += delim
                            self.skip(delim_len)

                        elif delim in stop_delims:
                            count -= 1

                            if count == 0:
                                if include_delim:
                                    partial += delim

                                self.skip(delim_len)

                            else:
                                partial += delim
                                self.skip(delim_len)


                    else:
                        # we've reached the end of the buffer
                        partial += p
                        break

        return partial

#     def read_between(self, **kwargs):
#         """Reads thru start_delim until stop_delim taking into account sub
#         strings that also might contain start_delim and stop_delim
# 
#         :Example:
#             s = Scanner("(foo (bar (che))) baz")
#             s.read_balanced_delims("(", ")") # "(foo (bar (che)))"
#             s.read_balanced_delims("(", ")", strip=True) # "foo (bar (che))"
# 
#         :param start_delim: str, the starting deliminator
#         :param stop_delim: str, the ending deliminator
#         :param **kwargs:
#             * strip: bool, defaults to False and will strip the top level
#                 delims, so by default only the inside of the read value gets
#                 returned, the value between start and stop delims
#         :returns: str, the found matching sub string
#         """
#         start_delims = self._normalize_delims(prefix="start_", **kwargs)
#         stop_delims = self._normalize_delims(prefix="stop_", **kwargs)
#         include_delim = self._normalize_include_delim(True, **kwargs)
# 
#         partial = self.read_thru(
#             start_delims=start_delims,
#             include_delim=include_delim
#         )
# 
#         if partial:
#             if start_delim == stop_delim:
#                 p = partial
#                 while p.endswith(start_delim):
#                     p = self.read_until(delims=[start_delim])
#                     if p.endswith(start_delim):
#                         partial += p
# 
#             else:
#                 count = 1
#                 while count > 0:
#                     partial += self.read_until(delims=[start_delim, stop_delim])
#                     if partial.endswith(start_delim):
#                         count += 1
# 
#                     elif partial.endswith(stop_delim):
#                         count -= 1
# 
#             if kwargs.get("strip", False):
#                 partial = partial[len(start_delim):-len(stop_delim)]
# 
#         return partial

    def __bool__(self):
        return self.peek() != ""
        #return self.tell() < self.__len__()

    def __len__(self):
        return len(self.getvalue())

