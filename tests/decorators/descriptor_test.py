# -*- coding: utf-8 -*-
from collections import Counter

from datatypes.compat import *
from datatypes.decorators.descriptor import (
    property,
    classproperty,
    method,
    classmethod,
    instancemethod,
    staticmethod,
    aliasmethods,
)

from . import TestCase, testdata


class ClassmethodTest(TestCase):
    def test_instancemethod(self):
        class Foo(object):
            @classmethod
            def bar(cls, *args, **kwargs):
                return f"classmethod {args[0]}"

            @bar.instancemethod
            def bar(self, *args, **kwargs):
                return f"instancemethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @classmethod
            def che_class(cls, *args, **kwargs):
                return cls.bar(*args, **kwargs)

        self.assertEqual("classmethod 1", Foo.bar(1))
        self.assertEqual("classmethod 2", Foo.che_class(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))


class InstancemethodTest(TestCase):
    def test_staticmethod(self):
        class Foo(object):
            @instancemethod
            def bar(self, *args, **kwargs):
                return f"instancemethod {args[0]}"

            @bar.staticmethod
            def bar(*args, **kwargs):
                return f"staticmethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @staticmethod
            def che_static(*args, **kwargs):
                return Foo.bar(*args, **kwargs)

        self.assertEqual("staticmethod 1", Foo.bar(1))
        self.assertEqual("staticmethod 2", Foo.che_static(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))

    def test_classmethod(self):
        class Foo(object):
            @instancemethod
            def bar(self, *args, **kwargs):
                return f"instancemethod {args[0]}"

            @bar.classmethod
            def bar(cls, *args, **kwargs):
                return f"classmethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @classmethod
            def che_class(cls, *args, **kwargs):
                return Foo.bar(*args, **kwargs)

        self.assertEqual("classmethod 1", Foo.bar(1))
        self.assertEqual("classmethod 2", Foo.che_class(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))


class StaticmethodTest(TestCase):
    def test_staticmethod(self):
        class Foo(object):
            @staticmethod
            def bar(*args, **kwargs):
                return f"staticmethod {args[0]}"

            @bar.instancemethod
            def bar(self, *args, **kwargs):
                return f"instancemethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @staticmethod
            def che_static(*args, **kwargs):
                return Foo.bar(*args, **kwargs)

        self.assertEqual("staticmethod 1", Foo.bar(1))
        self.assertEqual("staticmethod 2", Foo.che_static(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))


class MethodTest(TestCase):
    def test_swap(self):
        class Foo(object):
            @method
            def bar(self):
                return "instancemethod"

            @bar.classmethod
            def bar(cls, v):
                return f"classmethod {v}"

            @method
            def che(cls, v):
                return f"classmethod {v}"

            @che.instancemethod
            def che(cls):
                return "instancemethod"

        f = Foo()
        self.assertEqual("instancemethod", f.bar())
        self.assertEqual("classmethod 1", Foo.bar(1))

        self.assertEqual("instancemethod", f.che())
        self.assertEqual("classmethod 2", Foo.che(2))

    def test_method(self):
        class Foo(object):
            @method
            def bar(cls, *args, **kwargs):
                return f"staticmethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @classmethod
            def che_class(cls, *args, **kwargs):
                return cls.bar(*args, **kwargs)

        self.assertEqual("staticmethod 1", Foo.bar(1))
        self.assertEqual("staticmethod 2", Foo.che_class(2))

        f = Foo()
        self.assertEqual("staticmethod 3", f.bar(3))
        self.assertEqual("staticmethod 4", f.che_instance(4))
        self.assertEqual("staticmethod 5", f.che_class(5))

    def test_staticmethod(self):
        class Foo(object):
            @method
            def bar(cls, *args, **kwargs):
                return f"instancemethod {args[0]}"

            @bar.staticmethod
            def bar(*args, **kwargs):
                return f"staticmethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @staticmethod
            def che_static(*args, **kwargs):
                return Foo.bar(*args, **kwargs)

        self.assertEqual("staticmethod 1", Foo.bar(1))
        self.assertEqual("staticmethod 2", Foo.che_static(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))

    def test_instancemethod(self):
        class Foo(object):
            @method
            def bar(cls, *args, **kwargs):
                return f"classmethod {args[0]}"

            @bar.instancemethod
            def bar(self, *args, **kwargs):
                return f"instancemethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @classmethod
            def che_class(cls, *args, **kwargs):
                return cls.bar(*args, **kwargs)

        self.assertEqual("classmethod 1", Foo.bar(1))
        self.assertEqual("classmethod 2", Foo.che_class(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))

    def test_classmethod(self):
        class Foo(object):
            @method
            def bar(cls, *args, **kwargs):
                return f"instancemethod {args[0]}"

            @bar.classmethod
            def bar(cls, *args, **kwargs):
                return f"classmethod {args[0]}"

            def che_instance(self, *args, **kwargs):
                return self.bar(*args, **kwargs)

            @classmethod
            def che_class(cls, *args, **kwargs):
                return cls.bar(*args, **kwargs)

        self.assertEqual("classmethod 1", Foo.bar(1))
        self.assertEqual("classmethod 2", Foo.che_class(2))

        f = Foo()
        self.assertEqual("instancemethod 3", f.bar(3))
        self.assertEqual("instancemethod 4", f.che_instance(4))


