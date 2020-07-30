# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from .compat import *
from .string import String


class EnumMixin(object):
    @classmethod
    def find_name(cls, name):
        """find the name of an enum, case-insensitive

        :param name: str|int, can be anything and it will be converted to an int
        :returns: string, the value found for name
        """
        if isinstance(name, int):
            ret = cls.convert_int_to_str(name)
        else:
            cls.convert_str_to_int(name) # error check
            ret = cls.convert_str_to_str(name)
        return String(ret)

    @classmethod
    def find_value(cls, value):
        """find the value of an enum, similar to .find_name() this will normalize
        the name or value and return the found value

        :param value: str|int, an enum value or name
        :returns value: int, the value of the enum
        """
        if isinstance(value, int):
            cls.convert_int_to_str(value) # error check
            ret = value

        else:
            ret = cls.convert_str_to_int(value)
        return ret

    @classmethod
    def all(cls):
        """return all the enum values with names as key and integer values"""
        d = {}
        for k, v in cls.__members__.items():
            d[String(k)] = v.value
        return d

    @classmethod
    def names(cls):
        """return all the ENUM names"""
        return cls.all().keys()

    @classmethod
    def values(cls):
        """return all the enum values"""
        return cls.all().values()

    @classmethod
    def convert_str_to_int(cls, name):
        name = cls.convert_str_to_str(name)
        value = getattr(cls, name)
        return value.value

    @classmethod
    def convert_int_to_str(cls, value):
        found = False
        for k, v in cls.__members__.items():
            if v.value == value:
                ret = k
                found = True
                break
        if not found:
            raise ValueError("Value {} is not a valid enumerated value".format(value))

        return ret

    @classmethod
    def convert_str_to_str(cls, name):
        if isinstance(name, cls):
            name = name.name
        else:
            name = name.upper()
        return name

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


if is_py2:
    class EnumMeta(type):
        """This is the __metaclass__ for the Enum class, it is basically private to
        this module (and the Enum class). It exists so the Enum class can basically
        act like the built-in python3 enum class in python2

        https://docs.python.org/3/library/enum.html
        """
        def __new__(cls, name, bases, properties):
            """https://docs.python.org/3/library/functions.html#type"""
            instance = super(EnumMeta, cls).__new__(cls, name, bases, properties)

            # if the name of the class isn't Enum then we have a child and we should
            # do some magic
            if name != "Enum":
                members = {}

                for k, v in properties.items():
                    if k.isupper():
                        en = instance(v)
                        en.name = String(k)
                        members[k] = en
                        setattr(instance, k, en)

                # https://docs.python.org/3/library/enum.html#iteration
                instance.__members__ = members
            return instance

        def __contains__(cls, k):
            if isinstance(k, cls):
                k = k.name
            return k in cls.__dict__

        def __getitem__(cls, k):
            if k in cls.__dict__:
                return cls.__dict__[k]

            else:
                raise AttributeError(k)

        def __setattr__(cls, k, v):
            if hasattr(cls, "__members__"):
                # once the __members__ property is set it means we are done adding
                # to this enum instance and it is now read only
                pass
            else:
                super(EnumMeta, cls).__setattr__(k, v)

        def __iter__(cls):
            for v in cls.__members__.values():
                yield v


    class Enum(EnumMixin):
        """Enum Class

        This does its very best to act like the builtin python 3 enum class:

            https://docs.python.org/3/library/enum.html

        Differences from builtin py3 enum class:

            1. This expects enum keys to be uppercase
            2. Enum values can only be integers
            3. This has additional methods that py3 Enum does not have
        """
        __metaclass__ = EnumMeta

        def __init__(self, value):
            self.value = value

else:
    from enum import Enum as BaseEnum, EnumMeta as BaseEnumMeta

    class EnumMeta(BaseEnumMeta):
        def __contains__(cls, k):
            if isinstance(k, cls):
                return super(EnumMeta, cls).__contains__(k)
            else:
                # "FOO" in Enum is deprecated behavior in py3.8, this restores it
                return k in cls.__dict__

    # python 2 parser will fail on metaclass=... syntax, so work around that
    #
    # Order matters for the parent classes
    # https://docs.python.org/3/library/enum.html#restricted-enum-subclassing
    exec("class Enum(EnumMixin, BaseEnum, metaclass=EnumMeta): pass")

