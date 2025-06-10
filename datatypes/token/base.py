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
    """Contains the most common methods a child class should implement.

    You don't directly extend this class, you would instead extend
    Tokenizer
    """
    def next(self):
        """Return the next token

        This is responsible for creating the Token instance

        :returns: Token
        """
        raise NotImplementedError()

    def prev(self):
        """Return the previous token

        This is responsible for creating the Token instance

        :returns: Token
        """
        raise io.UnsupportedOperation()


class BaseTokenizer(TokenizerABC):
    """Basically an io.IOBase wrapper, implementing all the functionality of
    a feature complete io stream
    """
    def __init__(self, buffer):
        """
        :param buffer: str|io.IOBase, this is the input that will be tokenized,
            the buffer has to be seekable by default and will be set to
            `.buffer` using `.set_buffer` so children can customize the buffer
            there
        """
        self.set_buffer(buffer)

    def set_buffer(self, buffer):
        if isinstance(buffer, basestring):
            buffer = io.StringIO(String(buffer))

        self.buffer = buffer

        if not self.seekable():
            raise ValueError("buffer is not seekable")

    def __iter__(self):
        self.seek(0)
        return self

    def __next__(self):
        token = self.next()
        if token is None or token == "":
            raise StopIteration()

        return token

    def getvalue(self):
        """mimics `StringIO.getvalue`"""
        with self.temporary() as fp:
            return fp.read()

    def fileno(self):
        """
        https://docs.python.org/3/library/io.html#io.IOBase.fileno
        """
        return self.buffer.fileno()

    def readable(self):
        return self.buffer.readable()

    def writeable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.writable"""
        return False

    def skip(self, count):
        """Skip ahead count characters"""
        # I wanted to use `self.seek(count, SEEK_CUR)` but certain buffers
        # give this error: "OSError: Can't do nonzero cur-relative seeks
        return self.seek(self.tell() + count)
        #return self.seek(count, SEEK_CUR)

    def peek(self, count=1):
        """Return the next token but don't increment the cursor offset"""
        with self.temporary() as it:
            try:
                return it.read(count)

            except StopIteration:
                pass

    def tell(self):
        """Return the starting position of the current token but don't
        increment the cursor offset"""
        return self.buffer.tell()

    def seek(self, offset, whence=SEEK_SET):
        """Change to the token given by offset and calculated according to the
        whence value

        Change the token position to the given offset. offset is
        interpreted relative to the position indicated by whence.

        The default value for whence is SEEK_SET. Values for whence are:

            * SEEK_SET or 0 – start of the tokens (the default); offset should
                be zero or positive
                https://docs.python.org/3/library/os.html#os.SEEK_SET
            * SEEK_CUR or 1 – current token position; offset may be negative
                https://docs.python.org/3/library/os.html#os.SEEK_CUR
            * SEEK_END or 2 – end of the tokens; offset is usually negative
                https://docs.python.org/3/library/os.html#os.SEEK_END

        Return the new absolute buffer position.

        https://docs.python.org/3/library/io.html#io.IOBase.seek

        :param offset: int, the token to seek to
        :returns: int, the starting position in the buffer of the token
        """
        return self.buffer.seek(offset, whence)

    def seekable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.seekable"""
        return self.buffer.seekable()

    @contextmanager
    def transaction(self):
        """If an error is raised reset the cursor back to where the
        transaction was started, if no error is raised then keep the cursor
        at current position"""
        start = self.buffer.tell()
        try:
            yield self

        except Exception as e:
            self.buffer.seek(start)
            raise

    @contextmanager
    def temporary(self):
        """similar to `.transaction()` but will always discard anything read
        and reset the cursor back to where it started, you use this because
        you want to check some tokens ephemerally"""
        start = self.buffer.tell()
        try:
            yield self

        finally:
            self.buffer.seek(start)

    def __bool__(self):
        return True if self.peek() else False

    def close(self, *args, **kwargs):
        raise io.UnsupportedOperation()

    def closed(self, *args, **kwargs):
        return self.buffer.closed()

    def get_slice(self, start_offset, stop_offset):
        """Reads a slice of the buffer starting at `start_offset` and ending
        at `stop_offset`

        This uses `.temporary()` to not mess with the index pointer

        :param start_offset: int, where to start in the buffer
        :param stop_offset: int, where to stop in the buffer
        :returns: str, the read tokens in the buffer from start to stop offset
        """
        with self.temporary() as fp:
            fp.seek(start_offset)
            return fp.read(stop_offset - start_offset)

    def read(self, size=-1):
        """Read count tokens and return them

        https://docs.python.org/3/library/io.html#io.IOBase
            Even though IOBase does not declare read() or write() because their
            signatures will vary, implementations and clients should consider
            those methods part of the interface.

        :param count: int, if >0 then return count tokens, if -1 then return
            all remaining tokens
        :returns: str, the read tokens as a substring
        """
        return self.buffer.read(size)

    def readline(self, size=-1):
        """
        https://docs.python.org/3/library/io.html#io.IOBase.readline
        """
        return self.buffer.readline(size)

    def readlines(self, hint=-1):
        """
        https://docs.python.org/3/library/io.html#io.IOBase.readlines
        """
        return self.buffer.readlines(hint)


class Tokenizer(BaseTokenizer):
    """The base class for building a tokenizer

    A Tokenizer class acts like an IO object but returns tokens instead of
    strings and all read operations return Token instances and all setting
    operations manipulate positions according to tokens. You can see this
    by looking at `.read()`, it returns an array of tokens instead of a string
    like a normal io stream would.

    To create a custom Tokenizer, you usually would extend 2 classes:
        * Token
        * Tokenizer

    A custom Tokenizer will usually set the `.token_class` property to the
    new custom `Token` class and implement the `.next()` method

    .. Example:
        from datatypes.token import Token, Tokenizer

        class MyToken(Token):
            # customize this class based on needs
            pass

        class MyTokenizer(Tokenizer):
            token_class = MyToken

            def next(self):
                return self.token_class(self)

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

    def peek(self, count=1):
        """Return the next token but don't increment the cursor offset"""
        tokens = super().peek(count)
        if tokens:
            return tokens if count > 1 else tokens[0]

    def tell(self):
        """Return the starting position of the current token but don't
        increment the cursor offset"""
        t = self.peek()
        return t.start if t else self.buffer.tell() 

    def read(self, count=-1):
        """Read count tokens and return them

        :param count: int, if >0 then return count tokens, if -1 then return
            all remaining tokens
        :returns: list, the read Token instances
        """
        ret = []
        while count < 0 or count > 0:
            try:
                ret.append(self.next())

            except StopIteration:
                break

            else:
                count -= 1

        return ret

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

    def readline(self, size=-1):
        raise io.UnsupportedOperation()

    def readlines(self, hint=-1):
        raise io.UnsupportedOperation()


