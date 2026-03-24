"""Enum helper functions

This was originally created to bring Enum support to python2 but that
original use-case is no longer relevant

Some things to know:
    * `EnumType` is the actual Enum defined class when using `isinstance`
    * `Enum` is the type for properties when using `isinstance`

:example:
    import enum

    class Foo(enum.Enum):
        BAR = enum.auto()
        CHE = enum.auto()

    isinstance(Foo, enum.EnumType) # True
    isinstance(Foo, enum.Enum) # False
    issubclass(Foo, enum.Enum) # True
    isinstance(Foo.BAR, enum.EnumType) # False
    isinstance(Foo.BAR, enum.Enum) # True
"""
from enum import Enum, EnumMeta, Flag, EnumType
from typing import Any

from .compat import *
from .string import String


def convert_enum_to_dict(enum_class: EnumType) -> dict[str, Any]:
    """Convert the `enum_class` to a dict with the property names as the
    keys and the values as the enum value"""
    d = {}
    for k, v in enum_class.__members__.items():
        d[String(k)] = v.value

    return d


def convert_value_to_name(enum_class: EnumType, value: Any) -> str:
    """Given a value find the name

    :param enum_class: Enum, the enum class we'll check for value to find name
    :param value: Any, the enum value
    :returns: str, the name of the enum property
    """
#     names = []
#     is_flag = issubclass(enum_class, Flag)
# 
#     for k, v in enum_class.__members__.items():
#         if v.value & value:
#             names.append(k)
#             if not is_flag:
#                 break
# 
#     if not names:
#         raise ValueError(
#             "Value {} is not a valid enumerated value".format(value)
#         )
# 
#     return "|".join(names)

    name = ""

    if issubclass(enum_class, Flag):
        names = []
        for k, v in enum_class.__members__.items():
            if v.value & value:
                names.append(k)

        name = "|".join(names)

    else:
        for k, v in enum_class.__members__.items():
            if v.value == value:
                name = k
                break

    if not name:
        raise ValueError(
            "Value {} is not a valid enumerated value".format(value)
        )

    return name


def convert_name_to_value(enum_class: EnumType, name: str) -> Any:
    """Given a name find the value

    :param enum_class: Enum, the enum class we'll check for name to find value
    :param name: str, the enum name
    :returns: Any, the enum property value
    """
    try:
        if issubclass(enum_class, Flag):
            value = 0
            names = name.split("|")
            for n in names:
                value |= enum_class.__getitem__(n).value

        else:
            value = enum_class.__getitem__(name).value

    except (KeyError, AttributeError) as e:
        raise ValueError(
            f"{name} is not a member of {enum_class.__name__}"
        ) from e


# def convert_name_to_value(enum_class, name):
#     """Given a name find the value
# 
#     :param enum_class: Enum, the enum class we'll check for name to find value
#     :param name: str, the enum name
#     :returns: Any, the enum property value
#     """
#     if isinstance(name, enum_class):
#         value = name.value
# 
#     elif isinstance(name, int):
#         value = name
# 
#     else:
#         try:
#             if issubclass(enum_class, Flag):
#                 value = 0
#                 names = name.split("|")
#                 for n in names:
#                     value |= enum_class.__getitem__(n).value
# 
#             else:
#                 value = enum_class.__getitem__(name).value
# 
#         except KeyError as e:
#             raise ValueError(
#                 f"{name} is not a member of {enum_class.__name__}"
#             ) from e

#         try:
#             value = enum_class.__getitem__(name).value
# 
#         except KeyError as e:
#             if isinstance(name, enum_class):
#                 value = name.value
# 
#             else:
#                 raise ValueError(
#                     f"{name} is not a member of {enum_class.__name__}"
#                 ) from e

    return value


def find_enum(enum_class: EnumType, name_or_value: Any) -> Enum:
    """Given a name or a value find the actual enum property that matches

    :param enum_class: Enum, the enum class we'll find the property on
    :param name_or_value: Any, a name, value, or enum property
    :returns: Enum, the enum property with .name and .value properties
    """
    if isinstance(name_or_value, enum_class):
        return name_or_value
        #name = name_or_value.name

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

        en = None
        for n in name.split("|"):
            if en is None:
                en = enum_class[n]

            else:
                en |= enum_class[n]

        return en
#         return enum_class[name]


def find_name(enum_class: EnumType, name: str) -> str:
    """find the name of an enum, case-insensitive

    :param enum_class: Enum, the enum class we'll check for name
    :param name: str
    :returns: str, the name of the enum property
    """
    return find_enum(enum_class, name).name


def find_value(enum_class: EnumType, value: Any) -> Any:
    """find the value of an enum, similar to find_name() this will normalize
    the name or value and return the found value

    :param value: Any, an enum value or name
    :returns value: Any, the value normalized
    """
    return find_enum(enum_class, value).value


###############################################################################
# Enum and EnumMeta are deprecated as of 2026-03-24 since they were originally
# designed to bring Enum support to py2 and I almost always use the stdlib
# Enum now
###############################################################################

class EnumMeta(EnumMeta):
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
class Enum(Enum, metaclass=EnumMeta):
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
        return convert_enum_to_dict(cls)
#         d = {}
#         for k, v in cls.__members__.items():
#             d[String(k)] = v.value
#         return d

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

