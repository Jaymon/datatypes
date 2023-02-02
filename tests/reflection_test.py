# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys

from datatypes.compat import *
from datatypes.reflection import (
    Extend,
    ReflectModule,
    ReflectClass,
    ReflectMethod,
    ReflectDecorator,
)
from datatypes.path import Dirpath
from . import TestCase, testdata


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
    def test_docblock(self):
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

    def test_decorators_inherit_1(self):
        """make sure that a child class that hasn't defined a METHOD inherits the
        METHOD method from its parent with decorators in tact"""
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
        """you have a parent class with POST method, the child also has a POST method,
        what do you do? What. Do. You. Do?"""
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
        self.assertEqual(sys.modules[__name__], rc.module())


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
        m = rm.module()
        self.assertTrue(getattr(m, "Foo"))

    def test_mixed_modules_packages(self):
        """make sure a package with modules and other packages will resolve correctly"""
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
        self.assertEqual(set(['mmp.foo', 'mmp', 'mmp.foo.bar', 'mmp.che']), r.module_names())

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

    def test_find_module_names(self):
        modpath = "reflectmodules"
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

        # we don't return the path because it isn't importable by name from the path we
        # passed in (itself), as of 7-4-2019 I think this is the correct behavior
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

