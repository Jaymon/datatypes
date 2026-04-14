# -*- coding: utf-8 -*-
import enum

from datatypes.compat import *
from datatypes.enum import (
    Enum,
    find_enum,
    find_name,
    find_value,
    convert_enum_to_dict,
    convert_value_to_name,
    convert_name_to_value,
)

from . import TestCase, testdata


class EnumTest(TestCase):
    def test___contains__(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertTrue(Foo.BAR in Foo)
        self.assertTrue("BAR" in Foo)
        self.assertEqual(1, Foo["BAR"].value)
        self.assertEqual(1, Foo.BAR.value)
        self.assertEqual(set(["BAR", "CHE"]), set(Foo.__members__.keys()))

    def test___setattr__(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        Foo.VOODOO = 4
        self.assertFalse("VOODOO" in Foo.__members__.keys())

    def test_find_name(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertEqual("BAR", Foo.find_name("bar"))
        self.assertEqual("BAR", Foo.find_name("Bar"))
        self.assertEqual("BAR", Foo.find_name(1))
        self.assertEqual("BAR", Foo.find_name("BAR"))

    def test_find_value(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertEqual(1, Foo.find_value("bar"))
        self.assertEqual(1, Foo.find_value("Bar"))
        self.assertEqual(1, Foo.find_value(1))
        self.assertEqual(1, Foo.find_value("BAR"))
        self.assertEqual(2, Foo.find_value("che"))

    def test_compare(self):
        class Foo(Enum):
            BAR = 1

        self.assertEqual(1, int(Foo.BAR))
        self.assertTrue(1 == Foo.BAR)

    def test_not_py2(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertTrue(isinstance(Foo.BAR, enum.Enum))

    def test_equality(self):
        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertFalse([] == Foo.CHE)

        self.assertTrue(1 == Foo.BAR)
        self.assertTrue("BAR" == Foo.BAR)
        self.assertTrue(Foo.BAR == Foo.BAR)

        self.assertFalse(100 == Foo.BAR)
        self.assertFalse("ADFKLSDAKLJDL" == Foo.BAR)
        self.assertFalse(Foo.CHE == Foo.BAR)

    def test_enumtype(self):
        class Foo(Enum):
            BAR = 1

        self.assertTrue(issubclass(Foo, Enum))
        self.assertFalse(issubclass(Foo, enum.EnumType))
        self.assertTrue(isinstance(Foo, enum.EnumType))

        class Bar(enum.Enum):
            FOO = 1

        self.assertTrue(issubclass(Bar, enum.Enum))
        self.assertFalse(issubclass(Bar, enum.EnumType))
        self.assertTrue(isinstance(Bar, enum.EnumType))


class StdEnumTest(TestCase):
    """Tests for the python standard library enum to make sure Datatype's enum
    methods work with it as expected
    """
    def test_find_enum(self):
        class Foo(enum.Enum):
            ONE = 1
            TWO = 2

        r1 = find_enum(Foo, "ONE")
        r2 = find_enum(Foo, 1)
        r3 = find_enum(Foo, Foo.ONE)
        self.assertTrue(r1 == r2 == r3 == Foo.ONE)

    def test_find_name_1(self):
        class Foo(enum.Enum):
            ONE = "one"
            TWO = "two"

        r1 = find_name(Foo, "ONE")
        r2 = find_name(Foo, "one")
        r3 = find_name(Foo, Foo.ONE)
        self.assertTrue(r1 == r2 == r3 == "ONE")

    def test_find_name_2(self):
        class Foo(enum.Enum):
            ONE = 1
            TWO = 2

        r1 = find_name(Foo, "ONE")
        r2 = find_name(Foo, 1)
        r3 = find_name(Foo, Foo.ONE)
        r4 = find_name(Foo, "one")
        #pout.v(r1, r2, r3, r4)
        self.assertTrue(r1 == r2 == r3 == r4 == "ONE")

    def test_find_value_1(self):
        class Foo(enum.Enum):
            ONE = 1
            TWO = 2

        r1 = find_value(Foo, "ONE")
        r2 = find_value(Foo, 1)
        r3 = find_value(Foo, Foo.ONE)
        self.assertTrue(r1 == r2 == r3 == 1)

    def test_convert_enum_to_dict_1(self):
        class Foo(enum.Enum):
            ONE = 1
            TWO = 2

        d = convert_enum_to_dict(Foo)
        self.assertEqual(2, len(d))
        self.assertTrue("ONE" in d)
        self.assertEqual(2, d["TWO"])

        class Bar(enum.IntEnum):
            ONE = 1
            TWO = 2
            ALL = ONE|TWO

        d = convert_enum_to_dict(Bar)
        self.assertEqual(3, len(d))

    def test_convert_enum_to_dict_flag(self):
        class Foo(enum.Flag):
            ONE = enum.auto()
            TWO = enum.auto()
            THREE = enum.auto()
            FOUR = enum.auto()

        d = convert_enum_to_dict(Foo)
        self.assertEqual(4, len(d))
        self.assertEqual(8, d["FOUR"])

    def test_find_enum_value_flags(self):
        class Foo(enum.Flag):
            ONE = enum.auto()
            TWO = enum.auto()
            THREE = enum.auto()
            FOUR = enum.auto()

        en1 = Foo.ONE|Foo.TWO|Foo.THREE
        en2 = find_enum(Foo, en1)
        self.assertEqual(en1, en2)

        value = find_value(Foo, en1.value)
        self.assertEqual(en1.value, value)

    def test_convert_value_to_name_flag_1(self):
        class Foo(enum.Flag):
            ONE = enum.auto()
            TWO = enum.auto()

        name = convert_value_to_name(Foo, (Foo.ONE|Foo.TWO).value)
        self.assertEqual("ONE|TWO", name)

    def test_convert_value_to_name_flag_2(self):
        class Foo(enum.Flag):
            NONE = 0
            ONE = enum.auto()
            TWO = enum.auto()
            THREE = enum.auto()
            ALL = ONE|TWO|THREE

        name = convert_value_to_name(Foo, 0)
        self.assertEqual("NONE", name)

        name = convert_value_to_name(Foo, (Foo.ONE|Foo.TWO).value)
        self.assertEqual("ONE|TWO", name)

        name = convert_value_to_name(Foo, (Foo.ONE|Foo.THREE).value)
        self.assertEqual("ONE|THREE", name)

        name = convert_value_to_name(Foo, Foo.ONE.value)
        self.assertEqual("ONE", name)

        name = convert_value_to_name(Foo, Foo.THREE.value)
        self.assertEqual("THREE", name)

        name = convert_value_to_name(Foo, Foo.ALL.value)
        self.assertEqual("ALL", name)

    def test_convert_name_to_value_flag(self):
        class Foo(enum.Flag):
            ONE = enum.auto()
            TWO = enum.auto()

        value = convert_name_to_value(Foo, "ONE|TWO")
        self.assertEqual((Foo.ONE|Foo.TWO).value, value)

    def test_find_enum_none_value(self):
        class Foo(enum.Enum):
            ONE = 1
            TWO = 2

        with self.assertRaises(ValueError):
            find_enum(Foo, None)

