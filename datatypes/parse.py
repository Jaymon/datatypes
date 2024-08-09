# -*- coding: utf-8 -*-
import re
import shlex
from collections import defaultdict

from datatypes import Boolean

from .compat import *
from .string import String, NormalizeString
from .token.abnf import ABNFGrammar, ABNFDefinition
from .token.base import Scanner


class ArgvParser(dict):
    """Parses what is contained in sys.argv or the extra list of
    argparse.parse_known_args()

    :Example:
        d = ArgvParser([
            "--foo=1",
            "--bar",
            "che"
        ])
        print(d["foo"]) # ["1"]
        print(d["bar"]) # ["che"]
        print(d.info["foo"]) # prints info about foo key
    """
    def __init__(self, argv, **kwargs):
        """
        :param argv: list<str>, the argv list or the extra args returned from
            parse_known_args
            https://docs.python.org/3/library/sys.html#sys.argv
            https://docs.python.org/3/library/argparse.html#argparse.ArgumentParser.parse_known_args
        :param **kwargs: passed through to .normalize_* methods
            - var_positional: str, defaults to "*", this is the name for the
                found positional values
        :returns: dict[str, list[str]], key is the arg name (* for non
            positional args) and value is a list of found arguments (so --foo 1
            --foo 2 is supported). The value is always a list of strings
        """
        self.info = defaultdict(lambda: {"arg_strings": [], "indexes": []})
        d = defaultdict(list)
        self.positional_name = kwargs.get("var_positional", "*")
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
                        key,
                        bits[1].strip("\"'"),
                        **kwargs
                    )

                    d[key].append(val)

                    self.info[key]["arg_strings"].append(argv[i])
                    self.info[key]["indexes"].append(i)

                else:
                    s = self.normalize_key(s, **kwargs)

                    if i + 1 < length:
                        argv[i + 1] = String(argv[i + 1])
                        if argv[i + 1].startswith("-"):
                            val = self.normalize_value(s, True, **kwargs)
                            d[s].append(val)

                            self.info[s]["arg_strings"].append(argv[i])
                            self.info[s]["indexes"].append(i)

                        else:
                            val = self.normalize_value(
                                s,
                                argv[i + 1],
                                **kwargs
                            )
                            d[s].append(val)

                            self.info[s]["arg_strings"].extend([
                                argv[i],
                                argv[i+1]
                            ])
                            self.info[s]["indexes"].extend([i, i + 1])

                            i += 1

                    else:
                        # the last flag is a boolean flag
                        val = self.normalize_value(s, True, **kwargs)
                        d[s].append(val)

                        self.info[s]["arg_strings"].append(argv[i])
                        self.info[s]["indexes"].append(i)

            else:
                val = self.normalize_value(
                    self.positional_name,
                    argv[i],
                    **kwargs
                )
                d[self.positional_name].append(val)

                self.info[self.positional_name]["arg_strings"].append(argv[i])
                self.info[self.positional_name]["indexes"].append(i)

            i += 1

        super().__init__(d)

    def normalize_key(self, k, **kwargs):
        """Normalize the key

        :param **kwargs:
            * hyphen_to_underscore: bool, convert hyphens to underscores (eg, 
                foo-bar becomes foo_bar)
        :returns: str, the normalized key
        """
        if kwargs.get("hyphen_to_underscore", False):
            k = k.replace("-", "_")

        return k

    def normalize_value(self, k, v, **kwargs):
        """normalize the value

        :param k: str, the key for value v
        :param v: Any, the found value at key k
        :param **kwargs:
            * types: dict[str, type], the key should correspond to k and the
                value is the type that will be called with v (eg types[k](v))
            * infer_types: bool, if True and v is a string then there will
                be some light inference performed on v to see if the type is
                easily identifiable and if it is then v will be converted to
                the inferred type
        """
        inferred = False

        if types := kwargs.get("types", {}):
            if k in types:
                inferred = True
                v = types[k](v)

        if not inferred and kwargs.get("infer_types", False):
            if isinstance(v, str):
                if v.isdecimal():
                    v = int(v)

                elif re.match(r"^\d+\.\d+$", v):
                    v = float(v)

                elif Boolean.isbool(v):
                    v = Boolean(v)

        return v

    def positionals(self):
        """Return all the found positionals as a list

        :returns: list[Any]
        """
        return self.get(self.positional_name, [])

    def keywords(self):
        """Return all the found keywords/optionals

        :returns: dict[str, list[Any]]
        """
        d = {}

        for k, v in self.items():
            if k != self.positional_name:
                d[k] = v

        return d

    def optionals(self):
        return self.keywords()

    def unwrap_keywords(self, ignore_keys=None):
        """remove list wrapper of any value that has a count of 1

        by default, this returns lists for everything because it has no idea
        what might have multiple values so it treats everything as if it has
        multiple values so it can support things like `--foo=1 --foo=2` but
        that might not be wanted, so this method will return a dict with any
        value that has a length of one it will remove the list, so `[1]`
        becomes `1`

        this always has array values, let's normalize that so values
        with only one item contain just that item instead of a list of length 1

        :param ignore_keys: list, keys you don't want to strip of the list even
            if it only has one element
        :returns: dict[str, list|Any], a dictionary with values unrwapped
        """
        ignore_keys = set(ignore_keys or [])
        ignore_keys.add(self.positional_name)

        d = {}
        for k, v in self.items():
            if k not in ignore_keys:
                if len(v) == 1:
                    d[k] = v[0]

                else:
                    d[k] = v

        return d

    def unwrap_optionals(self, ignore_keys=None):
        return self.unwrap_keywords(ignore_keys=ignore_keys)


class ArgParser(ArgvParser):
    """Takes a command line string of shell arguments and splits them and
    converts them to a usable state

    :Example:
        d = ArgumentParser("--foo=1 --bar 'che boo'")
        print(d["foo"]) # ["1"]
        print(d["bar"]) # ["che boo"]

    all values will be lists, this is for uniformity, if you want to squash
    lists that only contain one value to just have the value then call
    .unwrap()

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
    def after_create(cls, instance, **kwargs):
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

