# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.collections import (
    Pool,
    PriorityQueue,
    idict,
    Trie,
    OrderedList,
    Dict,
)

from . import TestCase, testdata


class PriorityQueueTest(TestCase):
    def test_priority(self):
        q = PriorityQueue(5)

        q.put(5, priority=10)
        q.put(4, priority=1)
        self.assertEqual(4, q.get())
        return

    def test_order(self):
        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        pq = PriorityQueue(priority=lambda x: x.priority)

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
            def priority(self, x):
                return -x[0]

        q = MaxQueue()

        q.put((50, "foo"))
        q.put((5, "bar"))
        q.put((100, "che"))

        self.assertEqual((100, "che"), q.get())
        self.assertEqual((50, "foo"), q.get())
        self.assertEqual((5, "bar"), q.get())

    def test_minqueue(self):
        class MinQueue(PriorityQueue):
            def priority(self, x):
                return x[0]

        q = MinQueue()

        q.put((50, "foo"))
        q.put((5, "bar"))
        q.put((100, "che"))

        self.assertEqual((5, "bar"), q.get())
        self.assertEqual((50, "foo"), q.get())
        self.assertEqual((100, "che"), q.get())

    def test_key(self):
        q = PriorityQueue(5)

        q.put(5, key=1)
        q.put(4, key=1)
        self.assertEqual(1, len(q))
        self.assertEqual(4, q.get())

    def test_push(self):
        q = PriorityQueue(5)

        for x in range(11):
            q.push(x)

        self.assertEqual([6, 7, 8, 9, 10], list(q.values()))


class PoolTest(TestCase):
    def test_setdefault(self):
        p = Pool()
        p.setdefault("foo", 1)
        p.setdefault("foo", 2)
        self.assertEqual(p["foo"], 1)

    def test_get(self):
        p = Pool(2)

        p[1] = 1
        p[2] = 2

        v = p.get(1)
        self.assertEqual(1, v)

        p[3] = 3
        self.assertFalse(2 in p)
        self.assertTrue(1 in p)
        self.assertTrue(3 in p)

    def test_pop(self):
        p = Pool(2)

        p[1] = 1
        p[2] = 2

        v = p.pop(2)
        self.assertEqual(2, v)
        self.assertEqual(1, len(p))

    def test_size(self):
        p = Pool(5)

        for x in range(11):
            p[x] = x

        self.assertEqual([6, 7, 8, 9, 10], list(p.values()))

    def test_lifecycle(self):
        pool = Pool()

        self.assertEqual([], list(pool.pq.keys()))

        pool[1] = 1
        r = pool[1]
        self.assertEqual(1, r)

        r = pool[1]
        self.assertEqual(1, r)

        r = pool[1]
        self.assertEqual(1, r)

        self.assertEqual([1], list(pool.pq.keys()))

        pool[2] = 2
        r = pool[2]
        self.assertEqual(2, r)
        self.assertEqual([1, 2], list(pool.pq.keys()))

        r = pool[1]
        self.assertEqual(1, r)
        self.assertEqual([2, 1], list(pool.pq.keys()))

    def test___missing__(self):
        class MissingPool(Pool):
            def __missing__(self, k):
                self[k] = k
                return k

        p = MissingPool(2)

        v = p[1]
        self.assertEqual(1, v)
        self.assertEqual(1, len(p))

        v = p[2]
        self.assertEqual(2, v)
        self.assertEqual(2, len(p))

        v = p[3]
        self.assertEqual(3, v)
        self.assertEqual(2, len(p))


class DictTest(TestCase):
    def test_rmethods(self):
        d = Dict({
            "bar": {
                "foo": [1, 2, 3],
            },
            "che": {
                "bar": {
                    "foo": [4, 5, 6, 7],
                }
            },
            "boo": {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": {
                    "foo": [8, 9],
                },
            },
        })

        count = 0
        for kp, v in d.ritems():
            count += 1
        self.assertEqual(11, count)

        vs = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        kps = [
            ["bar", "foo"],
            ["che", "bar", "foo"],
            ["boo", "four", "foo"],
        ]

        foos = []
        for kp, v in d.ritems("foo"):
            self.assertTrue(kp in kps)
            foos.extend(v)
        self.assertEqual(vs, foos)

        for kp in d.rkeys("foo"):
            self.assertTrue(kp in kps)

        foos = []
        for v in d.rvalues("foo"):
            self.assertTrue(kp in kps)
            foos.extend(v)
        self.assertEqual(vs, foos)


class IdictTest(TestCase):
    def test_ritems(self):
        d = idict({
            "bar": {
                "foo": [1, 2, 3],
            },
            "che": {
                "bar": {
                    "foo": [4, 5, 6, 7],
                }
            },
            "boo": 1,
        })

        items = list(d.ritems("BAR"))
        self.assertEqual(2, len(items))

        items = list(d.ritems())
        self.assertEqual(6, len(items))

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

