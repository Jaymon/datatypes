# -*- coding: utf-8 -*-
from configparser import ConfigParser, ExtendedInterpolation
from collections import OrderedDict
import re
import functools

from ..compat import *
#from ..path import Filepath, UrlFilepath
#from ..token.abnf import ABNFParser
from ..collections.mapping import Namespace
from ..decorators import classproperty


class ConfigInterpolation(ExtendedInterpolation):
    """
    https://github.com/python/cpython/blob/3.11/Lib/configparser.py#L361
    """
    def before_set_dict(self, parser, section, option, value):
        if parser.path.endswith(".toml"):
            values = []
            for key, val in value.items():
                val = self.before_set_value(parser, section, key, val)
                values.append(f"{key} = {val}")

            return "{" + ", ".join(values) + "}"

        else:
            return value

    def before_get_dict(self, parser, section, option, value, defaults):
        if parser.path.endswith(".toml"):
            d = {}
            regex = r"([a-zA-Z0-9_-]+)\s*=\s*([\"\[\{])"
            for m in re.finditer(regex, value):
                key = m.group(1)
                sentinel = value[m.regs[2][0]:m.regs[2][1]]
                start = m.regs[2][0]
                stop = start + 1
                while value[stop] != sentinel:
                    if value[stop] == "\\":
                        # skip escaped characters
                        stop += 1
                    stop += 1
                stop += 1

                d[key] = self.before_get(
                    parser,
                    section,
                    key,
                    value[start:stop],
                    defaults
                )

            return d

        else:
            return value

    def before_get_str(self, parser, section, option, value, defaults):
        if parser.path.endswith(".toml"):
            return value.strip("\"")

        else:
            return value

    def before_set_str(self, parser, section, option, value):
        if parser.path.endswith(".toml"):
            return f"\"{value}\""

        else:
            return value

    def before_set_list(self, parser, section, option, value):
        if parser.path.endswith(".toml"):
            values = []
            for val in value:
                val = self.before_set_value(parser, section, option, val)
                values.append(f"  {val}")

            return "[\n" + ",\n".join(values) + "\n]"

        else:
            return value

    def before_get_list(self, parser, section, option, value, defaults):
        if parser.path.endswith(".toml"):
            l = []
            cv = value.strip("[]").strip()
            while cv:
                sentinel = cv[0]
                start = 0
                stop = start + 1
                while cv[stop] != sentinel:
                    if cv[stop] == "\\":
                        # skip escaped characters
                        stop += 1
                    stop += 1
                stop += 1

                l.append(self.before_get(
                    parser,
                    section,
                    option,
                    cv[start:stop],
                    defaults
                ))

                cv = cv[stop:].strip(",").strip()

            return l

        else:
            return value

    def before_set_value(self, parser, section, option, value):
        if value is not None:
            if isinstance(value, Mapping):
                value = self.before_set_dict(
                    parser,
                    section,
                    option,
                    value
                )

            elif isinstance(value, str):
                value = self.before_set_str(
                    parser,
                    section,
                    option,
                    value
                )

            elif isinstance(value, Sequence):
                value = self.before_set_list(
                    parser,
                    section,
                    option,
                    value
                )

            else:
                value = str(value)

        return value

    def optionxform(self, parser, optionstr):
        if parser.path.endswith(".toml"):
            return optionstr

        else:
            return optionstr.lower()

    def before_write(self, parser, section, option, value):
        return super().before_write(parser, section, option, value)

    def before_get(self, parser, section, option, value, defaults):
        if value.startswith("{"):
            return self.before_get_dict(
                parser,
                section,
                option,
                value,
                defaults
            )

        elif value.startswith("["):
            return self.before_get_list(
                parser,
                section,
                option,
                value,
                defaults
            )

        elif value.startswith("\""):
            return value.strip("\"")

        else:
            return super().before_get(parser, section, option, value, defaults)

    def before_set(self, parser, section, option, value):
        return super().before_set(parser, section, option, value)

    def before_read(self, parser, section, option, value):
        return super().before_read(parser, section, option, value)


