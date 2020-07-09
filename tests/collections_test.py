# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.collections import (
    Pool,
    PriorityQueue,
    idict,
    Trie,
    OrderedList,
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
    def test_create(self):
        d = idict({
            "foo": 1,
            "BAR": 2
        })
        self.assertTrue("Foo" in d)
        self.assertTrue("bar" in d)
        self.assertEqual(2, len(d))

    def test_keys(self):
        d = idict()

        d["FOO"] = 1
        self.assertTrue("foo" in d)
        self.assertTrue("Foo" in d)
        self.assertFalse("bar" in d)
        self.assertEqual(1, d["FOO"])

        d["foo"] = 2
        self.assertEqual(2, d["FOO"])


class TrieTest(TestCase):
    def test_has(self):
        values = ["foo", "bar", "che", "boo"]
        t = Trie(*values)
        #pout.v(t)

        for value in values:
            self.assertTrue(t.has(value))

        self.assertFalse(t.has("foobar"))
        self.assertFalse(t.has("zoo"))
        self.assertFalse(t.has("bars"))


class OrderedListTest(TestCase):
    def test_storage(self):
        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        x1 = Val(30, "che")
        x2 = Val(4, "bar")
        x3 = Val(1, "foo")

        ol = OrderedList([x1, x2, x3], lambda x: x.priority)

        for x in ol:
            self.assertTrue(isinstance(x, Val))

        for i in range(len(ol)):
            self.assertTrue(isinstance(x, Val))

        iterable = [(30, "che"), (4, "bar"), (1, "foo")]
        ol = OrderedList(iterable)
        for i, v in enumerate(reversed(iterable)):
            self.assertEqual(v, ol[i])

    def test_extend(self):

        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        class MyOL(OrderedList):
            def key(self, x):
                return x.priority

        ol = MyOL()

        ol.append(Val(30, "che"))
        ol.append(Val(1, "foo"))
        ol.append(Val(4, "bar"))

        self.assertEqual("foo", ol[0].val)
        self.assertEqual("bar", ol[1].val)
        self.assertEqual("che", ol[2].val)

    def test_order(self):
        h = OrderedList(key=lambda x: x[0])

        h.append((30, "che"))
        h.append((4, "bar"))
        h.append((1, "foo"))

        self.assertEqual("foo", h[0][1])
        self.assertEqual("che", h[-1][1])

        h.append((50, "boo"))
        self.assertEqual("boo", h[-1][1])

        self.assertEqual("foo", h.pop(0)[1])
        self.assertEqual("boo", h.pop(-1)[1])
        self.assertEqual("che", h.pop()[1])


class PriorityQueueTest(TestCase):
    def test_order(self):
        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        pq = PriorityQueue(lambda x: x.priority)

        pq.put(Val(30, "che"))
        pq.put(Val(1, "foo"))
        pq.put(Val(4, "bar"))

        self.assertTrue(bool(pq))
        self.assertEqual("foo", pq.get().val)
        self.assertEqual("bar", pq.get().val)
        self.assertEqual("che", pq.get().val)
        self.assertFalse(bool(pq))

    def test_maxqueue(self):
        class MaxQueue(PriorityQueue):
            def key(self, x):
                return -x[0]

        q = MaxQueue()

        q.put((50, "foo"))
        q.put((5, "bar"))
        q.put((100, "che"))

        self.assertEqual((100, "che"), q.get())
        self.assertEqual((50, "foo"), q.get())
        self.assertEqual((5, "bar"), q.get())