class ClassPropertyTest(TestCase):
    def test_readonly(self):
        class Foo(object):
            @classproperty
            def bar(cls):
                return 42

        self.assertEqual(42, Foo.bar)

        f = Foo()
        self.assertEqual(42, f.bar)

        Foo.bar = 43
        self.assertEqual(43, f.bar)

        f.bar = 44
        self.assertEqual(44, f.bar)

        with self.assertRaises(TypeError):
            class Foo(object):
                @classproperty
                def bar(cls):
                    return 42

                @bar.setter
                def bar(cls, v):
                    pass

        with self.assertRaises(TypeError):
            class Foo(object):
                @classproperty
                def bar(cls):
                    return 42

                @bar.deleter
                def bar(cls, v):
                    pass

        class Foo(object):
            bar = classproperty(lambda *_: 45, "this is the doc")

        self.assertEqual(45, Foo.bar)


class PropertyTest(TestCase):
    def test_set_init(self):
        counts = Counter()
        def fget(self):
            counts["fget"] += 1
            return self._v

        def fset(self, v):
            counts["fset"] += 1
            self._v = v

        def fdel(self):
            counts["fdel"] += 1
            del self._v

        class FooPropInit(object):
            v = property(fget, fset, fdel, "this is v")
        f = FooPropInit()
        f.v = 6
        self.assertEqual(6, f.v)
        self.assertEqual(2, sum(counts.values()))
        del f.v
        self.assertEqual(3, sum(counts.values()))

        counts = Counter()
        class FooPropInit2(object):
            v = property(fget=fget, fset=fset, fdel=fdel, doc="this is v")
        f = FooPropInit2()
        f.v = 6
        self.assertEqual(6, f.v)
        self.assertEqual(2, sum(counts.values()))
        del f.v
        self.assertEqual(3, sum(counts.values()))

    def test_decorate_init(self):
        counts = Counter()
        class FooPropInit(object):
            @property
            def v(self):
                counts["fget"] += 1
                return self._v

            @v.setter
            def v(self, v):
                counts["fset"] += 1
                self._v = v

            @v.deleter
            def v(self):
                counts["fdel"] += 1
                del self._v

        f = FooPropInit()
        f.v = 6
        self.assertEqual(6, f.v)
        self.assertEqual(2, sum(counts.values()))
        del f.v
        self.assertEqual(3, sum(counts.values()))

    def test_decorate_no_call(self):
        class FooPropInit(object):
            @property
            def v(self):
                return 1

        f = FooPropInit()
        self.assertEqual(1, f.v)

        with self.assertRaises(AttributeError):
            f.v = 6

        with self.assertRaises(AttributeError):
            del f.v

    def test_decorate_call(self):
        class FooPropInit(object):
            @property(cached="_v")
            def v(self):
                return 1

        f = FooPropInit()
        self.assertEqual(1, f.v)

        f.v = 6
        self.assertEqual(6, f.v)

        del f.v
        self.assertEqual(1, f.v)

    def test_cached_no_allow_empty(self):
        counts = Counter()
        class PAE(object):
            @property(cached="_foo", allow_empty=False)
            def foo(self):
                counts["fget"] += 1
                return 0

        c = PAE()
        self.assertEqual(0, c.foo)
        self.assertEqual(0, c.foo)
        self.assertEqual(0, c.foo)
        self.assertEqual(3, counts["fget"])

        c.foo = 1
        self.assertEqual(1, c.foo)
        self.assertEqual(3, counts["fget"])

    def test_cached_setter(self):
        class WPS(object):
            foo_get = False
            foo_set = False
            foo_del = False

            @property(cached="_foo")
            def foo(self):
                self.foo_get = True
                return 1

            @foo.setter
            def foo(self, val):
                self.foo_set = True
                self._foo = val

            @foo.deleter
            def foo(self):
                self.foo_del = True
                del(self._foo)

        c = WPS()

        self.assertEqual(1, c.foo)

        c.foo = 5
        self.assertEqual(5, c.foo)

        del(c.foo)
        self.assertEqual(1, c.foo)

        self.assertTrue(c.foo_get)
        self.assertTrue(c.foo_set)
        self.assertTrue(c.foo_del)

    def test_cached_sharing(self):
        class Foo(object):
            @property(cached="_bar")
            def bar(self):
                return 1

        f = Foo()
        self.assertEqual(1, f.bar)

        f.bar = 2
        self.assertEqual(2, f.bar)

        f2 = Foo()
        self.assertEqual(1, f2.bar)

        f2.bar = 3
        self.assertNotEqual(f.bar, f2.bar)

    def test_strange_behavior(self):
        class BaseFoo(object):
            def __init__(self):
                setattr(self, 'bar', None)

            def __setattr__(self, n, v):
                super(BaseFoo, self).__setattr__(n, v)

        class Foo(BaseFoo):
            @property(cached="_bar", allow_empty=False)
            def bar(self):
                return 1

        f = Foo()
        self.assertEqual(1, f.bar)

        f.bar = 2
        self.assertEqual(2, f.bar)

    def test___dict___direct(self):
        """this is a no win situation

        if you have a bar property and a __setattr__ that modifies directly then
        the other property methods like __set__ will not get called, and you can't
        have property.__get__ look for the original name because there are times
        when you want your property to override a parent's original value for the
        property, so I've chosen to just ignore this case and not support it
        """
        class Foo(object):
            @property(cached="_bar")
            def bar(self):
                return 1
            def __setattr__(self, field_name, field_val):
                self.__dict__[field_name] = field_val
                #super(Foo, self).__setattr__(field_name, field_val)

        f = Foo()
        f.bar = 2 # this will be ignored
        self.assertEqual(1, f.bar)

    def test_lifecycle(self):
        class WP(object):
            counts = Counter()
            @property
            def foo(self):
                self.counts["foo"] += 1
                return 1

            @property()
            def baz(self):
                self.counts["baz"] += 1
                return 2

            @property(cached="_bar")
            def bar(self):
                self.counts["bar"] += 1
                return 3

            @property(cached="_che")
            def che(self):
                self.counts["che"] += 1
                return 4

        c = WP()
        r = c.foo
        self.assertEqual(1, r)
        with self.assertRaises(AttributeError):
            c.foo = 2
        with self.assertRaises(AttributeError):
            del(c.foo)
        c.foo
        c.foo
        self.assertEqual(3, c.counts["foo"])

        r = c.baz
        self.assertEqual(2, r)
        with self.assertRaises(AttributeError):
            c.baz = 3
        with self.assertRaises(AttributeError):
            del(c.baz)

        r = c.bar
        self.assertEqual(3, r)
        self.assertEqual(3, c._bar)
        c.bar = 4
        self.assertEqual(4, c.bar)
        self.assertEqual(4, c._bar)
        del(c.bar)
        r = c.bar
        self.assertEqual(3, r)
        self.assertEqual(2, c.counts["bar"])

        r = c.che
        self.assertEqual(4, r)
        self.assertEqual(4, c._che)
        c.che = 4
        self.assertEqual(4, c.che)
        del(c.che)
        r = c.che
        self.assertEqual(4, r)

    def test_issue_4(self):
        """https://github.com/Jaymon/decorators/issues/4"""
        class Foo(object):
            @property
            def che(self):
                raise AttributeError("This error is caught")

        class Bar(object):
            @property
            def che(self):
                raise AttributeError("This error is lost")
            @property
            def baz(self):
                raise KeyError("_baz")
            def __getattr__(self, k):
                return 1

        b = Bar()
        with testdata.capture() as c:
            b.che
        self.assertTrue("This error is lost" in c)

        with self.assertRaises(KeyError):
            b.baz

        f = Foo()
        with self.assertRaises(AttributeError):
            f.che

    def test_setter_kwarg(self):
        class Foo(object):
            @property(setter="_che")
            def che(self, v):
                self._che = v

        f = Foo()
        f.che = 4
        self.assertEqual(4, f.che)

        class Foo(object):
            @property(deleter="_che")
            def che(self):
                del self._che

        f = Foo()
        f.che = 5
        self.assertEqual(5, f.che)

        del f.che

        with self.assertRaises(AttributeError):
            f.che

    def test_readonly(self):
        class Foo(object):
            @property(readonly="_che")
            def che(self):
                print("che getter")
                return 5

        f = Foo()

        with testdata.capture() as o:
            r = f.che
        self.assertEqual(5, r)
        self.assertTrue("che getter" in o)

        with testdata.capture() as o:
            r = f.che
        self.assertEqual(5, r)
        self.assertFalse("che getter" in o)

        with self.assertRaises(AttributeError):
            f.che = 4

        with self.assertRaises(AttributeError):
            del f.che

    def test_empty(self):
        class Foo(object):
            @property(readonly="_che")
            def che(self):
                print("che getter")
                return []

        f = Foo()
        self.assertEqual([], f.che)
        self.assertEqual([], f.che)
        self.assertEqual([], f.che)

    def test_onget(self):
        class Foo(object):
            @property(cached="_che", onget=False)
            def che(self):
                return 1

        f = Foo()
        for _ in range(10):
            self.assertEqual(1, f.che)

        f.che = 5
        self.assertEqual(5, f.che)

        del f.che
        self.assertEqual(1, f.che)

    def test_multiple_one_with_setter(self):
        class Foo(object):
            bar_count = 0
            baz_count = 0
            che_count = 0

            @property(cached="_bar")
            def bar(self):
                self.bar_count += 1
                return self.bar_count

            @builtins.property
            def che(self):
                self.che_count += 1
                return self.che_count

            @property(cached="_baz")
            def baz(self):
                self.baz_count += 1
                return self.baz_count

            @baz.setter
            def baz(self, v):
                self.baz_count = v
                self._baz = v

        f = Foo()
        r1 = f.bar
        r2 = f.bar
        self.assertEqual(r1, r2)

        r1 = f.che
        r2 = f.che
        self.assertNotEqual(r1, r2)

        r1 = f.baz
        r2 = f.baz
        self.assertEqual(r1, r2)


class AliasMethodsTest(TestCase):
    """
    https://github.com/Jaymon/datatypes/issues/49
    """
    def test___set_name__(self):
        class Foo(object):
            @aliasmethods("bar", "che")
            def foo(self, *args, **kwargs):
                return 1

        f = Foo()
        self.assertEqual(1, f.foo())
        self.assertEqual(1, f.bar())
        self.assertEqual(1, f.che())

        # this didn't work because property causes __set_name__ to not be
        # called
#     def test_property(self):
#         class Foo(object):
#             @property
#             @aliasmethods("bar")
#             def foo(self, *args, **kwargs):
#                 return 2
# 
#         f = Foo()
#         self.assertEqual(2, f.foo)
#         self.assertEqual(2, f.bar)


