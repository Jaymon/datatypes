# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import shlex
from collections import defaultdict

from .compat import *
from .string import String, NormalizeString


class ArgvParser(dict):
    """Parses what is contained in sys.argv or the extra list of argparse.parse_known_args()

    :Example:
        d = ArgvParser([
            "--foo=1",
            "--bar",
            "che"
        ])
        print(d["foo"]) # ["1"]
        print(d["bar"]) # ["che"]
    """
    def __init__(self, argv, **kwargs):
        """
        :param argv: list<str>, the argv list or the extra args returned from parse_known_args
            https://docs.python.org/3/library/sys.html#sys.argv
            https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.parse_known_args
        :param **kwargs: passed through to .normalize_* methods
        :returns: dict, key is the arg name (* for non positional args) and value is
            a list of found arguments (so --foo 1 --foo 2 is supported). The value is
            always a list of strings
        """
        d = defaultdict(list)
        i = 0
        length = len(argv)
        while i < length:
            argv[i] = String(argv[i])
            if argv[i].startswith("-"):
                s = argv[i].lstrip("-")
                bits = s.split("=", 1)
                if len(bits) > 1:
                    key = self.normalize_key(
                        bits[0],
                        **kwargs
                    )
                    val = self.normalize_value(
                        bits[1].strip("\"'"),
                        **kwargs
                    )

                    d[key].append(val)

                else:
                    s = self.normalize_key(s, **kwargs)

                    if i + 1 < length:
                        argv[i + 1] = String(argv[i + 1])
                        if argv[i + 1].startswith("-"):
                            val = self.normalize_value(True, **kwargs)
                            d[s].append(val)

                        else:
                            val = self.normalize_value(argv[i + 1], **kwargs)
                            d[s].append(val)
                            i += 1

                    else:
                        # the last flag is a boolean flag
                        val = self.normalize_value(True, **kwargs)
                        d[s].append(val)

            else:
                d["*"].append(argv[i])

            i += 1

        super().__init__(d)

    def normalize_key(self, k, **kwargs):
        """Normalize the key

        :param **kwargs:
            * hyphen_to_underscore: bool, convert hyphens to underscores (eg, 
                foo-bar becomes foo_bar)
        :returns: str, the normalized key
        """
        htu = kwargs.get("hyphen_to_underscore", False)
        if htu:
            k = k.replace("-", "_")
        return k

    def normalize_value(self, v, **kwargs):
        """normalize the value"""
        return v

    def unwrap(self, ignore_keys=None):
        """remove list wrapper of any value that has a count of 1

        by default, this returns lists for everything because it has no idea what
        might have multiple values so it treats everything as if it has multiple values
        so it can support things like `--foo=1 --foo=2` but that might not be wanted,
        so this method will return a dict with any value that has a length of one it
        will remove the list, so `[1]` becomes `1`

        UnknownParse always has array values, let's normalize that so values
        with only one item contain just that item instead of a list of length 1

        :param ignore_keys: list, keys you don't want to strip of the list even if
            it only has one element
        :returns: dict, a dictionary with values unrwapped
        """
        ignore_keys = set(ignore_keys or [])
        ignore_keys.add("*")

        d = {}
        for k in (k for k in self if (len(self[k]) == 1) and k not in ignore_keys):
            d[k] = self[k][0]
        return d


class ArgParser(ArgvParser):
    """Takes a command line string of shell arguments and splits them and converts
    them to a usable state

    :Example:
        d = ArgumentParser("--foo=1 --bar 'che'")
        print(d["foo"]) # ["1"]
        print(d["bar"]) # ["che"]

    all values will be lists, this is for uniformity, if you want to squash lists
    that only contain one value to just have the value then call .unwrap()

    References:
        * https://stackoverflow.com/questions/44945815/
    """
    def __init__(self, argline, **kwargs):
        """
        :param argline: str, the arguments string that should be parsed
        """
        # https://docs.python.org/3/library/shlex.html#shlex.split
        argv = shlex.split(argline)
        super().__init__(argv, **kwargs)


class Version(NormalizeString):
    """This is a lightweight quick and dirty version parser, it is not trying
    to replace the one in setuptools and is not PEP440 compliant

    https://peps.python.org/pep-0440/
    https://stackoverflow.com/a/11887885/5006
    """
    @classmethod
    def instance_normalize(cls, instance, **kwargs):
        parts = []
        for part in instance.split("."):
            if part.isdigit():
                parts.append(int(part))

            else:
                parts.append(part)

        instance.parts = parts
        return instance

    def __eq__(self, other):
        ov = type(self)(other)
        for i, part in enumerate(self.parts):
            if i >= len(ov.parts):
                return False

            elif part != ov.parts[i]:
                if part == "*" or ov.parts[i] == "*":
                    pass

                else:
                    return False

        return True

    def __ne__(self, other):
        return not (self == other)

    def __ge__(self, other):
        return self == other or self > other

    def __gt__(self, other):
        return not (self == other) and not (self < other)

    def __le__(self, other):
        return self == other or self < other

    def __lt__(self, other):
        ov = type(self)(other)
        for i, part in enumerate(self.parts):
            #pout.v(part, ov.parts[i])
            if i >= len(ov.parts):
                return False

            else:
                if isinstance(part, int) and isinstance(ov.parts[i], int):
                    if part > ov.parts[i]:
                        return False

                    elif part < ov.parts[i]:
                        return True

                elif isinstance(part, int) and isinstance(ov.parts[i], str):
                    if ov.parts[i].startswith(str(part)):
                        return True

                    elif ov.parts[i] == "*":
                        pass

                    else:
                        return False

                elif isinstance(part, str) and isinstance(ov.parts[i], int):
                    if part.startswith(str(ov.parts[i])):
                        return False

                    elif part == "*":
                        pass

                    else:
                        if part[0].isdigit():
                            return part < str(ov.parts[i])

                        else:
                            return True

                elif isinstance(part, str) and isinstance(ov.parts[i], str):
                    if part > ov.parts[i]:
                        return False

                    elif part == "*" or ov.parts[i] == "*":
                        pass

                    elif part < ov.parts[i]:
                        return True

        if len(self.parts) < len(ov.parts):
            return True

        return False

