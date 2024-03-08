# -*- coding: utf-8 -*-
from configparser import ConfigParser, ExtendedInterpolation
import re

from ..compat import *


class ConfigInterpolation(ExtendedInterpolation):
    """Internal class used by Config

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
    """Parse a configuration file

    :Example:
        c = Config("<PATH-TO-CONFIG-FILE>")
        c["<SECTION-NAME>"]["<VALUE>"]

    https://docs.python.org/3/library/configparser.html
    """
    def __init__(self, path, **kwargs):
        from ..path import Filepath # avoid circular dependency
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

