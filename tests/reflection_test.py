# -*- coding: utf-8 -*-
import sys
import functools

from datatypes.compat import *
from datatypes.reflection import (
    Extend,
    ReflectName,
    ReflectModule,
    ReflectClass,
    ReflectMethod,
    ReflectDecorator,
    OrderedSubclasses,
    ReflectPath,
    ReflectCallable,
)
from datatypes.path import Dirpath
from . import TestCase, testdata


class OrderedSubclassesTest(TestCase):
    """
    NOTE -- I've learned that this is now an incredibly difficult class to test
    because it is a vital class to testdata, so if it starts failing then you
    can't even get to the test because testdata will raise an error as it
    starts up
    """
    def test_edges_1(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Base): pass
        class Che(Foo): pass

        scs = OrderedSubclasses(classes=[Che, Foo, Base, Bar])

        r = set([Bar, Che])
        for count, c in enumerate(scs.edges(), 1):
            self.assertTrue(c in r)
        self.assertEqual(2, count)

    def test_edges_2(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Base): pass
        class Che(Foo): pass
        class Baz(Foo, Bar): pass

        scs = OrderedSubclasses(classes=[Che, Foo, Base, Bar, Baz])

        r = set([Baz, Che])
        for count, c in enumerate(scs.edges(), 1):
            self.assertTrue(c in r)
        self.assertEqual(2, count)

    def test_edges_3(self):
        class Base1(object): pass
        class Base2(Base1): pass
        class Base3(Base2): pass
        class Foo(Base2): pass
        class Bar(Base3): pass
        class Che(Base3): pass

        scs = OrderedSubclasses(classes=[Base2, Base3, Foo, Bar, Che])

        r = set([Che, Bar, Foo])
        for count, c in enumerate(scs.edges(), 1):
            self.assertTrue(c in r)
        self.assertEqual(3, count)

    def test_edges_4(self):
        class Foo(object): pass
        class Bar(Foo): pass

        scs = OrderedSubclasses(classes=[Bar])
        self.assertEqual([Bar], list(scs.edges()))

    def test_remove(self):
        class Base1(object): pass
        class Base2(Base1): pass
        class Base3(Base2): pass
        class Foo(Base2): pass
        class Bar(Base3): pass
        class Che(Base3): pass

        scs = OrderedSubclasses(classes=[Base2, Base3, Foo, Bar, Che])

        edges = set(scs.edges())
        self.assertEqual(3, len(edges))
        self.assertTrue(Bar in edges)

        scs.remove(Bar)
        edges = set(scs.edges())
        self.assertEqual(2, len(edges))
        self.assertFalse(Bar in edges)

    def test_insert_1(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        called = {
            "_insert_sub": 0,
            "_insert_edge": 0
        }

        class MockSubclasses(OrderedSubclasses):
            def _insert(self, klass, klass_info):
                super()._insert(klass, klass_info)
                if klass_info["edge"]:
                    called["_insert_edge"] += 1 

                else:
                    called["_insert_sub"] += 1 

        scs = MockSubclasses()
        scs.insert(Bar)
        scs.insert(Foo)
        scs.insert(Che)
        scs.insert(Bar)

        self.assertEqual(2, called["_insert_edge"])

    def test_insert_2(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        class MockSubclasses(OrderedSubclasses):
            def get_child_counts(self):
                d = {}
                for classpath, info in self.info.items():
                    d[classpath] = info["child_count"]
                return d

        ocs = MockSubclasses(
            classes=[Base, Foo, Bar, Che],
            cutoff_classes=(Base,)
        )
        info = ocs.get_child_counts()

        ocs.insert(Bar)
        info2 = ocs.get_child_counts()
        self.assertEqual(info, info2)

    def test_order(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        order = [Che, Bar, Foo, Base, object]

        ocs = OrderedSubclasses(classes=[Base, Foo, Bar, Che])
        self.assertEqual(order, list(ocs))

        ocs = OrderedSubclasses(classes=[Che, Bar, Foo, Base])
        self.assertEqual(order, list(ocs))

    def test_getmro(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        ocs = OrderedSubclasses(
            cutoff_classes=[Base],
            classes=[Base, Foo, Bar, Che],
            insert_cutoff_classes=False,
        )

        orders = []
        for c in ocs.getmro(Bar):
            orders.append(c)
        self.assertEqual([Bar, Foo], orders)


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


class ReflectNameTest(TestCase):
    def test_current_syntax(self):
        p = ReflectName("foo.bar.che:FooBar.baz")
        self.assertEqual("foo.bar.che", p.module_name)
        self.assertEqual("", p.filepath)
        self.assertEqual("FooBar", p.class_name)
        self.assertEqual("baz", p.method_name)

        p = ReflectName("foo/bar/che.py:FooBar.baz")
        self.assertEqual("", p.module_name)
        self.assertEqual("foo/bar/che.py", p.filepath)
        self.assertEqual("FooBar", p.class_name)
        self.assertEqual("baz", p.method_name)

    def test_previous_syntax_1(self):
        p = ReflectName("foo.bar.che.FooBar.baz")
        self.assertEqual("foo.bar.che:FooBar.baz", p)
        self.assertEqual("foo.bar.che", p.module_name)
        self.assertEqual("", p.filepath)
        self.assertEqual("FooBar", p.class_name)
        self.assertEqual("baz", p.method_name)

    def test_previous_syntax_2(self):
        p = ReflectName("foo.bar.che.baz")
        self.assertEqual("foo.bar.che.baz", p.module_name)
        self.assertEqual("", p.filepath)
        self.assertEqual("", p.class_name)
        self.assertEqual("", p.method_name)

    def test_relative_module_name(self):
        p = ReflectName("foo.bar.che.boo")
        smpath = p.relative_module_name("bar")
        self.assertEqual("che.boo", smpath)

        smpath = p.relative_module_name("bar.che")
        self.assertEqual("boo", smpath)

        smpath = p.relative_module_name(".bar.che.")
        self.assertEqual("boo", smpath)

        smpath = p.relative_module_name("foo")
        self.assertEqual("bar.che.boo", smpath)

        smpath = p.relative_module_name("boo")
        self.assertEqual("", smpath)

        with self.assertRaises(ValueError):
            p.relative_module_name("baz")

    def test_absolute_module_name(self):
        p = ReflectName("foo.bar.che.boo")

        smpath = p.absolute_module_name("boo")
        self.assertEqual("foo.bar.che.boo", smpath)

        smpath = p.absolute_module_name("bar")
        self.assertEqual("foo.bar", smpath)

        smpath = p.absolute_module_name("bar.che")
        self.assertEqual("foo.bar.che", smpath)

        smpath = p.absolute_module_name(".bar.che.")
        self.assertEqual("foo.bar.che", smpath)

        smpath = p.absolute_module_name("foo")
        self.assertEqual("foo", smpath)

        smpath = p.absolute_module_name("boo")
        self.assertEqual("foo.bar.che.boo", smpath)

        with self.assertRaises(ValueError):
            p.absolute_module_name("baz")

    def test_class_names(self):
        p = ReflectName("<run_path>:Foo.Bar")
        self.assertEqual(["Foo", "Bar"], p.class_names)

        p = ReflectName("mod1.mod2.mod3:Foo.bar.<locals>.Che.boo")
        self.assertEqual(["<locals>", "Che", "boo"], p.unresolvable)

    def test_get_classes(self):
        m = self.create_module([
            "class Foo(object):",
            "    class Bar(object):",
            "        class Che(object):",
            "            pass",
        ])
        p = ReflectName(f"{m}:Foo.Bar.Che")

        it = p.get_classes()
        c = it.__next__()
        self.assertEqual("Foo", c.__name__)
        c = it.__next__()
        self.assertEqual("Bar", c.__name__)
        c = it.__next__()
        self.assertEqual("Che", c.__name__)

        with self.assertRaises(StopIteration):
            it.__next__()

    def test_get_module_names_1(self):
        m = self.create_module([
            "class Foo(object):",
            "    pass",
        ], count=3)

        p = ReflectName(f"{m}:Foo")
        ms = list(p.get_module_names())
        self.assertEqual(3, len(ms))
        self.assertEqual(m, ms[-1])

    def test_get_module_names_module_name(self):
        p = ReflectName("foo.bar.che.baz.boo")
        ms = list(p.get_module_names("bar.che.baz"))
        self.assertEqual(3, len(ms))
        self.assertTrue("foo.bar" in ms)
        self.assertTrue("foo.bar.che.baz" in ms)
        self.assertFalse("foo" in ms)
        self.assertFalse("foo.bar.che.baz.boo" in ms)

        ms = list(p.get_module_names("moo"))
        self.assertEqual([], ms)

    def test_reflect_modules_1(self):
        p = ReflectName("<run_path>:Foo.Bar")
        ms = list(p.reflect_modules())
        self.assertEqual(0, len(ms))

    def test_reflect_modules_module_name(self):
        m = self.create_module({
            "foo": {
                "bar": {
                    "che": "",
                },
            }
        })
        p = ReflectName(f"{m}.foo.bar.che")
        for rm in p.reflect_modules("foo.bar"):
            if rm.module_name.endswith(".foo"):
                pass

            elif rm.module_name.endswith(".foo.bar"):
                pass

            else:
                raise AssertionError(rm.module_name)


class ReflectCallableTest(TestCase):
    def test_get_docblock_comment(self):
        m = self.create_module([
            "",
            "def _ignore(): pass",
            "",
            "# here is comment line 1",
            "# here is comment line 2",
            "def foo(*args, **kwargs):",
            "    pass",
        ])

        rf = ReflectCallable(m.get_module().foo)
        doc = rf.get_docblock()
        for v in ["comment line 1", "comment line 2", "\n"]:
            self.assertTrue(v in doc)

    def test_get_docblock_docstring(self):
        m = self.create_module([
            "def foo(*args, **kwargs):",
            "    \"\"\"here is comment line 1",
            "    here is comment line 2:",
            "",
            "        Indented line 1",
            "    \"\"\"",
            "    pass",
        ])

        rf = ReflectCallable(m.get_module().foo)
        doc = rf.get_docblock()
        for v in ["comment line 1", "comment line 2", "\n", " Indented"]:
            self.assertTrue(v in rf.get_docblock())

    def test_get_docblock_inherit(self):
        m = self.create_module("""
            class Foo(object):
                def foo():
                    '''Foo.foo'''
                    pass

            class Bar(Foo):
                def foo():
                    pass
        """)

        rf = ReflectCallable(m.get_module().Bar.foo)
        doc = rf.get_docblock(inherit=False)
        self.assertEqual("", doc)

    def test_get_module(self):
        m = self.create_module("""
            class Foo(object):
                def foo():
                    pass

            def foo():
                pass
        """).get_module()

        rf = ReflectCallable(m.foo)
        self.assertEqual(m, rf.get_module())

        rf = ReflectCallable(m.Foo.foo)
        self.assertEqual(m, rf.get_module())

    def test_get_class(self):
        RC = ReflectCallable
        m = self.create_module([
            "class Foo(object):",
            "    @staticmethod",
            "    def static_foo(): return \"static_foo\"",
            "    @classmethod",
            "    def class_foo(cls): return \"class_foo\"",
            "    def method_foo(self): return \"method_foo\"",
            "",
            "def function_foo(): return \"function_foo\"",
            "",
            "class C:",
            "    def f(): pass",
            "    class D:",
            "        def g(): pass",
            "",
            # examples from: https://stackoverflow.com/a/25959545
            "import io",
            "bm1 = io.BytesIO().__enter__",
            "bm2 = set().union",
            "",
            "def x(self): pass",
            "class Z:",
            "    y = x",
            "    v = lambda self: \"lambda\"",
            "    z = (lambda: lambda: 1)()",
        ]).get_module()

        rf = RC(functools.partial(m.Foo.method_foo))
        self.assertEqual(m.Foo, rf.get_class())

        with self.assertRaises(ValueError):
            RC(m.Z.z).get_class()
        rf = RC(m.Z().z)
        self.assertEqual(m.Z, rf.get_class())

        rf = RC(m.Z.v)
        self.assertEqual(m.Z, rf.get_class())
        rf = RC(m.Z().v)
        self.assertEqual(m.Z, rf.get_class())

        # there just isn't any way to infer this one
        rf = RC(m.Z.y)
        self.assertIsNone(rf.get_class())

        # this one gets inferred correctly though because the class instance
        # binds the method
        rf = RC(m.Z().y)
        self.assertEqual(m.Z, rf.get_class())

        rf = RC(m.Foo.class_foo)
        self.assertEqual(m.Foo, rf.get_class())
        rf = RC(m.Foo().class_foo)
        self.assertEqual(m.Foo, rf.get_class())

        rf = RC(m.Foo.static_foo)
        self.assertEqual(m.Foo, rf.get_class())
        rf = RC(m.Foo().static_foo)
        self.assertEqual(m.Foo, rf.get_class())

        rf = RC(m.Foo.method_foo)
        self.assertEqual(m.Foo, rf.get_class())
        rf = RC(m.Foo().method_foo)
        self.assertEqual(m.Foo, rf.get_class())
        rf = RC(m.Foo.method_foo, m.Foo)
        self.assertEqual(m.Foo, rf.get_class())

        rf = RC(m.function_foo)
        self.assertIsNone(rf.get_class())

        rf = RC(m.bm1)
        self.assertEqual(m.io.BytesIO, rf.get_class())

        rf = RC(m.bm2)
        self.assertEqual(set, rf.get_class())

        rf = RC(m.C.D.g)
        self.assertEqual(m.C.D, rf.get_class())

        class Bar(object):
            def foo(self): pass
        with self.assertRaises(ValueError):
            RC(Bar.foo).get_class()
        rf = RC(Bar.foo, Bar)
        self.assertEqual(Bar, rf.get_class())

    def test_is_type_methods(self):
        RC = ReflectCallable
        m = self.create_module([
            "class Foo(object):",
            "    @staticmethod",
            "    def static_foo(): return \"static_foo\"",
            "    @classmethod",
            "    def class_foo(cls): return \"class_foo\"",
            "    def method_foo(self): return \"method_foo\"",
            "",
            "def function_foo(): return \"function_foo\"",
        ]).get_module()

        class Bar(object):
            def __call__(self): return "class call"

        for rf in [RC(m.function_foo), RC(m.function_foo)]:
            self.assertFalse(rf.is_staticmethod())
            self.assertTrue(rf.is_function())
            self.assertFalse(rf.is_method())
            self.assertFalse(rf.is_classmethod())
            self.assertFalse(rf.is_class())
            self.assertFalse(rf.is_instance())

        for rf in [RC(m.Foo.method_foo), RC(m.Foo().method_foo)]:
            self.assertFalse(rf.is_staticmethod())
            self.assertFalse(rf.is_function())
            self.assertTrue(rf.is_method())
            self.assertFalse(rf.is_classmethod())
            self.assertFalse(rf.is_class())
            self.assertFalse(rf.is_instance())

        for rf in [RC(m.Foo.class_foo), RC(m.Foo().class_foo)]:
            self.assertFalse(rf.is_staticmethod())
            self.assertFalse(rf.is_function())
            self.assertTrue(rf.is_method())
            self.assertTrue(rf.is_classmethod())
            self.assertFalse(rf.is_class())
            self.assertFalse(rf.is_instance())

        for rf in [RC(m.Foo.static_foo), RC(m.Foo().static_foo)]:
            self.assertTrue(rf.is_staticmethod())
            self.assertFalse(rf.is_function())
            self.assertTrue(rf.is_method())
            self.assertFalse(rf.is_classmethod())
            self.assertFalse(rf.is_class())
            self.assertFalse(rf.is_instance())

        class Bar(object):
            def __call__(self): return "class call"

        rf = RC(Bar)
        self.assertFalse(rf.is_staticmethod())
        self.assertFalse(rf.is_function())
        self.assertFalse(rf.is_method())
        self.assertFalse(rf.is_classmethod())
        self.assertTrue(rf.is_class())
        self.assertFalse(rf.is_instance())

        rf = RC(Bar())
        self.assertFalse(rf.is_staticmethod())
        self.assertFalse(rf.is_function())
        self.assertFalse(rf.is_method())
        self.assertFalse(rf.is_classmethod())
        self.assertFalse(rf.is_class())
        self.assertTrue(rf.is_instance())

    def test_get_signature_info_positional_only(self):
        def foo(one, two, three=3, /): pass

        info = ReflectCallable(foo).get_signature_info()

        self.assertEqual(3, len(info["positional_only_names"]))
        for name in ["one", "two", "three"]:
            self.assertTrue(name in info["names"])

    def test_get_signature_info_keyword_only(self):
        def foo(one, two, *, three, four=4): pass

        info = ReflectCallable(foo).get_signature_info()

        self.assertEqual(2, len(info["keyword_only_names"]))
        for name in ["three", "four"]:
            self.assertTrue(name in info["names"])

    def test_get_signature_info_func(self):
        def foo(one, two, three=3, *args, **kwargs): pass

        rf = ReflectCallable(foo)
        info = rf.get_signature_info()

        self.assertEqual(3, len(info["names"]))
        for name in ["one", "two", "three"]:
            self.assertTrue(name in info["names"])

        self.assertEqual(2, len(info["required"]))
        for name in ["one", "two"]:
            self.assertTrue(name in info["required"])

        self.assertEqual(1, len(info["defaults"]))
        self.assertEqual(3, info["defaults"]["three"])

        self.assertEqual("args", info["positionals_name"])
        self.assertEqual("kwargs", info["keywords_name"])

    def test_get_signature_info_method_1(self):
        class Foo(object):
            #def foo(self): pass
            def foo(self, one, two, three=3, *args, **kwargs): pass

        rf = ReflectCallable(Foo.foo, Foo)
        info = rf.get_signature_info()

        self.assertEqual(3, len(info["names"]))
        for name in ["one", "two", "three"]:
            self.assertTrue(name in info["names"])

        self.assertEqual(2, len(info["required"]))
        for name in ["one", "two"]:
            self.assertTrue(name in info["required"])

        self.assertEqual(1, len(info["defaults"]))
        self.assertEqual(3, info["defaults"]["three"])

        self.assertEqual("args", info["positionals_name"])
        self.assertEqual("kwargs", info["keywords_name"])

    def test_get_signature_info_method_2(self):
        class Foo(object):
            def foo(self, foo, bar=1, che=3, **kwargs): pass

        sig = ReflectCallable(Foo.foo, Foo).get_signature_info()
        self.assertEqual(set(["foo"]), sig["required"])
        self.assertEqual(["foo", "bar", "che"], sig["names"])
        self.assertEqual(1, sig["defaults"]["bar"])
        self.assertEqual("kwargs", sig["keywords_name"])
        self.assertEqual("", sig["positionals_name"])

    def test_is_bound_method(self):
        RC = ReflectCallable
        class Foo(object):
            @classmethod
            def class_foo(cls, bar): pass
            @staticmethod
            def static_foo(bar): pass
            def method_foo(self, bar): pass

        rf = RC(Foo.method_foo, Foo)
        self.assertFalse(rf.is_bound_method())
        self.assertTrue(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

        rf = RC(Foo().method_foo, Foo)
        self.assertTrue(rf.is_bound_method())
        self.assertFalse(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

        rf = RC(Foo.class_foo, Foo)
        self.assertTrue(rf.is_bound_method())
        self.assertFalse(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

        rf = RC(Foo().class_foo, Foo)
        self.assertTrue(rf.is_bound_method())
        self.assertFalse(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

        rf = RC(Foo.static_foo, Foo)
        self.assertFalse(rf.is_bound_method())
        self.assertFalse(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

        rf = RC(Foo().static_foo, Foo)
        self.assertFalse(rf.is_bound_method())
        self.assertFalse(rf.is_unbound_method())
        info = rf.get_signature_info()
        self.assertEqual(["bar"], info["names"])

    def test_get_bind_info(self):
        class Foo(object):
            def foo(self, foo, bar=2, che=3, **kwargs): pass

        args = [1, 2, 3, 4]
        kwargs = {
            "foo": 10,
            "bar": 20,
            "che": 30,
            "boo": 40
        }
        info = ReflectCallable(Foo.foo, Foo).get_bind_info(*args, **kwargs)
        self.assertEqual([10, 20, 30], info["args"])
        self.assertEqual({"boo": 40}, info["kwargs"])
        self.assertEqual(args, info["unknown_args"])


class ReflectMethodTest(TestCase):
    def test_method_docblock_1(self):
        m = testdata.create_module([
            "class Foo(object):",
            "    '''controller docblock'''",
            "    def GET(*args, **kwargs):",
            "        '''method docblock'''",
            "        pass",
            "",
        ])

        rm = ReflectModule(m).reflect_class("Foo").reflect_method("GET")
        desc = rm.desc
        self.assertEqual("method docblock", desc)
 
    def test_method_docblock_bad_decorator(self):
        m = testdata.create_module([
            "def bad_dec(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "class Foo(object):",
            "    '''controller docblock'''",
            "    @bad_dec",
            "    def GET(*args, **kwargs):",
            "        '''method docblock'''",
            "        pass",
            "",
            "    def POST(*args, **kwargs):",
            "        '''should not return this docblock'''",
            "        pass",
            "",
        ])

        rm = ReflectModule(m).reflect_class("Foo").reflect_method("GET")
        desc = rm.desc
        self.assertEqual("method docblock", desc)


class ReflectClassTest(TestCase):
    def test_docblock_1(self):
        m = testdata.create_module([
            "class Foo(object):",
            "    '''this is a multiline docblock",
            "",
            "    this means it has...",
            "    ",
            "    multiple lines",
            "    '''",
            "    def GET(*args, **kwargs): pass",
            "",
        ])
        rc = ReflectModule(m).reflect_class("Foo")
        self.assertTrue("\n" in rc.desc)

    def test_get_docblock_inherit(self):
        m = self.create_module("""
            class Foo(object):
                '''Foo'''
                pass

            class Bar(Foo):
                pass
        """)
        rc = ReflectModule(m).reflect_class("Bar")
        doc = rc.get_docblock(inherit=False)
        self.assertEqual("", doc)

        idoc = rc.get_docblock(inherit=True)
        self.assertNotEqual(doc, idoc)

    def test_decorators_inherit_1(self):
        """make sure that a child class that hasn't defined a METHOD inherits
        the METHOD method from its parent with decorators in tact"""
        m = testdata.create_module([
            "def foodec(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "class _BaseController(object):",
            "    @foodec",
            "    def POST(self, **kwargs):",
            "        return 1",
            "",
            "class Default(_BaseController):",
            "    pass",
            "",
        ])
        rc = ReflectModule(m).reflect_class("Default")
        for count, rm in enumerate(rc.reflect_methods(), 1):
            self.assertEqual("foodec", rm.reflect_decorators()[0].name)
        self.assertEqual(1, count)

    def test_decorators_inherit_2(self):
        """you have a parent class with POST method, the child also has a POST
        method, what do you do? What. Do. You. Do?"""
        m = testdata.create_module([
            "def a(f):",
            "    def wrapped(*args, **kwargs):",
            "        return f(*args, **kwargs)",
            "    return wrapped",
            "",
            "class b(object):",
            "    def __init__(self, func):",
            "        self.func = func",
            "    def __call__(*args, **kwargs):",
            "        return f(*args, **kwargs)",
            "",
            "def c(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "def POST(): pass",
            "",
            "class D(object):",
            "    def HEAD(): pass"
            "",
            "class Parent(object):",
            "    @a",
            "    @b",
            "    def POST(self, **kwargs): pass",
            "",
            "    @a",
            "    @b",
            "    def HEAD(self): pass",
            "",
            "    @a",
            "    @b",
            "    def GET(self): pass",
            "",
            "class Child(Parent):",
            "    @c",
            "    def POST(self, **kwargs): POST()",
            "",
            "    @c",
            "    def HEAD(self):",
            "        d = D()",
            "        d.HEAD()",
            "",
            "    @c",
            "    def GET(self):",
            "        super(Default, self).GET()",
            "",
        ])

        rmod = ReflectModule(m)
        rc = rmod.reflect_class("Child")
        self.assertEqual(1, len(rc.reflect_method("POST").reflect_decorators()))
        self.assertEqual(1, len(rc.reflect_method("HEAD").reflect_decorators()))
        self.assertEqual(3, len(rc.reflect_method("GET").reflect_decorators()))

    def test_get_info(self):
        class Foo(object):
            def one(self, *args, **kwargs): pass
            def two(self, param1, param2): pass
            def three(self, param1, **kwargs): pass
            def four(self, param1, *args, **kwargs): pass
            @classmethod
            def five(cls, *args, **kwargs): pass

        rc = ReflectClass(Foo)
        self.assertEqual(5, len(rc.get_info()))

    def test_get_info_2(self):
        class FooParent(object):
            def one(self, *args, **kwargs): pass
            def two(self, param1, param2): pass

        class FooChild(FooParent):
            def one(self): pass
            def three(self, param1, **kwargs): pass

        rc = ReflectClass(FooChild)
        info = rc.get_info()
        self.assertEqual(3, len(info))
        self.assertTrue("two" in info)
        self.assertFalse(info["one"]["positionals"])
        self.assertFalse(info["one"]["keywords"])
        self.assertEqual(sys.modules[__name__], rc.get_module())

    def test_get_class(self):
        r = testdata.create_module([
            "def foo():",
            "    class FooCannotBeFound(object): pass",
        ])

        with self.assertRaises(AttributeError):
            ReflectClass.get_class(f"{r}:FooCannotBeFound")
            # this would be the object once you have the module:
            #     m.foo.__code__.co_consts
            # but I can't find anyway to take a code object and turn it into the
            # actual type instance. I tried eval() and exec() but they executed
            # but I couldn't get the class after running them

    def test_classpath_1(self):
        r = testdata.create_module([
            "class Foo(object):",
            "    class Bar(object): pass",
        ])

        rc = ReflectClass(r.module().Foo.Bar)
        self.assertTrue(rc.classpath.endswith(":Foo.Bar"))

    def test_classpath_2(self):
        class Foo(object):
            class Bar(object): pass

        qualname = ":ReflectClassTest.test_classpath_2.<locals>.Foo.Bar"
        rc = ReflectClass(Foo.Bar)
        self.assertTrue(rc.classpath.endswith(qualname))


class ReflectModuleTest(TestCase):
    def test_relative(self):
        modpath = "mmp_relative"
        r = testdata.create_modules({
            "foo": [
                "class Foo(object): pass",
            ],
            "bar": [
                "from datatypes.reflection import ReflectClass, ReflectModule",
                "",
                "class Bar(object):",
                "    def reflect(self):",
                "        return ReflectClass(type(self))",
                "",
                "    def reflect_foo_module(self):",
                "        return ReflectModule('..foo')",
            ],
        }, modpath=modpath)

        bar_class = getattr(r.module(f"{modpath}.bar"), "Bar")

        b = bar_class()
        rm = b.reflect_foo_module()
        m = rm.get_module()
        self.assertTrue(getattr(m, "Foo"))

    def test_mixed_modules_packages(self):
        """make sure a package with modules and other packages will resolve
        correctly"""
        modpath = "mmp"
        r = testdata.create_modules({
            "": [
                "class Default(object): pass",
            ],
            "foo": [
                "class Default(object): pass",
            ],
            "foo.bar": [
                "class Default(object): pass",
            ],
            "che": [
                "class Default(object): pass",
            ],
        }, modpath=modpath)

        r = ReflectModule(modpath)
        self.assertEqual(
            set([
                'mmp.foo',
                'mmp',
                'mmp.foo.bar',
                'mmp.che'
            ]),
            r.module_names()
        )

        # make sure just a file will resolve correctly
        modpath = "mmp2"
        testdata.create_module(modpath=modpath, data=[
            "class Bar(object): pass",
        ])
        r = ReflectModule(modpath)
        self.assertEqual(set(['mmp2']), r.module_names())

    def test_routing_module(self):
        modpath = "routing_module"
        data = [
            "class Bar(object):",
            "    def GET(*args, **kwargs): pass"
        ]
        testdata.create_module(modpath=f"{modpath}.foo", data=data)

        r = ReflectModule(modpath)
        self.assertTrue(modpath in r.module_names())
        self.assertEqual(2, len(r.module_names()))

    def test_routing_package(self):
        modpath = "routepack"
        data = [
            "class Default(object):",
            "    def GET(self): pass",
            "",
        ]
        f = testdata.create_package(modpath=modpath, data=data)

        r = ReflectModule(modpath)
        self.assertTrue(modpath in r.module_names())
        self.assertEqual(1, len(r.module_names()))

    def test_module_names(self):
        modpath = "get_controllers"
        d = {
            modpath: [
                "class Default(object):",
                "    def GET(*args, **kwargs): pass",
                ""
            ],
            f"{modpath}.default": [
                "class Default(object):",
                "    def GET(*args, **kwargs): pass",
                ""
            ],
            f"{modpath}.foo": [
                "class Default(object):",
                "    def GET(*args, **kwargs): pass",
                "",
                "class Bar(object):",
                "    def GET(*args, **kwargs): pass",
                "    def POST(*args, **kwargs): pass",
                ""
            ],
            f"{modpath}.foo.baz": [
                "class Default(object):",
                "    def GET(*args, **kwargs): pass",
                "",
                "class Che(object):",
                "    def GET(*args, **kwargs): pass",
                ""
            ],
            f"{modpath}.foo.boom": [
                "class Bang(object):",
                "    def GET(*args, **kwargs): pass",
                ""
            ],
        }
        r = testdata.create_modules(d)
        s = set(d.keys())


        r = ReflectModule(modpath)
        mods = r.module_names()
        self.assertEqual(s, mods)

        # just making sure it always returns the same list
        mods = r.module_names()
        self.assertEqual(s, mods)

    def test_find_module_names_directory(self):
        modpath = "reflectmodulesdir"
        path = testdata.create_modules({
            "foo": [
                "class Foo(object): pass"
            ],
            "foo.bar": [
                "class Bar1(object): pass",
                "class Bar2(object): pass"
            ],
            "che": [
                "class Che(object): pass"
            ],
        }, modpath)

        s = set([
            modpath,
            f"{modpath}.foo",
            f"{modpath}.foo.bar",
            f"{modpath}.che",
        ])
        self.assertEqual(s, ReflectModule.find_module_names(path))

    def test_path_is_package(self):
        m = testdata.create_package(data="class Foo(object): pass")

        self.assertEqual(set([m]), ReflectModule.find_module_names(m.directory))

        # we don't return the path because it isn't importable by name from the
        # path we passed in (itself), as of 7-4-2019 I think this is the correct
        # behavior
        dirpath = Dirpath(m.directory, m)
        self.assertEqual(set(), ReflectModule.find_module_names(dirpath))

    def test_find_module_import_path(self):
        modpath = testdata.create_module(modpath="foo.bar.che")
        rm = ReflectModule(modpath)
        import_path = rm.find_module_import_path()
        self.assertTrue(import_path in modpath.path)
        for modpart in ["foo", "bar", "che"]:
            self.assertFalse(modpart in import_path)

    def test_get_find_data(self):
        modpath = "gdrm"
        dp = testdata.create_modules({
            f"{modpath}.foo": "",
            f"{modpath}.foo.bar": "",
            f"{modpath}.che.baz.boo": "",
        })

        dp.child_file(modpath, "data", "one.txt").write_text("1")
        dp.child_file(modpath, "foo", "bar", "data", "two.txt").write_text("2")
        dp.child_file(modpath, "che", "data", "three.txt").write_text("3")

        rm = ReflectModule(modpath)

        data = rm.get_data("data/one.txt")
        self.assertEqual(b"1", data)

        data = rm.get_data("foo/bar/data/two.txt")
        self.assertEqual(b"2", data)

        data = rm.get_data("che/data/three.txt")
        self.assertEqual(b"3", data)

        with self.assertRaises(FileNotFoundError):
            rm.get_data("four.txt")

        data = rm.find_data("one.txt")
        self.assertEqual(b"1", data)

        data = rm.find_data("two.txt")
        self.assertEqual(b"2", data)

        data = rm.find_data("data/three.txt")
        self.assertEqual(b"3", data)

    def test_data_dirs(self):
        modpath = "fddrm"
        dp = testdata.create_modules({
            f"{modpath}.foo": "",
            f"{modpath}.foo.bar.__init__": "",
            f"{modpath}.che.baz.boo": "",
        })

        dp.child_file(modpath, "data", "one.txt").write_text("1")
        dp.child_file(modpath, "foo", "bar", "data", "two.txt").write_text("2")
        dp.child_file(
            modpath,
            "che",
            "other_name",
            "one_dir",
            "three.txt"
        ).write_text("3")
        dp.child_file(
            modpath,
            "che",
            "other_name",
            "two_dir",
            "four.txt"
        ).write_text("4")

        rm = ReflectModule(modpath)

        nr = set([
            f"{modpath}/data",
            f"{modpath}/che/other_name",
            f"{modpath}/foo/bar/data"
        ])
        for p in rm.data_dirs():
            self.assertTrue(p.relative_to(dp) in nr)

    def test_get_docblock_1(self):
        m = self.create_module("""
            # -*- coding: utf-8 -*-
            # module docblock
            # line 2

            var = 1
        """)
        rm = ReflectModule(m)
        doc = rm.get_docblock()
        self.assertTrue("module docblock" in doc)

        m = self.create_module("""
            '''module docblock'''

            var = 1
        """)
        rm = ReflectModule(m)
        doc = rm.get_docblock()
        self.assertEqual("module docblock", doc)

    def test_get_docblock_2(self):
        """Moved here from captain.reflection_test since captain Commands
        aren't using module comments anymore"""
        m = self.create_module("""
            #!/usr/bin/env python
            # -*- coding: utf-8 -*-
            '''the description on module doc'''
        """)
        rm = ReflectModule(m)
        doc = rm.get_docblock()
        self.assertEqual("the description on module doc", rm.get_docblock())

        m = self.create_module("""
            #!/usr/bin/env python
            # -*- coding: utf-8 -*-
            # the description on module comment
            # and the second line
        """)
        rm = ReflectModule(m)
        self.assertEqual(
            "the description on module comment\nand the second line",
            rm.get_docblock()
        )

    def test_get_module_module_package(self):
        """Makes sure ReflectModule can get the module with a relative
        module name (eg ".foo.bar") and an absolute module name (eg "foo.bar")
        """
        modpath = self.create_module({
            "foo": {
                "bar": ""
            }
        })

        rm = ReflectModule("foo", modpath)
        m = rm.get_module()
        self.assertTrue(m.__name__.endswith(".foo"))

        rm = ReflectModule("foo.bar", modpath)
        m = rm.get_module()
        self.assertTrue(m.__name__.endswith(".foo.bar"))

        rm = ReflectModule(".foo.bar", modpath)
        m = rm.get_module()
        self.assertTrue(m.__name__.endswith(".foo.bar"))


class ReflectPathTest(TestCase):
    def test_find_modules_1(self):
        modpath = self.get_module_name(count=2, name="controllers")
        basedir = self.create_modules({
            modpath: {
                "bar": "",
                "che": {
                    "boo": "",
                },
            },
        })

        p = ReflectPath(basedir)

        modpaths = set([
            modpath,
            f"{modpath}.che",
            f"{modpath}.che.boo",
            f"{modpath}.bar",
        ])

        modpaths2 = set()
        for m in p.find_modules("controllers"):
            modpaths2.add(m.__name__)
        self.assertEqual(modpaths, modpaths2)

    def test_find_modules_2(self):
        """test non-python module subpath (eg, pass in foo/ as the paths and
        then have foo/bin/MODULE/controllers.py where foo/bin is not a module
        """
        cwd = self.create_dir()
        modpath = self.get_module_name(count=2, name="controllers")

        basedir = self.create_modules(
            {
                modpath: {
                    "bar": "",
                    "che": {
                        "boo": "",
                    },
                },
            },
            tmpdir=cwd.child_dir("src")
        )

        p = ReflectPath(cwd)

        modpaths = set([
            modpath,
            f"{modpath}.che",
            f"{modpath}.che.boo",
            f"{modpath}.bar",
        ])

        modpaths2 = set()
        for m in p.find_modules("controllers"):
            modpaths2.add(m.__name__)
        self.assertEqual(modpaths, modpaths2)

    def test_find_modules_file(self):
        modpath = "reflectmodulesfile"
        modpaths = set([modpath])

        path = testdata.create_module(
            [
                "class Foo(object): pass"
            ],
            modpath
        )
        p = ReflectPath(path.path)
        modpaths2 = set()
        for m in p.find_modules(modpath):
            modpaths2.add(m.__name__)
        self.assertEqual(modpaths, modpaths2)

        path = testdata.create_module(
            [
                "class Foo(object): pass"
            ],
            "not" + modpath
        )
        p = ReflectPath(path.path)
        self.assertEqual(0, len(list(p.find_modules(modpath))))

    def test_get_module_python_file(self):
        mp = self.create_module([
            "foo = 1",
        ])

        rp = ReflectPath(mp.path)

        m = rp.get_module()
        self.assertEqual(mp, m.__name__)
        self.assertEqual(1, m.foo)

    def test_get_module_package(self):
        mp = self.create_package([
            "foo = 1",
        ])

        rp = ReflectPath(mp.parent)

        m = rp.get_module()
        self.assertEqual(mp, m.__name__)
        self.assertEqual(1, m.foo)

    def test_get_module_subpackage(self):
        mp = self.create_package(
            [
                "foo = 1",
            ],
            modpath=self.get_module_name(3)
        )

        rp = ReflectPath(mp.parent)

        m = rp.get_module()
        self.assertTrue(mp.endswith(m.__name__))
        self.assertEqual(1, m.foo)