class Config(ConfigParser):
    """
    https://docs.python.org/3/library/configparser.html
    """
    def __init__(self, path, **kwargs):
        self.path = Filepath(path)
        super().__init__(
            interpolation=ConfigInterpolation()
        )

        if self.path.is_file():
            self.read(path)

    def optionxform(self, optionstr):
        """Overrides parent to allow customization of the option value"""
        return self._interpolation.optionxform(self, optionstr)

    def read_dict(self, dictionary, source='<dict>'):
        """Overrides parent to allow customization of the raw value

        I had to copy this whole method body just to change one line because it
        just casts value to str instead of allowing the value to be manipulated
        in ._interpolation.before_set(). Sigh
        """
        elements_added = set()
        for section, keys in dictionary.items():
            section = str(section)
            try:
                self.add_section(section)

            except (DuplicateSectionError, ValueError):
                if self._strict and section in elements_added:
                    raise

            elements_added.add(section)
            for key, value in keys.items():
                key = self.optionxform(str(key))

                # ADDED BY JAY
                value = self._interpolation.before_set_value(
                    self,
                    section,
                    key,
                    value
                )

                if self._strict and (section, key) in elements_added:
                    raise DuplicateOptionError(section, key, source)

                elements_added.add((section, key))
                self.set(section, key, value)

    def write(self):
        with self.path.open("w") as fp:
            super().write(fp)

    def _write_section(self, fp, section_name, section_items, delimiter):
        """Overrides parent to ignore empty sections"""
        if section_items:
            super()._write_section(fp, section_name, section_items, delimiter)

    def jsonable(self):
        d = {}
        for k in self:
            d[k] = dict(self[k])

        return d


