# -*- coding: utf-8 -*-
import sys

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

