# -*- coding: utf-8 -*-
import enum

from datatypes.compat import *
from datatypes.enum import (
    Enum,
    find_enum,
    find_name,
    find_value,
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

