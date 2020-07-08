# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.collections import (
    Pool,
    PriorityQueue,
    idict,
)

from . import TestCase, testdata


class PoolTest(TestCase):
    def test_lifecycle(self):

        class TestPool(Pool):
            def create_value(self, key):
                return key

        pool = TestPool()

        self.assertEqual([], pool.pq.keys())

        r = pool[1]
        self.assertEqual(1, r)

        r = pool[1]
        self.assertEqual(1, r)

        r = pool[1]
        self.assertEqual(1, r)

        self.assertEqual([1], pool.pq.keys())

        r = pool[2]
        self.assertEqual(2, r)
        self.assertEqual([1, 2], pool.pq.keys())

        r = pool[1]
        self.assertEqual(1, r)
        self.assertEqual([2, 1], pool.pq.keys())


class IdictTest(TestCase):
    def test_keys(self):
        d = idict()

        d["FOO"] = 1
        self.assertTrue("foo" in d)
        self.assertTrue("Foo" in d)
        self.assertFalse("bar" in d)
        self.assertEqual(1, d["FOO"])

        d["foo"] = 2
        self.assertEqual(2, d["FOO"])