class TOML(object):
    """This is more or less a real TOML reader/writer.

    It should parse anything that gets thrown at it because it uses the actual
    TOML ABNF grammar to do the parsing but it can definitely fail on writing,
    but it works for what I am using it for right now (9-1-2023)

    NOTE
        * if you read in a TOML file with comments and write it back out then
          the comments will be gone.
        * Currently .write() only really supports list, dict, str, and int

    https://toml.io/en/
    https://toml.io/en/v1.0.0#abnf-grammar
    https://docs.python.org/3/library/tomllib.html
    https://github.com/python/cpython/blob/3.11/Lib/tomllib/_parser.py
    """
    GRAMMAR_URL = "https://raw.githubusercontent.com/toml-lang/toml/1.0.0/toml.abnf"

    @classproperty
    def parser_class(cls):
        from ..token.abnf import ABNFParser # avoid circular dependency
        return ABNFParser

    #parser_class = ABNFParser

    @functools.cached_property
    def parser(self):
        """Returns an ABNF parser instance, this will be cached"""
        from ..path import UrlFilepath # avoid circular dependency
        fp = UrlFilepath(self.GRAMMAR_URL)
        return self.parser_class(fp.read_text())

    def __init__(self, path, **kwargs):
        from ..path import Filepath # avoid circular dependency
        self.path = Filepath(path)
        self.parse()

    def parse(self):
        """This will parse the TOML file found at self.path"""
        buffer = self.path.read_text() if self.path.is_file() else ""
        self.sections = Namespace()
        self.sections_order = []

        if buffer:
            r = self.parser.toml.parse(buffer)
            section = self.sections

            for exp in r.tokens("expression"):
                has_tables = False
                for table in exp.tokens("table"):
                    has_tables = True
                    keys = self.parse_key(table.values[0].values[1])
                    section = self._add_section(keys)

                if not has_tables:
                    for keyval in exp.tokens("keyval"):
                        key, value = self.parse_keyvalue(keyval)
                        section[key] = value

    def parse_key(self, key):
        keys = []

        for k in key.values[0].values:
            if k.name == "unquoted-key":
                keys.append(str(k))

            elif k.name == "simple-key":
                keys.append(str(k).strip("\""))

        return keys

    def parse_keyvalue(self, keyval):
        key = str(keyval.values[0])
        value = self.parse_value(keyval.values[2].values[0])
        return key, value

    def parse_value(self, value):
        if value.name == "integer":
            return int(str(value))

        elif value.name == "string":
            return str(value)[1:-1]

        elif value.name == "array":
            a = []
            for av in value.tokens("array-values", depth=0):
                for v in av.tokens("val"):
                    a.append(self.parse_value(v.values[0]))

            return a

        elif value.name == "inline-table": # dict
            d = {}
            for dv in value.tokens("inline-table-keyvals", depth=0):
                for kv in dv.tokens("keyval"):
                    k, v = self.parse_keyvalue(kv)
                    d[k] = v

            return d

        else:
            raise NotImplementedError(value.name)

    def __getitem__(self, key):
        try:
            return self.sections[key]

        except KeyError:
            raise

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)

        except KeyError as e:
            raise AttributeError(key) from e

    def add_section(self, section_name):
        """Adds a section/table

        https://toml.io/en/v1.0.0#table

        :param section_name: str, the table name, this can be dotted
        :returns: Namespace, the section namespace
        """
        r = self.parser.key.parse(section_name)
        keys = self.parse_key(r)
        return self._add_section(keys)

    def _add_section(self, keys):
        section = self.sections
        for k in keys:
            if k not in section:
                section.setdefault(k, Namespace())
            section = section[k]

        self.sections_order.append(keys)
        return section

    def get_section_name(self, keys):
        parts = []
        for k in keys:
            if "." in k:
                k = f"\"{k}\""
            parts.append(k)
        return ".".join(parts)

    def get_write_key(self, key):
        if "." in key:
            return f"\"{key}\""

        else:
            return key

    def get_write_value(self, value):
        lines = []
        if value is not None:
            if isinstance(value, Mapping):
                slines = []

                for k, v in value.items():
                    slines.append(f"{k} = {self.get_write_value(v)}")

                lines.append("{ " + ", ".join(slines) + " }")

            elif isinstance(value, str):
                lines.append(f"\"{value}\"")

            elif isinstance(value, Sequence):
                lines.append("[")
                slines = []

                for v in value:
                    slines.append(f"  {self.get_write_value(v)}")

                lines.append(",\n".join(slines))
                lines.append("]")

            elif isinstance(value, bool):
                lines.append("true" if value else "false")

            else:
                lines.append(str(value))

        return "\n".join(lines)

    def write_section(self, fp, section_name, section_items, keyset):
        lines = []
        for k, v in section_items:
            if k not in keyset:
                wk = self.get_write_key(k)
                wv = self.get_write_value(v)
                lines.append(f"{wk} = {wv}\n")

        if lines:
            if section_name:
                fp.write(f"[{section_name}]")
                fp.write("\n")

            for line in lines:
                fp.write(line)

#             for k, v in section_items:
#                 if k not in keyset:
#                     fp.write(f"{k} = {self.get_write_value(v)}")
#                     fp.write("\n")

            fp.write("\n")

    def write(self):
        body = OrderedDict()
        depth = 0

        keysets = {}

        while True:
            keyset = set()
            for skeys in self.sections_order:
                if depth < len(skeys):
                    keyset.add(skeys[depth])

            if keyset:
                keysets[depth] = keyset
                depth += 1

            else:
                break

        with self.path.open("w+") as fp:
            # first thing we need to do is find all the default keys (keys with
            # no table)
            keyset = keysets.get(0, set())
            self.write_section(fp, "", self.sections.items(), keyset)

            for keys in self.sections_order:
                depth = len(keys)
                keyset = keysets.get(depth, set())

                section = self.sections
                for k in keys:
                    section = section[k]

                self.write_section(
                    fp,
                    self.get_section_name(keys),
                    section.items(),
                    keyset
                )

