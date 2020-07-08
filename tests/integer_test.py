# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.integer import (
    Integer,
    Shorten,
)

from . import TestCase, testdata


class ShortenTest(TestCase):
    def test_encode_decode(self):
        s = Shorten(100)
        i = testdata.get_int()
        s = Shorten(i)
        self.assertNotEqual(s, i)

        i2 = Shorten(s)
        self.assertEqual(i, i2)


class IntegerTest(TestCase):
    def test___iter__(self):
        i = Integer(-5)
        count = 0
        for x in i:
            count += 1
            self.assertLess(x, 0)
        self.assertEqual(5, count)

        i = Integer(5)
        count = 0
        for x in i:
            count += 1
            self.assertLess(x, 5)
        self.assertEqual(5, count)

