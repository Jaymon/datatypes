# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.reflection import Extend
from . import TestCase


class ExtendTest(TestCase):
    def test_property(self):
        class Foo(object): pass

        c = Foo()
        ex = Extend()

        with self.assertRaises(AttributeError):
            c.foo_test

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
        class Foo(object): pass
        c = Foo()
        ex = Extend()

        with self.assertRaises(AttributeError):
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
        class ParentFoo(object): pass
        class Foo(ParentFoo): pass

        @extend(ParentFoo, "bar")
        def bar(self, n1, n2):
            return n1 + n2

        f = Foo()
        self.assertEqual(3, f.bar(1, 2))

