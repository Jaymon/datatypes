# -*- coding: utf-8 -*-
from enum import Enum as BaseEnum, EnumMeta as BaseEnumMeta

from .compat import *
from .string import String


def convert_value_to_name(enum_class, value):
    """Given a value find the name

    :param enum_class: Enum, the enum class we'll check for value to find name
    :param value: Any, the enum value
    :returns: str, the name of the enum property
    """
    found = False
    for k, v in enum_class.__members__.items():
        if v.value == value:
            name = k
            found = True
            break

    if not found:
        raise ValueError(
            "Value {} is not a valid enumerated value".format(value)
        )

    return name


def convert_name_to_value(enum_class, name):
    """Given a name find the value

    :param enum_class: Enum, the enum class we'll check for name to find value
    :param name: str, the enum name
    :returns: Any, the enum property value
    """
    try:
        value = enum_class.__getitem__(name).value

    except KeyError as e:
        if isinstance(name, enum_class):
            value = name.value

        else:
            raise ValueError(
                f"{name} is not a member of {enum_class.__name__}"
            ) from e

    return value


def find_enum(enum_class, name_or_value):
    """Given a name or a value find the actual enum property that matches

    :param enum_class: Enum, the enum class we'll find the property on
    :param name_or_value: Any, a name, value, or enum property
    :returns: Enum, the enum property with .name and .value properties
    """
    if isinstance(name_or_value, enum_class):
        name = name_or_value.name

    else:
        try:
            convert_name_to_value(enum_class, name_or_value)
            name = name_or_value

        except ValueError:
            try:
                name = convert_value_to_name(enum_class, name_or_value)

            except ValueError:
                # if we have a string then check upper and lower names to see
                # if we can find a match
                if isinstance(name_or_value, basestring):
                    found = False
                    for name in [name_or_value.upper(), name_or_value.lower()]:
                        try:
                            convert_name_to_value(enum_class, name)
                            found = True
                            break

                        except ValueError:
                            pass

                    if not found:
                        raise ValueError("Could not find the enum")

    return enum_class[name]


def find_name(enum_class, name):
    """find the name of an enum, case-insensitive

    :param enum_class: Enum, the enum class we'll check for name
    :param name: str
    :returns: str, the name of the enum property
    """
    return find_enum(enum_class, name).name


def find_value(enum_class, value):
    """find the value of an enum, similar to find_name() this will normalize
    the name or value and return the found value

    :param value: Any, an enum value or name
    :returns value: Any, the value normalized
    """
    return find_enum(enum_class, value).value


class EnumMeta(BaseEnumMeta):
    def __contains__(cls, k):
        """
        https://docs.python.org/3/library/enum.html#enum.EnumType.__contains__
        """
        if isinstance(k, cls):
            return super().__contains__(k)

        else:
            # "FOO" in Enum is deprecated behavior in py3.8, this restores it,
            # but it might actually be back in 3.12+
            return k in cls.__dict__


# Order matters for the parent classes
# https://docs.python.org/3/library/enum.html#restricted-enum-subclassing
class Enum(BaseEnum, metaclass=EnumMeta):
    @classmethod
    def find_name(cls, name):
        return find_name(cls, name)

    @classmethod
    def find_value(cls, value):
        return find_value(cls, value)

    @classmethod
    def find_enum(cls, name_or_value):
        return find_enum(cls, name_or_value)

    @classmethod
    def todict(cls):
        """return all the enum values with names as key and integer values"""
        d = {}
        for k, v in cls.__members__.items():
            d[String(k)] = v.value
        return d

    @classmethod
    def names(cls):
        """return all the ENUM names"""
        return cls.todict().keys()

    @classmethod
    def values(cls):
        """return all the enum values"""
        return cls.todict().values()

    def __int__(self):
        return self.value

    def __eq__(self, other):
        try:
            if isinstance(other, int):
                ret = other == self.value

            elif isinstance(other, basestring):
                ret = other == self.name

            else:
                ret = other.value == self.value

        except (AttributeError, TypeError):
            ret = False

        return ret

