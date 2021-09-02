# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.number import (
    Integer,
    Shorten,
    #Hex,
    #Binary,
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
    def test_conversion(self):
        i = Integer(b'\xf0')
        self.assertEqual(240, i)

    def test_range(self):
        i = Integer(-5)
        count = 0
        for x in i.range():
            count += 1
            self.assertLess(x, 0)
        self.assertEqual(5, count)

        i = Integer(5)
        count = 0
        for x in i.range():
            count += 1
            self.assertLess(x, 5)
        self.assertEqual(5, count)

    def test_hex(self):
        v = Integer(55817)

        i = Integer("0xDA09")
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer("DA09")
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer(0xDA09)
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer("-DA09")
        self.assertEqual(-v, i)

        i = Integer("+DA09")
        self.assertEqual(v, i)

        i = Integer("-0xDA09")
        self.assertEqual(-v, i)

        i = Integer("+0xDA09")
        self.assertEqual(v, i)

    def test_binary(self):
        v = Integer(55817)

        i = Integer("1101101000001001")
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer("0b1101101000001001")
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer(0b1101101000001001)
        self.assertEqual(v, i)
        self.assertTrue("DA09", i.hex())

        i = Integer("-1101101000001001")
        self.assertEqual(-v, i)

        i = Integer("+1101101000001001")
        self.assertEqual(v, i)

        i = Integer("-0b1101101000001001")
        self.assertEqual(-v, i)

        i = Integer("+0b1101101000001001")
        self.assertEqual(v, i)

    def test_ambiguous(self):
        ia = Integer("0010")
        ih = Integer("0010", 16)
        ib = Integer("0010", 2)

        self.assertEqual(ib, ia)
        self.assertNotEqual(ih, ia)

