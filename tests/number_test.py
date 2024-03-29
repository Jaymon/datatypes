# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.number import (
    Integer,
    Shorten,
    Exponential,
    Hex,
    #Binary,
    Bool,
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

    def test_sub(self):
        i = Integer("830")
        self.assertEqual(830, i)

        i = Integer("3,265")
        self.assertEqual(3265, i)

        i = Integer("10K")
        self.assertEqual(10000, i)


class HexTest(TestCase):
    def test_create(self):
        h = Hex("5B")
        self.assertEqual(int("5B", 16), h)


class ExponentialTest(TestCase):
    def test_decay(self):
        exp = Exponential(97, 0.1)
        self.assertEqual(696, int(sum(exp.decay(12))))

    def test_rate(self):
        exp = Exponential(10, 25)
        self.assertEqual(0.25, exp.rate)


class BoolTest(TestCase):
    def test_true(self):
        self.assertTrue(Bool(100))
        self.assertTrue(Bool(1.1))
        self.assertTrue(Bool("yes"))
        self.assertTrue(Bool("YES"))
        self.assertTrue(Bool("ok"))
        self.assertTrue(isinstance(Bool(1), bool))

    def test_false(self):
        self.assertFalse(Bool(-100))
        self.assertFalse(Bool(-1.1))
        self.assertFalse(Bool(0))
        self.assertFalse(Bool("no"))
        self.assertFalse(Bool("OFF"))
        self.assertFalse(Bool("   "))

