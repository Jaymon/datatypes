# -*- coding: utf-8 -*-
import string

from ...token.base import Tokenizer, Token, Scanner


class EnvironToken(Token):
    """A parsed environ variable name and value

    Fields each instance should have:

        * `.name` - the variable name
        * `.value` - the variable value
        * `.start` - the offset this token's name started
        * `.stop` - the offset this token's value stopped
    """
    def __init__(self, tokenizer, name, value, start, stop):
        super().__init__(tokenizer, start, stop)

        self.name = name
        self.value = value


class EnvironTokenizer(Tokenizer):
    """Parses an environment file buffer and returns the key/value pairs as
    EnvironToken instances

    An environment file is a file that contains NAME=VALUE pairs. It ignores
    all comments starting with the number sign (#)

    .. Example:
        with open("<ENVIRON-FILE-PATH>") as fp:
            ts = EnvironTokenizer(fp, os.environ)
            for t in ts:
                print(t.name, t.value)
    """
    token_class = EnvironToken

    def __init__(self, buffer, environ=None):
        """
        :param buffer: io.IOBase|str
        :param environ: Mapping
        """
        super().__init__(Scanner(buffer))
        self.environ = environ

    def next(self):
        """Get the next environment variable

        :returns: EnvironToken
        """
        token = None
        name = ""
        value = ""

        buffer = self.buffer
        alphanum = string.ascii_letters + string.digits + "_"

        # get the variable name
        while True:
            start = buffer.tell()
            ch = buffer.read(1)

            if ch == "":
                # we've exhausted the buffer
                break

            elif ch == "#":
                # read to the end of the line and discard
                buffer.readline()

            elif ch in string.whitespace:
                buffer.read_thru(whitespace=True)

            elif ch in string.ascii_letters:
                name = ch + buffer.read_thru(chars=alphanum)

                # ignore export statements
                if name == "export":
                    buffer.read_thru(whitespace=True)
                    name = ""

                else:
                    break

            else:
                raise ValueError(
                    f"Not sure what to do with char [{ch}]"
                    " in environ variable name"
                )

        if name:
            equal_sign = buffer.read(1)
            if equal_sign != "=":
                raise ValueError(
                    f"Equal sign [=] was expected but got [{equal_sign}]"
                )

            sentinel = ""
            multiline = False

            while True:
                ch = buffer.read(1)

                if ch == "":
                    # we've exhausted the buffer
                    break

                elif ch == "\\":
                    multiline = True
                    ch = buffer.read(1)

                    if ch in string.whitespace:
                        buffer.read_thru(whitespace=True)
                        if value.endswith(" "):
                            ch = ""

                        else:
                            ch = " "

                    value += ch

                elif ch == "\"" or ch == "'":
                    if sentinel == ch:
                        sentinel = ""

                    else:
                        sentinel = ch

                elif ch == "$":
                    ch = buffer.read(1)
                    if ch == "{":
                        variable_name = buffer.read_to(delim="}")
                        buffer.read_thru(delim="}")

                    else:
                        variable_name = ch + buffer.read_thru(chars=alphanum)

                    if self.environ:
                        value += self.environ.get(variable_name, "")

                elif ch == "#":
                    if sentinel:
                        value += ch

                    else:
                        # ignore the rest of the line since it's a comment
                        buffer.readline()

                        if multiline:
                            buffer.read_thru(whitespace=True)
                            multiline = False

                        else:
                            break

                elif ch == "\n":
                    # we are done grabbing the value
                    break

                else:
                    value += ch

            token = self.token_class(
                self,
                name,
                value,
                start,
                buffer.tell()
            )

        return token

