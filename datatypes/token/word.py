# -*- coding: utf-8 -*-

from ..compat import *
from ..string import String
from .base import Token, Tokenizer


class WordToken(Token):
    """This is what is returned from the Tokenizer and contains pointers to the
    left deliminator and the right deliminator, and also the actual token

        .ldelim - the deliminators to the left of the token
        .text - the actual token value that was found
        .rdelim - the deliminators to the right of the token
    """
    def __init__(self, tokenizer, text, start, stop, ldelim=None, rdelim=None):
        super().__init__(tokenizer, start, stop)
        self.text = text
        self.ldelim = ldelim
        self.rdelim = rdelim

    def __str__(self):
        return self.text

    def __pout__(self):
        """used by pout python external library

        https://github.com/Jaymon/pout
        """
        tokens = (
            '"{}"'.format(self.ldelim.text) if self.ldelim else None,
            '"{}"'.format(self.text),
            '"{}"'.format(self.rdelim.text) if self.rdelim else None,
        )

        return "{} <- {} -> {}".format(tokens[0], tokens[1], tokens[2])


class WordTokenizer(Tokenizer):
    """Tokenize a string finding tokens that are divided by passed in
    characters
    """
    DEFAULT_CHARS = String.WHITESPACE + String.PUNCTUATION
    """If no deliminators are passed into the constructor then use these"""

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
        """Tell the current ldelim start position, this is mainly used
        internally

        :returns: int, the cursor position of the start of the left deliminator
            of the current token
        """
        pos = self.buffer.tell()
        ch = self.buffer.read(1)
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

        return self.normalize(token)

    def prev(self):
        """Returns the previous Token

        :returns: Token, the previous token found in the stream, None if there
            are no previous tokens
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

        if not token:
            raise StopIteration()

        start = token.ldelim.start if token.ldelim else token.start
        self.buffer.seek(start)

        return self.normalize(token)

    def normalize(self, token):
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

