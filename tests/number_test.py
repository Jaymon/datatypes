# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.number import (
    Integer,
    Shorten,
    Exponential,
    Hex,
    #Binary,
    Boolean,
    Partitions,
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


class BooleanTest(TestCase):
    def test_true(self):
        self.assertTrue(Boolean(True))
        self.assertTrue(Boolean(100))
        self.assertTrue(Boolean(1.1))
        self.assertTrue(Boolean("yes"))
        self.assertTrue(Boolean("YES"))
        self.assertTrue(Boolean("ok"))
        self.assertTrue(Boolean("t"))
        self.assertTrue(Boolean("true"))
        self.assertTrue(isinstance(Boolean(1), bool))

    def test_false(self):
        self.assertFalse(Boolean(False))
        self.assertFalse(Boolean(-100))
        self.assertFalse(Boolean(-1.1))
        self.assertFalse(Boolean(0))
        self.assertFalse(Boolean("no"))
        self.assertFalse(Boolean("OFF"))
        self.assertFalse(Boolean("   "))
        self.assertFalse(Boolean("f"))
        self.assertFalse(Boolean("false"))


class PartitionsTest(TestCase):
    def test_bounds(self):
        p = Partitions(10)
        self.assertLess(p.lower_bound(), len(p))
        self.assertGreater(p.upper_bound(), len(p))

    def test_kpartitions(self):
        p = Partitions(10)
        for p in p.kpartitions(4):
            for k in p.keys():
                self.assertLessEqual(k, 4)

        p = Partitions(6)
        for p in p.kpartitions(2):
            for k in p.keys():
                self.assertLessEqual(k, 2)

    def test___iter__(self):
        ps = Partitions(10)
        count = 0
        for p in ps:
            count += 1
        self.assertEqual(42, count)

    def test___len__(self):
        # values from: https://en.wikipedia.org/wiki/Partition_function_(number_theory)
        ps = [
            (0, 1),
            (1, 1),
            (2, 2),
            (3, 3),
            (4, 5),
            (5, 7),
            (6, 11),
            (7, 15),
            (8, 22),
            (9, 30),
            (10, 42),
            (25, 1958),
            (40, 37338),
        ]

        for pn, plen in ps:
            p = Partitions(pn)
            self.assertEqual(plen, len(p))

    def test_strict(self):
        pstests = [
            (0, 1),
            (1, 1),
            (2, 1),
            (3, 2),
            (4, 2),
            (5, 3),
            (6, 4),
            (7, 5),
            (8, 6),
            (9, 8),
        ]

        for pn, plen in pstests:
            ps = Partitions(pn)
            count = 0
            for p in ps.strict():
                count += 1
                seen = set()
                for n in p:
                    self.assertFalse(n in seen)
                    seen.add(n)

            self.assertEqual(plen, count, f"{ps.n=}")