class Scanner(BaseTokenizer):
    """Python implementation of an Obj-c Scanner

    This is really handy to build arbitrary parsers and tokenizers

    There are 3 keywords you need to know to use this class effectively:

        * to - read anything up to and including the sentinel depending on the
            passed in flags
        * thru - read only the sentinel values and nothing else, the return
            will be empty if no sentinel values were found
        * between - read between two sentinel values

    There are 2 main sentinel value types:

        * delims - a list of arbitrary length strings that will be checked
            (ie, `delims=["foo", "bar"]` will check for the sentinels "foo"
            and "bar" and will keep going until "foo" or "bar" are encountered
            in total)
        * chars - a set of single characters to be checked (ie, `chars="abc"`
            will check for character "a", "b", and "c" separately and if any
            one of those matches the sentinel is considered found)

    :Example:
        s = Scanner("before [[che baz]] middle [[foo]] after")
        s.read_to(delim="[[") # "before "
        s.read_to(delim="]]", include_delim=True) # "[[che baz]]"
        s.read_to(delim="[[") # " middle "
        s.read_between(start_delim="[[", stop_delim="]]") # "[[foo]]"
        s.readline() # " after"

    Moved from bang.utils on 1-6-2023

    * https://developer.apple.com/documentation/foundation/nsscanner
    * https://docs.python.org/3/library/io.html#io.StringIO
    * https://docs.python.org/3/library/io.html#io.TextIOWrapper
    """
    def __init__(self, buffer, convert_escaped=False, escape_char="\\"):
        r"""
        :param buffer: str|io.IOBytes
        :param convert_escaped: bool, True if the `escape_char` should be
            removed from the returned text (eg, "foo$bar" would be returned
            for buffer "foo\$bar")
        :param escape_char: str, the escape character, it has to be one
            character and probably shouldn't ever be changed from its
            default backslash
        """
        self.convert_escaped = convert_escaped
        self.escape_char = escape_char

        super().__init__(buffer)

    def next(self):
        return self.readline()

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

        if kwargs.get(
            f"{prefix}newline",
            kwargs.get(
                f"{prefix}vspace",
                kwargs.get(f"{prefix}vertical_space", False)
            )
        ):
            #delims["\r\n"] = 2
            delims["\n"] = 1
            #delims["\r"] = 1

        return delims

    def _normalize_ignore_delims(self, **kwargs):
        """Find the delims used to ignore the sentinel delims.

        When you are searching for delims you might want to ignore them
        when they are between other delims, this figures out what delims
        should trigger ignoring the sentinel delims

        It uses all the same keywords as `._normalize_delims()` with the
        following prefixes:
            * ignore_between_
            * ignore_between_start
            * ignore_between_stop
        """
        ignore_delims = self._normalize_delims(
            prefix="ignore_between_",
            **kwargs
        )
        ignore_start_delims = {
            **ignore_delims,
            **self._normalize_delims(
                prefix="ignore_between_start_",
                **kwargs
            )
        }
        ignore_stop_delims = {
            **ignore_delims,
            **self._normalize_delims(
                prefix="ignore_between_stop_",
                **kwargs
            )
        }

        return ignore_start_delims, ignore_stop_delims

    def _normalize_include_delim(self, default=False, **kwargs):
        """Find the passed in flag to include delims, default to `default` if
        not found

        :param default: bool, the default `include_delim` value
        :keyword include_delim: bool, this key or one of the variations will
            be checked
        :returns: bool
        """
        for k in ["include_delim", "include_delims", "include"]:
            if k in kwargs:
                return kwargs[k]

        return default

    def _read_to_delim(self, delims):
        """Internal method. Reads to the found delim in `delims`

        :param delims: dict[str, int], the returned value from
            `._normalize_delims`
        :returns: tuple[str, str, int], returns the found stubstring, the
            matched delim, and the length of the matched delim
        """
        partial = ""

        while True:
            offset = self.tell()
            char = self.buffer.read(1)
            delim = ""
            delim_len = 0

            if char == "":
                # we've reached eof
                break

            elif char == self.escape_char:
                # escaped characters don't count against our delim

                if not self.convert_escaped:
                    partial += char

                # record the character and move passed it since it can't
                # be taken into account when checking the delim because it
                # is escaped
                partial += self.buffer.read(1)
                offset = self.tell()
                char = self.buffer.read(1)

            found = False

            for delim, delim_len in delims.items():
                token = char + self.buffer.read(delim_len - 1)

                self.seek(offset)
                char = self.buffer.read(1)

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

        return partial, delim, delim_len

    def _read_thru_delim(self, delims):
        """Internal method. Reads through the found delim in `delims`

        :param delims: dict[str, int], the returned value from
            `._normalize_delims`
        :returns: tuple[str, str, int], returns the found stubstring, the
            matched delim, and the length of the matched delim
        """
        partial = ""
        offset = self.tell()

        found = False

        for delim, delim_len in delims.items():
            partial = self.buffer.read(delim_len)
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

    def _read_thru_delims(self, delims):
        """Internal method. Reads through all the found delims in delims,
        this is basically a wrapper around `._read_thru_delim` and is what
        is called by `.read_thru`

        :param delims: dict[str, int], the returned value from
            `._normalize_delims`
        :returns: tuple[str, str, int], returns the found substring, the
            matched delims (basically a concatenated string of all the matched
            delims, and the length of all the matched delims
        """
        partial = ""
        partial_delims = ""
        partial_delims_len = 0

        while True:
            p, delim, delim_len = self._read_thru_delim(delims)
            if delim:
                partial += p
                partial_delims += delim
                partial_delims_len += delim_len
                self.skip(delim_len)

            else:
                break

        return partial, partial_delims, partial_delims_len

    def read_to(self, **kwargs):
        """scans and returns string up to but not including the delim unless
        `include_delim=True` is passed in

        .. Example:
            s = Scanner("foo bar [[che baz]]")
            s.read_to(delim="[[") # "foo bar "

        This has roughly the same signature as `.read_thru` and `.read_between`

        :param **kwargs: see `._normalize_delims()` and
            `._normalize_ignore_delims()`
        :keyword include_delim: bool, see ._normalize_include_delim, if this
            is True then the index will be set to after the found delims, if
            False then the index will be set to before the found delims
        :returns: str, returns the matched substring from self.tell() when this
            method was called to self.tell() right before or after the delim
        """
        partial = ""

        delims = self._normalize_delims(**kwargs)
        delims.update(self._normalize_delims(prefix="stop_", **kwargs))
        ignore_delims = self._normalize_ignore_delims(**kwargs)

        all_delims = {
            **delims,
            **ignore_delims[0],
        }

        include_delim = self._normalize_include_delim(False, **kwargs)

        while True:
            p, delim, delim_len = self._read_to_delim(all_delims)

            if delim in ignore_delims[0]:
                p += self.read_between(
                    start_delims=ignore_delims[0],
                    stop_delims=ignore_delims[1],
                    include_delims=True
                )

                partial += p

            else:
                if include_delim and delim_len > 0:
                    p += delim
                    self.skip(delim_len)

                partial += p
                break

        return partial

    def read_thru(self, **kwargs):
        """Scans and returns string that only includes the delims or chars

        This has roughly the same signature as `.read_to` and `.read_between`

        :param **kwargs: see ._normalize_delims
        :keyword include_delim: bool, see ._normalize_include_delim, no
            matter what the value the index will always be set to after the
            found delims
        :returns: str, returns the string that only includes the found
            sentinel value
        """
        partial = ""

        delims = self._normalize_delims(**kwargs)
        delims.update(self._normalize_delims(prefix="start_", **kwargs))
        include_delim = self._normalize_include_delim(True, **kwargs)

        partial, delim, delim_len = self._read_thru_delims(delims)
        if not include_delim:
            partial = ""

        return partial

    def read_between(self, **kwargs):
        """Reads thru start_delim until stop_delim taking into account sub
        strings that also might contain start_delim and stop_delim

        .. Example:
            s = Scanner("(foo (bar (che))) baz")
            s.read_between(
                start_delim="(",
                stop_delim=")"
            ) # "(foo (bar (che)))"
            s.read_between(
                start_delim="(",
                stop_delim=")",
                include_delim=False
            ) # "foo (bar (che))"

        This has roughly the same signature as `.read_to` and `.read_thru`

        :param **kwargs: see `._normalize_delims()` and
            `._normalize_ignore_delims()`
        :keyword start_delim: str, the starting deliminator
        :keyword stop_delim: str, the ending deliminator
        :keyword include_delims: bool, see ._normalize_include_delim, whether
            this is True or False the index will be set to after the found
            final stop delim
        :returns: str, the found matching sub string, with or without the
            wrapping delims depending on the value of `include_delims`
        """
        delims = self._normalize_delims(**kwargs)

        ignore_delims = self._normalize_ignore_delims(**kwargs)

        start_delims = {
            **delims,
            **self._normalize_delims(prefix="start_", **kwargs)
        }
        stop_delims = {
            **delims,
            **ignore_delims[0],
            **self._normalize_delims(prefix="stop_", **kwargs)
        }
        include_delim = self._normalize_include_delim(True, **kwargs)

        offset = self.tell()
        partial, delim, delim_len = self._read_thru_delim(start_delims)
        self.skip(delim_len)

        if delim:
            if not include_delim:
                partial = ""

            if delim in stop_delims:
                offset_delim_len = 0

                p = ""
                while True: # handle ignore_between_* delims
                    sp, delim, delim_len = self._read_to_delim(stop_delims)
                    if delim in ignore_delims[0]:
                        p += sp
                        p += self.read_between(
                            start_delims=ignore_delims[0],
                            stop_delims=ignore_delims[1],
                            include_delims=True
                        )

                    else:
                        p += sp
                        break

                if delim:
                    partial += p

                    if include_delim:
                        partial += delim

                    self.skip(delim_len)

                else:
                    # we couldn't match and we got to the end of the file so
                    # fail
                    partial = ""
                    self.seek(offset)

            else:
                all_delims = {**start_delims, **stop_delims}
                count = 1
                while count > 0:
                    p = ""
                    while True: # handle ignore_between_* delims
                        sp, delim, delim_len = self._read_to_delim(all_delims)
                        if delim in ignore_delims[0]:
                            p += sp
                            p += self.read_between(
                                start_delims=ignore_delims[0],
                                stop_delims=ignore_delims[1],
                                include_delims=True
                            )

                        else:
                            p += sp
                            break

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
                        # we've reached the end of the buffer and we didn't
                        # finish matching so we failed
                        #partial += p
                        partial = ""
                        self.seek(offset)
                        break

        return partial

    def read(self, size=-1):
        """Read `size` consumable characters.

        A consumable character is a character not proceeded with
        `.escape_char`

        :param size: int, how many characters to read
        :returns: str
        """
        if self.convert_escaped:
            s = ""

            while size < 0 or size > 0:
                size -= 1

                char = self.buffer.read(1)

                if char == "":
                    break

                else:
                    if char == self.escape_char:
                        char = self.buffer.read(1)

                    s += char

        else:
            s = self.buffer.read(size)

        return s

    def readline(self, size=-1):
        """Read `size` consumable characters or until encountering a newline

        A consumable character is a character not proceeded with
        `.escape_char`

        :param size: int, how many characters to read
        :returns: str
        """
        if self.convert_escaped:
            s = ""

            while size < 0 or size > 0:
                size -= 1

                char = self.buffer.read(1)

                if char == "":
                    break

                else:
                    if char == self.escape_char:
                        char = self.buffer.read(1)
                        s += char

                    else:
                        s += char
                        if char == "\n":
                            break

        else:
            s = self.buffer.readline(size)

        return s

    def readlines(self, hint=-1):
        raise io.UnsupportedOperation()

