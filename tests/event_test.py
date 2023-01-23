# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.event import Event, Extend
from . import TestCase


class EventTest(TestCase):
    def setUp(self):
        event = Event()
        event.reset()

    def test_singleton(self):
        e = Event()
        e2 = Event()
        self.assertTrue(e is e2)

    def test_push_and_bind(self):
        ev = Event()

        @ev("push_and_bind")
        def push1(event):
            event.text += "1"

        r1 = ev.push("push_and_bind", text="1")

        @ev("push_and_bind")
        def push2(event):
            event.text += "2"

        r2 = ev.push("push_and_bind", text="2")

        @ev("push_and_bind")
        def push3(event):
            event.text += "3"

        self.assertEqual("1123", r1.text)
        self.assertEqual("2123", r2.text)

    def test_broadcast(self):
        ev = Event()

        r = ev.broadcast("foo", count=0)
        self.assertEqual(0, r.count)

        def cb1(event):
            event.count += 1
        ev.bind("foo", cb1)

        r = ev.broadcast("foo", count=0)
        self.assertEqual(1, r.count)

        r = ev.broadcast("foo", count=r.count)
        self.assertEqual(2, r.count)

    def test_once(self):
        ev = Event()

        @ev("once")
        def once1(event):
            pass

        @ev("once")
        def once2(event):
            pass

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("once1" in logs)
        self.assertTrue("once2" in logs)

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("ignored" in logs)

        @ev("once")
        def once3(event):
            pass

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertFalse("once1" in logs)
        self.assertFalse("once2" in logs)
        self.assertTrue("once3" in logs)

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("ignored" in logs)


class ExtendTest(TestCase):
    def test_property(self):
        c = self.create_config()
        ex = Extend()

        self.assertEqual(None, c.foo_test)

        @ex.property(c, "foo_test")
        def foo_test(self):
            return 42
        self.assertEqual(42, c.foo_test)

        @ex(c, "foo_test")
        @property
        def foo2_test(self):
            return 43
        self.assertEqual(43, c.foo_test)

    def test_method(self):
        c = self.create_config()
        ex = Extend()

        with self.assertRaises(TypeError):
            c.foo(1, 2)

        @ex.method(c, "foo")
        def foo(self, n1, n2):
            return n1 + n2
        self.assertEqual(3, c.foo(1, 2))

        @ex(c, "foo")
        def foo2(self, n1, n2):
            return n1 * n2
        self.assertEqual(2, c.foo(1, 2))

    def test_class(self):
        extend = Extend()
        class Foo(object): pass

        @extend(Foo, "bar")
        def bar(self, n1, n2):
            return n1 + n2

        f = Foo()
        self.assertEqual(3, f.bar(1, 2))

        @extend(f, "che")
        @property
        def che(self):
            return 42

        self.assertEqual(42, f.che)

        @extend(Foo, "boo")
        def boo(self):
            return 43
        self.assertEqual(43, f.boo())

    def test_inheritance(self):
        extend = Extend()
        class FooPage(Page):
            def __init__(self): pass

        @extend(Page, "bar")
        def bar(self, n1, n2):
            return n1 + n2

        f = FooPage()
        self.assertEqual(3, f.bar(1, 2))




