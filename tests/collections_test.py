# -*- coding: utf-8 -*-

from datatypes.compat import *

from datatypes.collections.mapping import (
    Pool,
    Dict,
    NormalizeDict,
    idict,
    Namespace,
    ContextNamespace,
    DictTree,
)
from datatypes.collections.sequence import (
    PriorityQueue,
    AppendList,
    SortedList,
    Stack,
    ListIterator,
)
from datatypes.collections.container import (
    Trie,
    HotSet,
    OrderedSet,
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

        v = d.rget("foo")
        self.assertEqual([1, 2, 3], v)

    def test_merge(self):
        d = Dict({
            "foo": {
                "bar": 1,
            },
            "che": 1,
            "baz": {
                "boo": {
                    "bah": 1,
                    "cha": 1,
                },
            },
        })

        d.merge({
            "foo": {
                "bar2": 2
            },
            "baz": {
                "boo": {
                    "bah": 2
                },
                "boo2": 2
            },
            "new": 2,
            "che": {
                "che2": 2
            }
        })
        self.assertEqual(2, d["foo"]["bar2"])
        self.assertEqual(1, d["foo"]["bar"])
        self.assertEqual(2, d["baz"]["boo"]["bah"])
        self.assertEqual(1, d["baz"]["boo"]["cha"])
        self.assertEqual(2, d["che"]["che2"])
        self.assertEqual(2, d["new"])


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

    def test_pop(self):
        d = idict()
        d["foo"] = 1
        self.assertEqual(1, d.pop("foo"))
        self.assertEqual(None, d.pop("foo", None))
        with self.assertRaises(KeyError):
            d.pop("foo")


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


class SortedListTest(TestCase):
    def test_storage(self):
        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        x1 = Val(30, "che")
        x2 = Val(4, "bar")
        x3 = Val(1, "foo")

        ol = SortedList([x1, x2, x3], lambda x: x.priority)

        for x in ol:
            self.assertTrue(isinstance(x, Val))

        for i in range(len(ol)):
            self.assertTrue(isinstance(x, Val))

        iterable = [(30, "che"), (4, "bar"), (1, "foo")]
        ol = SortedList(iterable)
        for i, v in enumerate(reversed(iterable)):
            self.assertEqual(v, ol[i])

    def test_extend(self):

        class Val(object):
            def __init__(self, priority, val):
                self.priority = priority
                self.val = val

        class MyOL(SortedList):
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
        h = SortedList(key=lambda x: x[0])

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


class NamespaceTest(TestCase):
    def test_crud(self):
        n = Namespace()

        n.bar = 1
        self.assertEqual(1, n.bar)
        self.assertEqual(1, n["bar"])
        del n.bar
        with self.assertRaises(AttributeError):
            n.bar

        n["foo"] = 2
        self.assertEqual(2, n.foo)
        self.assertEqual(2, n["foo"])
        del n["foo"]
        with self.assertRaises(AttributeError):
            n.foo

    def test___missing__(self):
        class ChildNS(Namespace):
            def __missing__(self, k):
                return None

        n = ChildNS()

        self.assertIsNone(n.foo)

        n.foo = 1
        self.assertEqual(1, n.foo)


class ContextNamespaceTest(TestCase):
    def test_crud(self):
        n = ContextNamespace()

        n.foo = "foo"
        self.assertEqual("foo", n.foo)
        self.assertTrue("foo" in n)

        with n.context("bar") as nbar:
            self.assertEqual("foo", nbar.foo)
            self.assertTrue("foo" in nbar)

            nbar.foo = "bar"
            self.assertEqual("bar", nbar.foo)
            self.assertTrue("foo" in nbar)
            self.assertEqual("bar", n.foo)
            self.assertTrue("foo" in n)

            nbar.bar = "bar2"
            self.assertEqual("bar2", nbar.bar)
            self.assertTrue("bar" in nbar)

            del nbar.foo
            self.assertEqual("foo", nbar.foo)

        self.assertEqual("foo", n.foo)
        self.assertTrue("foo" in n)
        with self.assertRaises(AttributeError):
            n.bar


    def test_pop(self):
        n = ContextNamespace("one")

        n.foo = 1
        n.bar = 2

        with n.context("two"):
            n.bar = 3
            self.assertEqual(3, n.pop("bar"))
            self.assertEqual(None, n.pop("bar", None))
            with self.assertRaises(KeyError):
                n.pop("bar")

        self.assertEqual(2, n.pop("bar"))
        with self.assertRaises(KeyError):
            n.pop("bar")
        self.assertEqual(None, n.pop("bar", None))

    def test_popitem(self):
        n = ContextNamespace()

        with self.assertRaises(KeyError):
            n.popitem()

        n.foo = 1
        self.assertEqual(("foo", 1), n.popitem())

        n.foo = 2
        with n.context("two"):
            with self.assertRaises(KeyError):
                n.popitem()

            n.foo = 3
            self.assertEqual(("foo", 3), n.popitem())

            with self.assertRaises(KeyError):
                n.popitem()
        self.assertEqual(("foo", 2), n.popitem())

    def test_reversed(self):
        n = ContextNamespace()
        n.foo = 1
        n.bar = 2

        keys = []
        for k in reversed(n):
            keys.append(k)
        self.assertEqual(["bar", "foo"], keys)


    def test_setdefault(self):
        n = ContextNamespace()
        self.assertEqual(1, n.setdefault("foo", 1))
        self.assertEqual(1, n.setdefault("foo", 2))

        with n.context("two"):
            self.assertEqual(1, n.setdefault("foo", 3))

    def test_update(self):
        n = ContextNamespace()

        n.update({"foo": 1, "bar": 2})
        self.assertEqual(1, n.foo)
        self.assertEqual(2, n.bar)

        with n.context("two"):
            n.update({"che": 3, "bar": 4})
            self.assertEqual(1, n.foo)
            self.assertEqual(4, n.bar)
            self.assertEqual(3, n.che)
        self.assertEqual(1, n.foo)
        self.assertEqual(2, n.bar)

        with n.context("three"):
            n |= {"che": 5, "bar": 6}
            self.assertEqual(1, n.foo)
            self.assertEqual(6, n.bar)
            self.assertEqual(5, n.che)
        self.assertEqual(1, n.foo)
        self.assertEqual(2, n.bar)

        n2 = n | {"che": 5, "bar": 6}
        self.assertEqual(1, n2.foo)
        self.assertEqual(6, n2.bar)
        self.assertEqual(5, n2.che)
        self.assertEqual(1, n.foo)
        self.assertEqual(2, n.bar)

    def test_clear(self):
        n = ContextNamespace()

        n.foo = 1
        with n.context("two"):
            n.foo = 2
            n.clear()
            self.assertEqual(1, n.foo)

    def test_copy(self):
        n = ContextNamespace()

        n.foo = 1

        self.assertEqual({"foo": 1}, n.copy())

        with n.context("two"):
            n.foo = 2
            n.bar = 3
            self.assertEqual({"foo": 2, "bar": 3}, n.copy())

        self.assertEqual({"foo": 1}, n.copy())

    def test_contexts(self):
        class Config(ContextNamespace):
            @property
            def base_url(self):
                s = ""
                if self.host:
                    s = f"{self.scheme}://" if self.scheme else "//"
                    s += self.host
                return s

        config = Config()
        config.host="example2.com"

        with config.context("web", scheme="", host="example.com") as conf:
            self.assertEqual("//example.com", conf.base_url)

        with config.context("feed", scheme="https", host="example.com") as conf:
            self.assertEqual("https://example.com", conf.base_url)

        with config.context("no_host_no_scheme", scheme="", host="") as conf:
            self.assertEqual("", conf.base_url)

        with config.context("no_host_scheme", scheme="http", host="") as conf:
            self.assertEqual("", conf.base_url)

        with config.context("host_none_scheme", scheme="http", host=None) as conf:
            self.assertEqual("", conf.base_url)

        with config.context("none_host_and_scheme", scheme=None, host=None) as conf:
            self.assertEqual("", conf.base_url)

    def test_context_with(self):
        config = ContextNamespace()
        with config.context("foo", bar=1) as conf:
            self.assertEqual("foo", conf.context_name())
            self.assertEqual(1, conf.bar)

        with self.assertRaises(AttributeError):
            config.bar

        self.assertEqual("", conf.context_name())

        with config.context("foo2", bar=2) as conf:
            self.assertEqual(2, conf.bar)

        with config.context("foo") as conf:
            self.assertEqual(1, conf.bar)

    def test_context_hierarchy(self):
        """https://github.com/Jaymon/bang/issues/33"""
        config = ContextNamespace()
        config.foo = False

        with config.context("foo") as c:
            c.foo = True
            self.assertEqual("foo", c.context_name())
            self.assertTrue(c.foo)

            with config.context("bar") as c:
                self.assertEqual("bar", c.context_name())
                self.assertTrue(c.foo)
                c.foo = False

                with config.context("che") as c:
                    # should be in che context here
                    self.assertEqual("che", c.context_name())
                    self.assertFalse(c.foo)

                # should be in bar context here
                self.assertEqual("bar", c.context_name())
                self.assertFalse(c.foo)

            #should be in foo context here
            self.assertEqual("foo", c.context_name())
            self.assertTrue(c.foo)

        # should be in "" context here
        self.assertEqual("", c.context_name())
        self.assertFalse(c.foo)

    def test_cascade_off(self):
        c = ContextNamespace(cascade=False)

        c.foo = 1
        self.assertTrue("foo" in c)

        c.push_context("foobar")
        self.assertFalse("foo" in c)

        c.foo = 5
        self.assertTrue("foo" in c)
        self.assertEqual(5, c.foo)

        c.bar = 6
        self.assertTrue("bar" in c)
        self.assertEqual(6, c.bar)

        c.pop_context()
        self.assertTrue("foo" in c)
        self.assertFalse("bar" in c)
        self.assertEqual(1, c.foo)

    def test_clear_context(self):
        c = ContextNamespace()

        c.foo = 1

        with c.context("foobar"):
            c.foo = 2
            c.bar = 3
            self.assertEqual(2, c.foo)
            self.assertEqual(3, c.bar)

        c.clear_context("foobar")
        with c.context("foobar"):
            self.assertEqual(1, c.foo)

    def test___missing__1(self):
        class ChildNS(ContextNamespace):
            def __missing__(self, k):
                return None

        n = ChildNS()

        self.assertIsNone(n.foo)

        n.foo = 1
        self.assertEqual(1, n.foo)

    def test___missing____contains__(self):
        class ChildNS(ContextNamespace):
            def __missing__(self, k):
                return None

        n = ChildNS()

        self.assertIsNone(n.foo)
        self.assertFalse("foo" in n)

        n.setdefault("foo", 1)
        self.assertEqual(1, n.foo)

        n.push_context("bar")
        self.assertEqual(1, n.foo)
        n.setdefault("foo", 2)
        self.assertEqual(1, n.foo)

    def test___contains__(self):
        n = ContextNamespace(cascade=False)
        n.switch_context("foo")
        self.assertFalse("bar" in n)

    def test_setdefault(self):
        n = ContextNamespace()
        n.setdefault("foo", 1)
        self.assertEqual(1, n.foo)

        n.push_context("bar")
        self.assertEqual(1, n.foo)
        n.setdefault("foo", 2)
        self.assertEqual(1, n.foo)

    def test_get(self):
        n = ContextNamespace()
        n.foo = 1

        self.assertEqual(1, n.get("foo"))

        n.push_context("bar")
        self.assertEqual(1, n.get("foo"))
        n.foo = 2
        self.assertEqual(2, n.get("foo"))


class StackTest(TestCase):
    def test_crud(self):
        s = Stack()
        s.push(1)
        self.assertEqual(1, s.peek())

        s.push(2)
        self.assertEqual(2, s.peek())
        self.assertEqual(2, s.peek())

        self.assertEqual(2, s.pop())
        self.assertEqual(1, s.peek())

        s.push(3)
        self.assertEqual(3, s.peek())
        self.assertEqual(2, len(s))

        self.assertEqual([3, 1], [x for x in s])
        self.assertEqual([1, 3], list(reversed(s)))


class DictTreeTest(TestCase):
    def test_set_get_1(self):
        d = DictTree()

        keys = ["foo", "bar", "che"]
        d.set(keys, 1)

        self.assertEqual(1, d.get(keys))
        self.assertEqual(1, d["foo", "bar", "che"])
        self.assertEqual(5, d.get(["foo", "che"], 5))

    def test_set_root(self):
        d = DictTree()

        d.set([], 1)
        self.assertEqual(1, d.value)
        self.assertEqual(1, d[[]])

        d.set(["foo", "bar"], 2)
        self.assertEqual(2, d["foo", "bar"])
        self.assertEqual(None, d["foo"])

        d.set("", 3)
        self.assertEqual(3, d[""])

    def test_set_already_exists(self):
        """Setting on a sub key (eg [foo, bar]) and then setting on the parent
        (eg, [foo]) would cause bar to disappear, this makes sure that is
        fixed (2024-8-8)
        """
        d = DictTree()

        d.set(["foo", "bar"], 1)
        self.assertEqual(1, d["foo", "bar"])

        d.set(["foo"], 2)
        self.assertEqual(1, d["foo", "bar"])
        self.assertEqual(2, d["foo"])

    def test_pop_1(self):
        d = DictTree()
        d.set(["foo", "bar", "che"], 2)

        self.assertEqual(2, d.pop(["foo", "bar", "che"]))
        self.assertEqual(6, d.pop(["foo", "bar", "che"], 6))

    def test_pop_2(self):
        d = DictTree()
        d.set(["foo", "bar", "che"], 1)
        d.set(["foo", "bar"], 2)
        d.set(["foo"], 3)

        self.assertEqual(2, d.pop(["foo", "bar"]))

        with self.assertRaises(KeyError):
            d.pop(["foo", "bar"])

        self.assertEqual(1, d.pop(["foo", "bar", "che"]))

    def test_pop_node(self):
        d = DictTree()
        d.set(["foo", "bar", "che"], 1)
        d.set(["foo", "bar"], 2)

        self.assertEqual(2, d.pop_node(["foo", "bar"]).value)
        self.assertEqual(6, d.pop(["foo", "bar", "che"], 6))

    def test_setdefault(self):
        d = DictTree()
        d.setdefault(["foo", "bar", "che"], 3)
        self.assertEqual(3, d["foo", "bar", "che"])

    def test_magic_methods(self):
        d = DictTree()
        d[["foo", "bar"]] = 4
        self.assertEqual(4, d[["foo", "bar"]])

        self.assertTrue(["foo", "bar"] in d)

        del d[["foo", "bar"]]

        with self.assertRaises(KeyError):
            del d[["foo", "bar"]]

        self.assertFalse(["foo", "bar"] in d)
        self.assertTrue(["foo"] in d)
        self.assertTrue("foo" in d)

    def test_trees(self):
        d = DictTree()

        self.assertEqual(0, len(list(d.trees())))

        d[["foo", "bar"]] = 1
        d[["foo", "che", "baz"]] = 2
        d[["foo", "che", "boo", "far"]] = 3

        td = {
            None: ["foo"],
            "foo": ["bar", "che"],
            "che": ["baz", "boo"],
            "boo": ["far"],
        }

        for ks, v in d.trees():
            for k in td[ks[-1] if ks else None]:
                self.assertTrue(k in v)

    def test_leaves(self):
        d = DictTree()
        d[["foo", "bar"]] = 1
        d[["foo", "che", "baz"]] = 2
        d[["foo", "che", "boo", "far"]] = 3

        td = {
            "bar": 1,
            "baz": 2,
            "far": 3,
        }

        for ks, v in d.leaves():
            self.assertEqual(td[ks[-1]], v.value)

        count = 0
        for ks, v in d.leaves(1):
            count += 1
        self.assertEqual(0, count)

        count = 0
        for ks, v in d.leaves(2):
            count += 1
        self.assertEqual(1, count)

    def test_tree_properties(self):
        d = DictTree()
        self.assertEqual(None, d.parent)

        d[["foo", "bar"]] = 1
        self.assertEqual(d, d.get_node("foo").parent)
        self.assertEqual("foo", d.get_node("foo").key)

        d[["foo", "baz", "che"]] = 2
        self.assertEqual("baz", d.get_node(["foo", "baz"]).key)
        self.assertEqual(["foo", "baz"], d.get_node(["foo", "baz"]).pathkeys)

        self.assertEqual(d, d.get_node(["foo", "baz"]).root)

        # root should have an empty list as keys
        self.assertEqual([], d.pathkeys)

    def test_get_node(self):
        d = DictTree([
            (["foo", "bar"], 1),
            (["foo", "che"], 2),
        ])
        self.assertEqual(1, len(d))
        self.assertEqual(2, len(d.get_node(["foo"])))
        self.assertEqual(0, len(d.get_node(["foo", "bar"])))
        self.assertEqual(0, len(d.get_node(["foo", "che"])))

        with self.assertRaises(KeyError):
            d.get_node(["DOES-NOT-EXIST"])

    def test___getitem__(self):
        d = DictTree([
            ("foo", 1),
            (["foo", "bar"], 2),
        ])

        self.assertEqual(1, d["foo"])
        self.assertEqual(1, d[["foo"]])
        self.assertEqual(2, d[["foo", "bar"]])
        self.assertEqual(2, d["foo", "bar"])

    def test___init__(self):
        d = DictTree(
            [
                (["foo", "bar"], 1),
            ],
            foo=2
        )
        self.assertEqual(2, d["foo"])

        d = DictTree([
            (["foo", "bar"], 1),
            (["foo", "che"], 2),
        ])

        self.assertEqual(1, d[["foo", "bar"]])
        self.assertEqual(2, d["foo", "che"])
        self.assertEqual(1, len(d))
        self.assertEqual(2, len(d.get_node("foo")))

    def test_walk_1(self):
        d = DictTree()
        d[["foo", "bar"]] = 1
        d[["foo", "che", "baz"]] = 2
        d[["foo", "che", "boo", "far"]] = 3

        it = d.walk(["foo", "che", "boo", "far"])
        ks, sd = it.__next__()
        self.assertEqual(["foo"], ks)
        ks, sd = it.__next__()
        self.assertEqual(["foo", "che"], ks)
        ks, sd = it.__next__()
        self.assertEqual(["foo", "che", "boo"], ks)
        ks, sd = it.__next__()
        self.assertEqual(["foo", "che", "boo", "far"], ks)
        self.assertEqual(3, sd.value)

    def test_walk_set_missing(self):
        d = DictTree()

        it = d.walk(["foo", "che", "boo"], set_missing=True)
        ks, sd = it.__next__()
        self.assertEqual(["foo"], ks)
        self.assertIsNone(sd.value)
        ks, sd = it.__next__()
        self.assertEqual(["foo", "che"], ks)
        self.assertIsNone(sd.value)
        ks, sd = it.__next__()
        self.assertEqual(["foo", "che", "boo"], ks)
        self.assertIsNone(sd.value)

    def test_nodes(self):
        d = DictTree()
        d[["foo", "bar"]] = 1
        d[["foo", "che", "baz"]] = 2
        d[["foo", "che", "boo", "far"]] = 3

        keys = set([
            tuple(),
            ("foo",),
            ("foo", "bar"),
            ("foo", "che"),
            ("foo", "che", "baz"),
            ("foo", "che", "boo"),
            ("foo", "che", "boo", "far"),
        ])

        for nkeys, n in d.nodes():
            keys.remove(tuple(nkeys))
        self.assertEqual(0, len(keys))

        it = d.nodes()
        ks, n = it.__next__()
        self.assertEqual(tuple(), tuple(ks))

        ks, n = it.__next__()
        self.assertEqual(("foo",), tuple(ks))

        keys = set([
            ("foo", "bar"),
            ("foo", "che"),
        ])
        keys.remove(tuple(it.__next__()[0]))
        keys.remove(tuple(it.__next__()[0]))
        self.assertEqual(0, len(keys))

        keys = set([
            ("foo", "che", "baz"),
            ("foo", "che", "boo"),
        ])
        keys.remove(tuple(it.__next__()[0]))
        keys.remove(tuple(it.__next__()[0]))
        self.assertEqual(0, len(keys))

        ks, n = it.__next__()
        self.assertEqual(("foo", "che", "boo", "far"), tuple(ks))



class OrderedSetTest(TestCase):
    def test_order(self):
        s = OrderedSet()

        s.add(1)
        s.add(10)
        s.add(5)
        s.add(10)

        self.assertEqual([1, 10, 5], list(s))

        self.assertEqual(1, s.pop())
        self.assertEqual(10, s.pop())
        self.assertEqual(5, s.pop())

        with self.assertRaises(KeyError):
            s.pop()

