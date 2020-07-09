# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.enum import Enum

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
        if is_py2:
            self.skip_test("Not supported in Python2")

        from enum import Enum as StdEnum

        class Foo(Enum):
            BAR = 1
            CHE = 2

        self.assertTrue(isinstance(Foo.BAR, StdEnum))

