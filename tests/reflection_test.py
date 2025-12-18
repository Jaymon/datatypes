# -*- coding: utf-8 -*-
import io
import sys
import functools
from typing import Any, Literal, Annotated, TypedDict, Type
import runpy
import ast

from datatypes.compat import *
from datatypes.reflection import (
    ReflectName,
    ReflectModule,
    ReflectClass,
    ReflectPath,
    ReflectType,
    ReflectCallable,
    ReflectDocblock,
    ClasspathFinder,
    ClassFinder,
    ClassKeyFinder,
)
from datatypes.reflection.inspect import ReflectAST
from datatypes.path import Dirpath
from . import TestCase, testdata


class ClasspathFinderTest(TestCase):
    def test_add_class(self):
        prefix = self.get_module_name(2)
        modpath = self.create_module(
            [
                "class Foo(object): pass",
                "class CheBoo(Foo): pass",
            ],
            modpath=prefix + ".foo_bar",
        )

        m = modpath.get_module()
        pf = ClasspathFinder([prefix])
        pf.add_class(m.Foo)
        pf.add_class(m.CheBoo)

        value = pf.get(["foo-bar", "che-boo"])
        self.assertEqual("CheBoo", value["class"].__name__)

        value = pf.get(["foo-bar", "foo"])
        self.assertEqual("Foo", value["class"].__name__)

    def test_add_empty_key(self):
        class CPF(ClasspathFinder):
            def _get_node_class_info(self, key, **kwargs):
                key, value = super()._get_node_class_info(key, **kwargs)
                if key == "Default":
                    key = None
                return key, value

        prefix = self.create_module("class Default(object): pass")
        m = prefix.get_module()
        pf = CPF([prefix])
        pf.add_class(m.Default)
        self.assertEqual(m.Default, pf[[]]["class"])

    def test_get_prefix_modules(self):
        prefix = self.create_module({
            "foo": "",
            "bar": {
                "che": "",
            }
        })

        ms = ClasspathFinder.get_prefix_modules([prefix])
        self.assertEqual(1, len(ms))
        self.assertEqual(4, len(ms[prefix]))

    def test_get_path_modules_file(self):
        path = self.create_file(ext="py")
        ms = ClasspathFinder.get_path_modules([path])
        self.assertEqual(1, len(ms))
        self.assertEqual(1, len(ms[""]))

    def test_get_path_modules_dir(self):
        path = self.create_modules({
            "cheboo": {
                "foobar": {
                    "foo": "",
                    "bar": {
                        "che": "",
                    }
                },
                "ignored": "",
            }
        })

        ms = ClasspathFinder.get_path_modules([path], "foobar")
        self.assertEqual(1, len(ms))
        self.assertEqual(4, len(ms["cheboo.foobar"]))

    def test_overwrite(self):
        """Makes sure destination nodes take precedence over waypoint nodes"""
        prefix = self.create_module(
            {
                "": [
                    "class Foo(object): pass",
                ],
                "foo": {
                    "": [
                        "class Bar(object): pass",
                    ],
                    "baz": [
                        "class Che(object): pass",
                    ],
                },
            },
        )
        pf = ClasspathFinder(prefixes=[prefix])

        # first we add a waypoint node
        pf.add_class(prefix.get_module("foo").Bar)
        self.assertTrue("module" in pf["foo"])

        # now lets add the destination node and make sure it overwrites the
        # waypoint node
        pf.add_class(prefix.get_module().Foo)
        self.assertEqual(pf["foo"]["class"].__name__, "Foo")

        # make sure adding another waypoint doesn't overwrite our destination
        pf.add_class(prefix.get_module("foo.baz").Che)
        self.assertEqual(pf["foo"]["class"].__name__, "Foo")

    def test_get_class_items(self):
        """Make sure we can iterate through all destination nodes in the tree
        """
        prefix = self.create_module(
            {
                "": [
                    "class Foo(object): pass",
                ],
                "foo": {
                    "": [
                        "class Bar(object): pass",
                    ],
                    "baz": [
                        "class Che(object): pass",
                    ],
                },
            },
        )

        pf_classes = set()
        pf = ClasspathFinder(prefixes=[prefix])
        for klass in prefix.get_classes():
            pf.add_class(klass)
            pf_classes.add(klass.__name__)

        node_classes = set()
        for keys, value in pf.get_class_items():
            node_classes.add(value["class"].__name__)

        self.assertEqual(pf_classes, node_classes)

    def test_runpath_classes(self):
        """Test a class that was loaded using something like `runpy.run_path`
        """
        modpath = self.create_module("""
            class Foo(object):
                class Bar(object):
                    class Che(object):
                        pass
        """)

        m = runpy.run_path(modpath.path)
        pf = ClasspathFinder()
        pf.add_class(m["Foo"].Bar.Che)

        che_value = pf.get_node("Foo").get_node("Bar")["Che"]
        self.assertEqual(3, len(che_value["class_keys"]))
        self.assertEqual(0, len(che_value["module_keys"]))

    def test_inaccessible_class(self):
        """Make sure a class with a qualname containing parts like <locals>
        fails"""
        def foo_factory():
            class Foo(object):
                pass

            return Foo

        pf = ClasspathFinder()

        with self.assertRaises(ValueError):
            pf.add_class(foo_factory())


class ClassFinderTest(TestCase):
    """
    .. note:: This is an incredibly difficult class to test because it is a vital
    class to testdata, so if it starts failing then you can't even get to the
    test because testdata will raise an error as it starts up
    """
    def test_add_class(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class GC11(C1): pass
            class GC12(C1): pass
            class GC21(C2): pass
            class GGC221(GC21): pass
        """)

        cf = ClassFinder()
        for c in classes.values():
            cf.add_class(c)
        self.assertTrue(len(classes) + 1, len(list(cf.nodes())))

    def test_get_abs_class_1(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class GC11(C1): pass
            class GC12(C1): pass
            class GC21(C2): pass
            class GGC221(GC21): pass
        """)

        cf = ClassFinder()
        cf.add_classes(classes.values())

        ac = cf.get_abs_class(classes["C2"])
        self.assertEqual(classes["GGC221"], ac)

        with self.assertRaises(ValueError):
            cf.get_abs_class(classes["P"])

        ac = cf.get_abs_class(classes["GGC221"])
        self.assertEqual(classes["GGC221"], ac)

    def test_get_abs_classes(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class GC11(C1): pass
            class GC12(C1): pass
            class GC21(C2): pass
            class GGC221(GC21): pass
        """)

        cf = ClassFinder()
        cf.add_classes(classes.values())

        acs = list(cf.get_abs_classes(classes["P"]))
        self.assertEqual(3, len(acs))
        for k in ["GC11", "GC12", "GGC221"]:
            self.assertTrue(classes[k] in acs)

        acs = list(cf.get_abs_classes(classes["GGC221"]))
        self.assertEqual(1, len(acs))
        self.assertTrue(classes["GGC221"] in acs)

    def test_delete_class(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
        """)

        cf = ClassFinder()
        cf.add_classes(classes.values())

        cf.delete_class(classes["C1"])

        with self.assertRaises(KeyError):
            cf.delete_class(classes["C1"])

        with self.assertRaises(TypeError):
            cf.delete_class(classes["P"])

    def test_delete_mro(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class GGP2(object): pass
        """)

        cf = ClassFinder()
        cf.add_classes(classes.values())
        self.assertEqual(2, len(cf.find_class_node(object)))

        cf.delete_mro(classes["P"])
        self.assertEqual(1, len(cf.find_class_node(object)))

        cf = ClassFinder()
        classes.pop("GGP2")
        cf.add_classes(classes.values())
        self.assertEqual(2, len(cf.find_class_node(classes["P"])))

        cf.delete_mro(classes["C2"])
        self.assertEqual(1, len(cf.find_class_node(classes["P"])))

    def test_get_mro_classes(self):
        classes = self.create_module_classes("""
            class GGP(object): pass
            class GP(GGP): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class GGP2(object): pass
        """)

        cf = ClassFinder()
        cf.add_classes(classes.values())

        subclasses = []
        for count, c in enumerate(cf.get_mro_classes(), 1):
            for sc in subclasses:
                self.assertFalse(issubclass(c, sc))
        self.assertEqual(7, count)

    def test_edges_1(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Base): pass
        class Che(Foo): pass

        cf = ClassFinder()
        cf.add_classes([Che, Foo, Base, Bar])

        r = set([Bar, Che])
        for count, c in enumerate(cf.get_abs_classes(), 1):
            self.assertTrue(c in r)
        self.assertEqual(2, count)

    def test_edges_2(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Base): pass
        class Che(Foo): pass
        class Baz(Foo, Bar): pass

        cf = ClassFinder()
        cf.add_classes([Che, Foo, Base, Bar, Baz])

        r = set([Baz, Che])
        for count, c in enumerate(cf.get_abs_classes(), 1):
            self.assertTrue(c in r)
        self.assertEqual(2, count)

    def test_edges_3(self):
        class Base1(object): pass
        class Base2(Base1): pass
        class Base3(Base2): pass
        class Foo(Base2): pass
        class Bar(Base3): pass
        class Che(Base3): pass

        cf = ClassFinder()
        cf.add_classes([Base2, Base3, Foo, Bar, Che])

        r = set([Che, Bar, Foo])
        for count, c in enumerate(cf.get_abs_classes(), 1):
            self.assertTrue(c in r)
        self.assertEqual(3, count)

    def test_edges_4(self):
        class Foo(object): pass
        class Bar(Foo): pass

        cf = ClassFinder()
        cf.add_classes([Bar])
        self.assertEqual([Bar], list(cf.get_abs_classes()))

    def test_order(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        order = [Che, Bar, Foo, Base, object]

        cf = ClassFinder()
        cf.add_classes([Base, Foo, Bar, Che])
        self.assertEqual(order, list(cf.get_mro_classes()))

        cf = ClassFinder()
        cf.add_classes([Che, Bar, Foo, Base])
        self.assertEqual(order, list(cf.get_mro_classes()))

    def test_getmro(self):
        class Base(object): pass
        class Foo(Base): pass
        class Bar(Foo): pass
        class Che(Bar): pass

        cf = ClassFinder()
        cf.add_classes([Base, Foo, Bar, Che])
        cf.set_cutoff_class(Base)

        orders = []
        for c in cf.getmro(Bar):
            orders.append(c)
        self.assertEqual([Bar, Foo], orders)


class ClassKeyFinderTest(TestCase):
    def test_find_class(self):
        classes = self.create_module_classes("""
            class GP(object): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
        """)
        cf = ClassKeyFinder()
        cf.add_classes(classes.values())

        p = cf.find_class("p_class")
        c1 = cf.find_class("c1_class")
        c2 = cf.find_class("c2_class")
        self.assertTrue(issubclass(c1, p))
        self.assertTrue(issubclass(c2, p))

    def test_get_abs_classes(self):
        classes = self.create_module_classes("""
            class GP(object): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
        """)
        cf = ClassKeyFinder()
        cf.add_classes(classes.values())
        for klass in cf.get_abs_classes():
            self.assertTrue(isinstance(klass, Type))


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
            if rm.name.endswith(".foo"):
                pass

            elif rm.name.endswith(".foo.bar"):
                pass

            else:
                raise AssertionError(rm.name)


class ReflectTypeTest(TestCase):
    def test_reflect_cast_types_1(self):
        rt = ReflectType(str)
        rts = list(rt.reflect_cast_types())
        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_str())

        rt = ReflectType(str|list[int]|float|None)
        rts = list(rt.reflect_cast_types())
        self.assertEqual(3, len(rts))
        self.assertTrue(rts[1].is_list())

        rt = ReflectType(tuple[int, ...])

        rts = list(rt.reflect_cast_types())
        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_tuple())

        rts = list(rt.reflect_cast_types(depth=-1))
        self.assertEqual(2, len(rts))
        self.assertTrue(rts[0].is_tuple())
        self.assertTrue(rts[1].is_int())

        rt = ReflectType(list[int|float])
        rts = tuple(rt.reflect_cast_types(depth=-1))
        self.assertEqual(3, len(rts))
        self.assertTrue(rts[1].is_int())
        self.assertTrue(rts[2].is_float())

    def test_get_origin_type(self):
        rt = ReflectType(str)
        self.assertEqual(str, rt.get_origin_type())

        rt = ReflectType(list[int])
        self.assertEqual(list, rt.get_origin_type())

    def test_is_methods(self):
        rt = ReflectType(set)
        self.assertTrue(rt.is_setish())
        self.assertFalse(rt.is_dictish())
        self.assertFalse(rt.is_listish())
        self.assertFalse(rt.is_stringish())

        rt = ReflectType(dict[str, int])
        self.assertTrue(rt.is_dictish())
        self.assertFalse(rt.is_listish())
        self.assertFalse(rt.is_stringish())
        self.assertFalse(rt.is_setish())

        rt = ReflectType(str)
        self.assertFalse(rt.is_dictish())
        self.assertTrue(rt.is_stringish())
        self.assertFalse(rt.is_listish())
        self.assertFalse(rt.is_setish())

        rt = ReflectType(list[int])
        self.assertFalse(rt.is_dictish())
        self.assertTrue(rt.is_listish())
        self.assertFalse(rt.is_stringish())
        self.assertFalse(rt.is_setish())

    def test_is_numeric_methods(self):
        rt = ReflectType(int)
        self.assertFalse(rt.is_bool())
        self.assertFalse(rt.is_floatish())
        self.assertTrue(rt.is_int())
        self.assertTrue(rt.is_numberish())

        rt = ReflectType(float)
        self.assertFalse(rt.is_bool())
        self.assertTrue(rt.is_floatish())
        self.assertFalse(rt.is_int())
        self.assertTrue(rt.is_numberish())

        rt = ReflectType(bool)
        self.assertTrue(rt.is_bool())
        self.assertFalse(rt.is_floatish())
        self.assertFalse(rt.is_int())
        self.assertFalse(rt.is_numberish())

    def test_any_type(self):
        rt = ReflectType(list[Any])
        rts = list(rt.reflect_types(depth=1))

        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_list())
        self.assertEqual([Any], list(rt.get_arg_types()))

        rt = ReflectType(Any)
        self.assertEqual(Any, rt.get_origin_type())
        self.assertTrue(rt.is_any())
        self.assertTrue(isinstance(dict, rt))
        self.assertTrue(issubclass(int, rt))

        self.assertFalse(rt.is_numberish())
        self.assertFalse(rt.is_listish())
        self.assertFalse(rt.is_dictish())
        self.assertFalse(rt.is_stringish())
        self.assertFalse(rt.is_none())

    def test_none_type(self):
        rt = ReflectType(None)
        self.assertTrue(rt.is_none())
        self.assertTrue(isinstance(None, rt))
        self.assertTrue(issubclass(None, rt))

        self.assertFalse(rt.is_numberish())
        self.assertFalse(rt.is_listish())
        self.assertFalse(rt.is_dictish())
        self.assertFalse(rt.is_stringish())
        self.assertFalse(rt.is_any())

    def test_str_type(self):
        rt = ReflectType(str)
        self.assertTrue(rt.is_str())

    def test_get_key_types(self):
        rt = ReflectType(dict[str, int])
        types = tuple(rt.get_key_types())
        self.assertEqual(1, len(types))
        self.assertEqual(str, types[0])

        rt = ReflectType(dict[str|int, list])
        types = tuple(rt.get_key_types())
        self.assertEqual(2, len(types))
        self.assertEqual(str, types[0])
        self.assertEqual(int, types[1])

        rt = ReflectType(list)
        with self.assertRaises(ValueError):
            list(rt.get_key_types())

    def test_get_value_types_simple(self):
        rt = ReflectType(dict[str, int])
        types = tuple(rt.get_value_types())
        self.assertEqual(1, len(types))
        self.assertEqual(int, types[0])

        rt = ReflectType(dict[str, str|int])
        types = tuple(rt.get_value_types())
        self.assertEqual(2, len(types))
        self.assertEqual(str, types[0])
        self.assertEqual(int, types[1])

        rt = ReflectType(list[int])
        types = tuple(rt.get_value_types())
        self.assertEqual(1, len(types))
        self.assertEqual(int, types[0])

    def test_reflect_value_types_1(self):
        rt = ReflectType(dict[str, int])
        rts = list(rt.reflect_value_types())
        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_type(int))

    def test_reflect_value_types_2(self):
        rt = ReflectType(list[dict[str, int]|tuple[float, float]])
        rts = list(rt.reflect_value_types())
        self.assertEqual(2, len(rts))

        rts0 = list(rts[0].reflect_value_types())
        self.assertEqual(1, len(rts0))
        self.assertTrue(rts0[0].is_type(int))

        rts1 = list(rts[1].reflect_value_types())
        self.assertEqual(2, len(rts1))
        self.assertTrue(rts1[0].is_type(float))
        self.assertTrue(rts1[1].is_type(float))

    def test_reflect_value_types_sub(self):
        rt = ReflectType(dict[str, dict[str, int]])
        rts = tuple(rt.reflect_value_types())
        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_dictish())

    def test_get_args_1(self):
        rt = ReflectType(dict|None)
        ts = list(rt.get_args())
        self.assertEqual(2, len(ts))

        rt = ReflectType(None)
        ts = list(rt.get_args())
        self.assertEqual(0, len(ts))

        rt = ReflectType(tuple[list, dict, int, str])
        ts = list(rt.get_args())
        self.assertEqual(4, len(ts))

    def test_reflect_arg_types_depth(self):
        """Make sure depth works as expected"""
        rt = ReflectType(dict[str, int|float]|list[dict[str, str|bytes]])
        rts = list(rt.reflect_arg_types(depth=-1))
        self.assertEqual(9, len(rts))

        rts = list(rt.reflect_arg_types(depth=2))
        self.assertEqual(5, len(rts))
        self.assertTrue(rts[0].is_dictish())
        self.assertTrue(rts[1].is_listish())
        self.assertTrue(rts[2].is_str())
        self.assertTrue(rts[3].is_int())
        self.assertTrue(rts[3].is_floatish())
        self.assertTrue(rts[4].is_dictish())

        rts = list(rt.reflect_arg_types(depth=1))
        self.assertEqual(2, len(rts))
        self.assertTrue(rts[0].is_dictish())
        self.assertTrue(rts[1].is_listish())

    def test_union_type(self):
        rt = ReflectType(bool|int)
        self.assertTrue(rt.is_bool())
        self.assertTrue(rt.is_int())

        rt = ReflectType(Any|None)
        self.assertTrue(rt.is_union())
        self.assertTrue(rt.is_any())
        self.assertTrue(rt.is_none())

        rt = ReflectType(dict|None)
        self.assertTrue(rt.is_union())
        self.assertTrue(rt.is_dictish())
        self.assertTrue(rt.is_none())

    def test_reflect_origin_types(self):
        rt = ReflectType(dict[str, list[int]])
        ots = list(rt.reflect_origin_types())
        self.assertEqual(1, len(ots))
        self.assertTrue(ots[0].is_dictish())

        rt = ReflectType(dict[str, int]|list[str]|tuple[str, str])
        ots = list(rt.reflect_origin_types())
        self.assertEqual(3, len(ots))
        self.assertTrue(ots[0].is_dictish())
        self.assertTrue(ots[1].is_listish())
        self.assertTrue(ots[2].is_tuple())

        rt = ReflectType(dict[str, int])
        ots = list(rt.reflect_origin_types())
        self.assertEqual(1, len(ots))
        self.assertTrue(ots[0].is_dictish())

        rt = ReflectType(dict)
        ots = list(rt.reflect_origin_types())
        self.assertEqual(1, len(ots))
        self.assertTrue(ots[0].is_dictish())

    def test_is_subclass(self):
        rt = ReflectType(...)
        self.assertTrue(rt.is_subclass(...))

    def test_is_ellipsis(self):
        rt = ReflectType(...)
        self.assertTrue(rt.is_ellipsis())

    def test_reflect_types_1(self):
        rt = ReflectType(dict[str, int])
        rts = list(rt.reflect_types())
        self.assertEqual(1, len(rts))
        self.assertTrue(rts[0].is_dictish())

        rt = ReflectType(dict[str, int])
        rts = list(rt.reflect_types(depth=-1))
        self.assertEqual(3, len(rts)) # dict[str, int], str, int

        rt = ReflectType(dict[str, int]|list[str])
        rts = list(rt.reflect_types())
        self.assertEqual(2, len(rts)) # dict[...], list[...]

        rt = ReflectType(dict[str, int]|list[str])
        rts = list(rt.reflect_types(depth=-1))
        self.assertEqual(5, len(rts)) # dict[...], list[...]

    def test_reflect_types_annotated_1(self):
        rt = ReflectType(Annotated[int|float|str, None])
        rts = list(rt.reflect_arg_types())
        self.assertEqual(3, len(rts))
        self.assertTrue(rts[0].is_int())

    def test_reflect_types_annotated_2(self):
        rt = ReflectType(Annotated[int|str, None])
        self.assertTrue(rt.is_union())
        self.assertTrue(rt.is_annotated())

        rts = list(rt.reflect_types(depth=-1))
        self.assertEqual(3, len(rts))
        self.assertTrue(rts[0].is_annotated())
        self.assertTrue(rts[1].is_int())
        self.assertTrue(rts[2].is_str())

    def test_reflect_types_2(self):
        rt = ReflectType(
            Annotated[str, "foo"]|Annotated[int|None, "bar"]
        )
        rts = list(rt.reflect_types(depth=1))
        self.assertEqual(2, len(rts))
        self.assertEqual("foo", list(rts[0].get_metadata())[0])
        self.assertEqual("bar", list(rts[1].get_metadata())[0])

    def test_literal(self):
        t = Literal["a", "b", "c"]
        rt = ReflectType(t)
        self.assertTrue(rt.is_literal())
        self.assertEqual(["a", "b", "c"], list(rt.get_args()))

    def test_annotated(self):
        rt = ReflectType(Annotated[str, {"foo": 1, "bar": 2}])
        self.assertTrue(rt.is_annotated())
        self.assertTrue(rt.is_str())
        self.assertTrue(1, list(rt.get_metadata())[0]["foo"])

    def test_cast_union(self):
        rt = ReflectType(int | None)

        v = rt.cast("100")
        self.assertEqual(100, v)
        self.assertTrue(isinstance(v, int))

        with self.assertRaises(ValueError):
            rt.cast("dalfdfjl")

    def test_cast_annotated(self):
        rt = ReflectType(Annotated[int, None])
        self.assertEqual(100, rt.cast("100"))

        rt = ReflectType(Annotated[int|str, None])
        self.assertEqual("foo", rt.cast("foo"))

    def test_cast_listish(self):
        rt = ReflectType(Annotated[list[int], None])
        self.assertEqual([1, 2, 3], rt.cast(["1", "2", "3"]))

        rt = ReflectType(list[int])
        self.assertEqual([1, 2, 3], rt.cast(["1", "2", "3"]))

    def test_cast_none(self):
        rt = ReflectType(int | None)
        self.assertEqual(None, rt.cast(None))

    def test_cast_annotated_list(self):
        rt = ReflectType(Annotated[list[int], None])
        self.assertEqual([12, 34], rt.cast(["12", "34"]))

    def test_cast_any(self):
        rt = ReflectType(Any)
        v = "foo"
        self.assertEqual(v, rt.cast(v))

    def test_cast_literal(self):
        rt = ReflectType(Literal["one", "two"])
        self.assertEqual("one", rt.cast("one"))
        with self.assertRaises(ValueError):
            r = rt.cast("three")

        rt = ReflectType(Literal[1])
        self.assertEqual(1, rt.cast("1"))

    def test_cast_bytesio(self):
        rt = ReflectType(io.BytesIO)
        fp = io.BytesIO(b"1234567890")
        fp2 = rt.cast(fp)
        self.assertTrue(fp is fp2)

    def test_cast_annotated_function(self):
        def parse(v):
            return int(v)

        rt = ReflectType(Annotated[parse, {}])
        v = rt.cast("100")
        self.assertEqual(100, v)

    def test_typed_dict(self):
        class TD(TypedDict):
            foo: str
            bar: int

        rt = ReflectType(TD)

        self.assertTrue(rt.is_type(TypedDict))
        self.assertTrue(rt.is_type(TD))
        self.assertTrue(rt.is_dictish())
        self.assertFalse(rt.is_none())

    def test__is_subclass_instance_tuple(self):
        """I had a typo in the internal get_type method that puts a tuple
        together inside ._is_subclass that none of the other tests caught,
        this makes sure that bug is fixed and it doesn't crop up again"""
        rt = ReflectType(str)
        self.assertTrue(rt._is_subclass(str, ("foo", "bar")))


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

    def test_get_docblock_1(self):
        foo_class = self.create_module_class([
            "class Foo(object):",
            "    '''class docblock'''",
            "    def GET(*args, **kwargs):",
            "        '''method docblock'''",
            "        pass",
        ])

        rc = ReflectCallable(foo_class.GET)
        desc = rc.get_docblock()
        self.assertEqual("method docblock", desc)

    def test_get_docblock_bad_decorator(self):
        foo_class = self.create_module_class([
            "def bad_dec(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "class Foo(object):",
            "    '''class docblock'''",
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

        rc = ReflectCallable(foo_class.GET, target_class=foo_class)
        desc = rc.get_docblock()
        self.assertEqual("method docblock", desc)

    def test_docblock_runpath(self):
        """What if the callable was loaded with runpath and doesn't have a
        docblock so the ast is checked. Instead of failing, the method should
        just return an empty string
        """
        modpath = self.create_module("""
            class Foo(object):
                def foo(self):
                    pass
        """)

        m = runpy.run_path(modpath.path)
        rc = ReflectCallable(m["Foo"].foo)
        desc = rc.get_docblock()
        self.assertEqual("", desc)

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

        self.assertEqual(5, len(info["names"]))
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

        self.assertEqual(5, len(info["names"]))
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
        self.assertEqual(["foo", "bar", "che", "kwargs"], sig["names"])
        self.assertEqual(1, sig["defaults"]["bar"])
        self.assertEqual("kwargs", sig["keywords_name"])
        self.assertEqual("", sig["positionals_name"])

    def test_get_signature_info_pos_key(self):
        def foo(foo, bar=1, *args, che=3, **kwargs): pass

        sig = ReflectCallable(foo).get_signature_info()
        self.assertEqual("args", sig["names"][sig["indexes"]["args"]])
        self.assertEqual("kwargs", sig["names"][sig["indexes"]["kwargs"]])

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

    def test_reflect_arguments_1(self):
        def foo(bar, che): pass
        rc = ReflectCallable(foo)

        ras = iter(rc.reflect_arguments(che=1))

        ra = next(ras)
        self.assertEqual("bar", ra.name)
        self.assertFalse(ra.is_bound())
        self.assertTrue(ra.is_unbound())
        self.assertFalse(ra.has_value())
        self.assertFalse(ra.is_unbound_positionals())
        self.assertFalse(ra.is_unbound_keywords())

        ra = next(ras)
        self.assertEqual("che", ra.name)
        self.assertTrue(ra.is_bound())
        self.assertTrue(ra.has_value())
        self.assertEqual(1, ra.value)

        ras = iter(rc.reflect_arguments(1, 2, 3, 4))
        next(ras) # bar
        next(ras) # che
        ra = next(ras) # unbound
        self.assertTrue(ra.is_unbound_positionals())
        self.assertTrue(ra.is_unbound())
        self.assertTrue(ra.is_catchall())
        self.assertEqual([3, 4], ra.value)

    def test_reflect_arguments_2(self):
        def foo(foo, bar=2, /, che=3): pass
        sig = ReflectCallable(foo)

        bound = {
            "foo": 1,
            "bar": 2,
            "che": 3,
        }
        for ra in sig.reflect_arguments(1, 2, 3):
            self.assertEqual(bound[ra.name], ra.value)
            bound.pop(ra.name)
        self.assertFalse(bound)

        bound = {
            "foo": 1,
            "che": 3,
        }
        for ra in sig.reflect_arguments(1, che=3):
            if ra.name != "bar":
                self.assertEqual(bound[ra.name], ra.value)
                bound.pop(ra.name)
        self.assertFalse(bound)

    def test_reflect_arguments_value(self):
        def foo(bar): pass
        rc = ReflectCallable(foo)

        ras = iter(rc.reflect_arguments(1, bar=2))
        ra = next(ras)
        self.assertTrue(ra.has_value())
        self.assertTrue(ra.has_positional_value())
        self.assertTrue(ra.has_keyword_value())
        self.assertTrue(ra.has_multiple_values())
        self.assertEqual(1, ra.value)
        self.assertEqual(2, ra.get_keyword_value())
        self.assertEqual(1, ra.get_value())

    def test_reflect_arguments_unbound_kwargs(self):
        def foo(): pass
        rc = ReflectCallable(foo)

        kwargs = {"bar": 1, "che": 2}
        ras = iter(rc.reflect_arguments(**kwargs))
        ra = next(ras)
        self.assertEqual(kwargs, ra.value)

    def test_reflect_arguments_unbound_param(self):
        def foo(bar, /, che): pass
        rc = ReflectCallable(foo)

#         for ra in rc.reflect_arguments(*[1], **{"boo": 2}):
#             pout.v(ra)
#         return

        ras = iter(rc.reflect_arguments(*[1], **{"boo": 2}))
        ra = next(ras) # bar
        ra = next(ras)
        self.assertEqual("che", ra.name)
        self.assertTrue(ra.is_unbound())

    def test_reflect_arguments_misbind(self):
        def foo(bar=1, che=100): pass
        rc = ReflectCallable(foo)

        for ra in rc.reflect_arguments(ignored=2):
            self.assertFalse(ra.is_bound())

    def test_get_bind_info_1(self):
        def foo(foo, bar=2, che=3, **kwargs): pass
        args = [1, 2, 3, 4]
        kwargs = {
            "foo": 10,
            "bar": 20,
            "che": 30,
            "boo": 40
        }
        rc = ReflectCallable(foo)

        info = rc.get_bind_info(*args, **kwargs)
        self.assertEqual([4], info["unbound_args"])

        info = rc.get_bind_info(**kwargs)
        self.assertEqual(kwargs, info["bound_kwargs"])

    def test_get_bind_info_missing(self):
        def foo(bar, /, che): pass
        rc = ReflectCallable(foo)

        info = rc.get_bind_info(*[1], **{"boo": 2})
        self.assertTrue("boo" in info["unbound_kwargs"])
        self.assertTrue("che" in info["missing_names"])
        self.assertTrue("bar" in info["bound_names"])

    def test_get_bind_info_misbind(self):
        class Foo(object):
            def foo(self, bar=1, che=100): pass
        rc = ReflectCallable(Foo.foo, Foo)

        info = rc.get_bind_info(ignored=2)
        self.assertTrue("bar" in info["missing_names"])
        self.assertTrue("che" in info["missing_names"])
        self.assertFalse(info["bound_args"])
        self.assertFalse(info["bound_kwargs"])

    def test_reflect_ast_decorators_function(self):
        mp = self.create_module("""
            def name(func):
                def wrapper(*args, **kwargs):
                    return func(*args, **kwargs)
                return wrapper

            def call(one=1, two=2):
                def decorator(func):
                    def wrapper(*args, **kwargs):
                        return func(*args, **kwargs)
                    return wrapper
                return decorator

            @name
            @call(1, 2)
            @call()
            def bar():
                pass
        """)
        m = mp.get_module()

        rc = ReflectCallable(m.bar)
        decs = list(rc.reflect_ast_decorators())
        self.assertEqual(3, len(decs))
        self.assertEqual("name", decs[0].name)

    def test_reflect_ast_decorators_async(self):
        modpath = testdata.create_module([
            "def a(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "b = a",
            "c = a",
            "d = a",
            "",
            "class Foo(object):",
            "    @a",
            "    async def abar(self): pass",
            "    @c",
            "    def bar(self): pass",
            "",
            "@b",
            "async def abar(): pass",
            "",
            "@d",
            "async def bar(): pass",
        ])

        m = modpath.get_module()

        rc = ReflectCallable(m.Foo.abar, m.Foo)
        decs = list(rc.reflect_ast_decorators())
        self.assertEqual(1, len(decs))
        self.assertEqual("a", decs[0].name)

        rc = ReflectCallable(m.Foo.bar, m.Foo)
        decs = list(rc.reflect_ast_decorators())
        self.assertEqual(1, len(decs))
        self.assertEqual("c", decs[0].name)

        rc = ReflectCallable(m.bar)
        decs = list(rc.reflect_ast_decorators())
        self.assertEqual(1, len(decs))
        self.assertEqual("d", decs[0].name)

        rc = ReflectCallable(m.Foo.abar, m.Foo)
        decs = list(rc.reflect_ast_decorators())
        self.assertEqual(1, len(decs))
        self.assertEqual("a", decs[0].name)

    def test_get_ast_bad_decorators(self):
        modpath = testdata.create_module([
            "def a(func):",
            "    def wrapper(*args, **kwargs):",
            "        return func(*args, **kwargs)",
            "    return wrapper",
            "",
            "b = a",
            "c = a",
            "d = a",
            "",
            "class Foo(object):",
            "    @a",
            "    async def abar(self): pass",
            "    @c",
            "    def bar(self): pass",
            "",
            "@b",
            "async def abar(): pass",
            "",
            "@d",
            "def bar(): pass",
        ])

        m = modpath.get_module()

        # methods
        # !!! this will fail if target_class isn't given because the methods
        # aren't wrapped with well-behaved decorators
        rc = ReflectCallable(m.Foo.abar, m.Foo, name="abar")
        node = rc.get_ast()
        self.assertEqual("abar", node.name)
        self.assertEqual(12, node.lineno)

        rc = ReflectCallable(m.Foo.bar, m.Foo, name="bar")
        node = rc.get_ast()
        self.assertEqual("bar", node.name)
        self.assertEqual(14, node.lineno)

        # functions
        rc = ReflectCallable(m.abar, name="abar")
        node = rc.get_ast()
        self.assertEqual("abar", node.name)
        self.assertEqual(17, node.lineno)

        rc = ReflectCallable(m.bar, name="bar")
        node = rc.get_ast()
        self.assertEqual("bar", node.name)
        self.assertEqual(20, node.lineno)

    def test_get_ast_embedded_classes(self):
        modpath = self.create_module("""
            class Foo(object):
                class Bar(object):
                    class Che(object):
                        async def bam(self):
                            pass
        """)
        m = modpath.get_module()

        rc = ReflectCallable(m.Foo.Bar.Che.bam, m.Foo.Bar.Che)
        self.assertIsNotNone(rc.get_ast())

    def test_get_ast_parent_def(self):
        foo_class = self.create_module_class("""
            class _Parent(object):
                async def bar(self):
                    che = 1

            class Foo(_Parent):
                pass

        """)

        rc = ReflectCallable(foo_class.bar, foo_class)
        n = rc.get_ast()
        self.assertTrue(n.name == "bar")

    def test_reflect_supers(self):
        foo_class = testdata.create_module_class("""
            class _GP(object):
                def foo(self):
                    return 1
                def bar(self):
                    return 2
                def che(self):
                    return 3

            class _P(_GP):
                def foo(self):
                    return 2
                def bar(self):
                    return super().bar()

            class Foo(_P):
                def foo(self):
                    return super().foo()
                def bar(self):
                    return super().bar()
                def che(self):
                    return super().che()
        """)

        rc = ReflectCallable(foo_class.che, foo_class)
        supers = list(rc.reflect_supers())
        self.assertEqual(1, len(supers))
        self.assertEqual("_GP", supers[0].get_class().__name__)

        rc = ReflectCallable(foo_class.bar, foo_class)
        supers = list(rc.reflect_supers())
        self.assertEqual(2, len(supers))
        self.assertEqual("_P", supers[0].get_class().__name__)
        self.assertEqual("_GP", supers[1].get_class().__name__)

        rc = ReflectCallable(foo_class.foo, foo_class)
        supers = list(rc.reflect_supers())
        self.assertEqual(1, len(supers))
        self.assertEqual("_P", supers[0].get_class().__name__)

    def test_reflect_ast_raises_1(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self, v):
                    if v == 1:
                        raise ValueError("value error")

                    elif v == 2:
                        raise RuntimeError("runtime error")

                    elif v == 3:
                        raise TypeError("type error")

        """)

        rc = ReflectCallable(foo_class.foo, foo_class)

        nodes = list(rc.reflect_ast_raises())
        self.assertEqual(3, len(nodes))
        self.assertEqual("ValueError", nodes[0].name)
        self.assertEqual("value error", nodes[0].get_parameters()[0][0])

    def test_reflect_ast_raises_no_exc(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self, v):
                    try:
                        raise ValueError("value error")

                    except ValueError:
                        raise

                    except KeyError as e:
                        if True:
                            raise

                    except (RuntimeError, TypeError) as e:
                        raise e

                    else:
                        raise IOError()
        """)

        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_raises())
        self.assertEqual(6, len(nodes))

    def test_reflect_ast_raises_multiple_args(self):
        foo_class = testdata.create_module_class("""
            class _FooError(Exception):
                def __init__(self, one, two):
                    super().__init__(two)

            class Foo(object):
                def foo(self, v):
                    raise _FooError(123, "four five six")

        """)

        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_raises())
        params = nodes[0].get_parameters()
        self.assertEqual(123, params[0][0])
        self.assertEqual("four five six", params[0][1])

    def test_reflect_ast_returns_1(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self):
                    return dict(foo=1, bar=2)
        """)

        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_returns())
        self.assertEqual(1, len(nodes))
        self.assertEqual("dict", nodes[0].name)

    def test_reflect_ast_returns_no_return(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self):
                    foo = 1
                    bar = "2"
        """)

        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_returns())
        self.assertEqual(0, len(nodes))

    def test_reflect_ast_returns_none(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self):
                    return None

        """)
        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_returns())
        self.assertEqual(1, len(nodes))

        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self):
                    ret = None
                    return ret

        """)
        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_returns())
        self.assertEqual(1, len(nodes))

        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self):
                    return

        """)
        rc = ReflectCallable(foo_class.foo, foo_class)
        nodes = list(rc.reflect_ast_returns())
        self.assertEqual(0, len(nodes))

    def test_reflect_return_type(self):
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def foo(self) -> dict[str, int]:
                    return dict(foo=1, bar=2)
                def bar(self):
                    return 2
                def che(self) -> None:
                    return None
        """)

        rc = ReflectCallable(foo_class.foo, foo_class)
        rt = rc.reflect_return_type()
        self.assertEqual(dict, rt.get_origin_type())

        rc = ReflectCallable(foo_class.bar, foo_class)
        rt = rc.reflect_return_type()
        self.assertEqual(None, rt)

        rc = ReflectCallable(foo_class.che, foo_class)
        rt = rc.reflect_return_type()
        self.assertEqual(None, rt.get_origin_type())

    def test_has_catchall_methods(self):
        """make sure the has_*_catchall methods work as expected to
        test if a callable has an *args or **kwargs argument"""
        foo_class = testdata.create_module_class("""
            class Foo(object):
                def has_args(self, *args):
                    pass
                def has_kwargs(self, **kwargs):
                    pass
                def has_both(self, *args, **kwarsg):
                    pass
        """)

        rc = ReflectCallable(foo_class.has_args, foo_class)
        self.assertTrue(rc.has_positionals_catchall())
        self.assertFalse(rc.has_keywords_catchall())

        rc = ReflectCallable(foo_class.has_kwargs, foo_class)
        self.assertFalse(rc.has_positionals_catchall())
        self.assertTrue(rc.has_keywords_catchall())

        rc = ReflectCallable(foo_class.has_both, foo_class)
        self.assertTrue(rc.has_positionals_catchall())
        self.assertTrue(rc.has_keywords_catchall())

    def test_get_signature_info_types(self):
        class Foo(object):
            def bar(
                self,
                one: Literal["a", "b", "c"],
                two: bool = False,
                /,
                three: int = 1,
                *,
                four: str|None,
                five: str = "d",
                six,
            ):
                pass

        rc = ReflectCallable(Foo.bar, Foo)
        siginfo = rc.get_signature_info()
        siginfo.pop("signature", None)
        self.assertFalse("six" in siginfo["annotations"])


class ReflectClassTest(TestCase):
    def test_docblock_1(self):
        foo_class = testdata.create_module_class([
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
        rc = ReflectClass(foo_class)
        self.assertTrue("\n" in rc.get_docblock())

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

    def test_get_class(self):
        r = testdata.create_module([
            "def foo():",
            "    class FooCannotBeFound(object): pass",
        ])

        with self.assertRaises(AttributeError):
            ReflectClass.get_class(f"{r}:FooCannotBeFound")
            # this would be the object once you have the module:
            #     m.foo.__code__.co_consts
            # but I can't find anyway to take a code object and turn it into
            # the actual type instance. I tried eval() and exec() but they
            # executed but I couldn't get the class after running them

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

    def test_get_parents(self):
        foo_class = self.create_module_class("""
            class _One(object):
                pass

            class _Two(_One):
                pass

            class _Three(_Two):
                pass

            class Foo(_Three):
                pass
        """)

        rc = ReflectClass(foo_class)
        parents = list(rc.get_parents())
        expected = set(["_Three", "_Two", "_One"])
        self.assertEqual(3, len(parents))
        for p in parents:
            self.assertTrue(p.__name__ in expected)

    def test_get_ast(self):
        foo_class = self.create_module_class("""
            class _One(object):
                pass

            class _Two(_One):
                pass

            class _Three(_Two):
                pass

            class Foo(_Three):
                pass
        """)

        rc = ReflectClass(foo_class)
        node = rc.get_ast()
        self.assertEqual(foo_class.__name__, node.name)
        self.assertLess(0, node.lineno)

    def test_getmro_depth(self):
        foo_class = self.create_module_class("""
            class _GGP(object):
                pass
            class _GP(_GGP):
                pass
            class _P(_GP):
                pass
            class Foo(_GP):
                pass
        """)

        rc = ReflectClass(foo_class)
        classes = list(rc.get_parents(depth=1))
        self.assertNotEqual(foo_class, classes[0])

        rc = ReflectClass(foo_class)
        classes = list(rc.getmro(depth=2))
        self.assertEqual(2, len(classes))
        self.assertEqual(foo_class, classes[0])

    def test_has_definition(self):
        foo_class = testdata.create_module_class("""
            class _P(object):
                def foo(self): pass
                def bar(self): pass

            class Foo(_P):
                def foo(self): pass
                @classmethod
                def clsfoo(cls): pass
                @staticmethod
                def stafoo(): pass
                @property
                def propfoo(self): pass
        """)

        rc = ReflectClass(foo_class)
        self.assertFalse(rc.has_definition("bar"))
        self.assertTrue(rc.has_definition("foo"))
        self.assertTrue(rc.has_definition("clsfoo"))
        self.assertTrue(rc.has_definition("propfoo"))
        self.assertTrue(rc.has_definition("stafoo"))

        pc = next(rc.reflect_parents(depth=1))
        self.assertTrue(pc.has_definition("bar"))


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
            r.get_module_names()
        )

        # make sure just a file will resolve correctly
        modpath = "mmp2"
        testdata.create_module(modpath=modpath, data=[
            "class Bar(object): pass",
        ])
        r = ReflectModule(modpath)
        self.assertEqual(set(['mmp2']), r.get_module_names())

    def test_routing_module(self):
        modpath = "routing_module"
        data = [
            "class Bar(object):",
            "    def GET(*args, **kwargs): pass"
        ]
        testdata.create_module(modpath=f"{modpath}.foo", data=data)

        r = ReflectModule(modpath)
        self.assertTrue(modpath in r.get_module_names())
        self.assertEqual(2, len(r.get_module_names()))

    def test_routing_package(self):
        modpath = "routepack"
        data = [
            "class Default(object):",
            "    def GET(self): pass",
            "",
        ]
        f = testdata.create_package(modpath=modpath, data=data)

        r = ReflectModule(modpath)
        self.assertTrue(modpath in r.get_module_names())
        self.assertEqual(1, len(r.get_module_names()))

    def test_get_module_names(self):
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
        mods = r.get_module_names()
        self.assertEqual(s, mods)

        # just making sure it always returns the same list
        mods = r.get_module_names()
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

        self.assertEqual(
            set([m]),
            ReflectModule.find_module_names(m.directory)
        )

        # we don't return the path because it isn't importable by name from the
        # path we passed in (itself), as of 7-4-2019 I think this is the
        # correct behavior
        dirpath = Dirpath(m.directory, m)
        self.assertEqual(set(), ReflectModule.find_module_names(dirpath))

    def test_is_package(self):
        m = testdata.create_package(data="class Foo(object): pass")
        rm = ReflectModule(m)
        self.assertTrue(rm.is_package())

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

    def test_get_docblock_3(self):
        m = self.create_module("""
            #!/usr/bin/env python
            # -*- coding: utf-8 -*-
            # editor: set name=value :
            # editor2: set name=value :
            # description
        """)
        rm = ReflectModule(m)
        self.assertEqual(
            "description",
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

    def test_modroot(self):
        modpath = self.create_module(count=3)
        rm = ReflectModule(modpath)
        self.assertTrue(modpath.startswith(rm.modroot))
        self.assertFalse("." in rm.modroot)


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
            "class Foo(object): pass",
            modpath
        )
        p = ReflectPath(path.path)
        modpaths2 = set()
        for m in p.find_modules(modpath):
            modpaths2.add(m.__name__)
        self.assertEqual(modpaths, modpaths2)

        path = testdata.create_module(
            "class Foo(object): pass",
            "not" + modpath
        )
        p = ReflectPath(path.path)
        self.assertEqual(0, len(list(p.find_modules(modpath))))

    def test_get_module_python_file_1(self):
        mp = self.create_module("foo = 1")
        rp = ReflectPath(mp.path)
        m = rp.get_module()
        self.assertEqual(mp, m.__name__)
        self.assertEqual(1, m.foo)

    def test_get_module_python_file_2(self):
        mp = self.create_module("foo = 1", count=3)
        rp = ReflectPath(mp.path)
        m = rp.get_module()
        self.assertEqual(mp, m.__name__)
        self.assertEqual(1, m.foo)

    def test_get_module_package(self):
        mp = self.create_package("foo = 1")
        rp = ReflectPath(mp.parent)
        m = rp.get_module()
        self.assertEqual(mp, m.__name__)
        self.assertEqual(1, m.foo)

    def test_get_module_subpackage(self):
        mp = self.create_package(
            "foo = 1",
            modpath=self.get_module_name(3)
        )
        rp = ReflectPath(mp.parent)
        m = rp.get_module()
        self.assertTrue(mp.endswith(m.__name__))
        self.assertEqual(1, m.foo)

    def test_exec_module_file(self):
        fp = self.create_file([
            "class Foo(object): pass",
            "foo = Foo()"
        ])
        rp = ReflectPath(fp)
        m1 = rp.exec_module()
        m2 = rp.exec_module()
        self.assertNotEqual(m1.foo, m2.foo)

    def test_exec_module_dir(self):
        fp = self.create_file([
            "class Foo(object): pass",
            "foo = Foo()"
        ], name="__init__.py")
        dp = fp.dirname
        rp = ReflectPath(dp)
        m1 = rp.exec_module()
        m2 = rp.exec_module()
        self.assertNotEqual(m1.foo, m2.foo)


class ReflectDocblockTest(TestCase):
    def test_parse(self):
        db = "description\n:param foo: foo desc\n:returns: return desc\n"
        rdb = ReflectDocblock(db)
        self.assertTrue(rdb.info)

    def test_parse_directive(self):
        db = (
            ".. note::\n"
            "   directive desc line 1\n"
            "   directive desc line 2\n"
            "not directive description"
        )
        rdb = ReflectDocblock(db)
        body = list(rdb.get_bodies("note"))[0]
        self.assertTrue("desc line 1" in body)
        self.assertTrue("desc line 2" in body)
        self.assertFalse("not directive" in body)

    def test_get_signature_info(self):
        db = (
            ":param one: desc one\n"
            ":arg two: desc two\n"
            ":arg three: desc three\n"
            ":keyword four: desc four\n"
        )
        rdb = ReflectDocblock(db)
        siginfo = rdb.get_signature_info()

        for name in ["two", "three"]:
            self.assertTrue(name in siginfo["positional_only_names"])
            self.assertTrue(name in siginfo["descriptions"])

        self.assertTrue("four" in siginfo["keyword_only_names"])
        self.assertTrue("four" in siginfo["descriptions"])

        self.assertFalse("one" in siginfo["keyword_only_names"])
        self.assertFalse("one" in siginfo["positional_only_names"])
        self.assertTrue("one" in siginfo["descriptions"])

    def test_blank_lines(self):
        db = (
            "description line 1\n"
            "\n"
            ":example:\n"
            "\n"
            "    example line 1\n"
            "    example line 2\n"
            "    \n"
            "    example line 3\n"
            "\n"
            "description line 2"
        )
        rdb = ReflectDocblock(db)

        example = list(rdb.get_bodies("example"))[0]
        self.assertTrue("example line 1" in example)
        self.assertTrue("example line 2\n    \nexample line 3" in example)

        desc = list(rdb.get_bodies("description"))[0]
        self.assertTrue("description line 1\n\ndescription line 2" in desc)


class ReflectASTTest(TestCase):
    def test_get_expr_value(self):
        n = ast.parse("1234")
        ra = ReflectAST(n.body[0].value)
        self.assertTrue(isinstance(ra.get_expr_value(), int))

        n = ast.parse("\"one two three four\"")
        ra = ReflectAST(n.body[0].value)
        self.assertTrue(isinstance(ra.get_expr_value(), str))

        n = ast.parse("12.34")
        ra = ReflectAST(n.body[0].value)
        self.assertTrue(isinstance(ra.get_expr_value(), float))


class ReflectParamTest(TestCase):
    def test_positional_1(self):
        def foo(a, /): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        self.assertEqual("a", rp.name)
        self.assertTrue(rp.is_positional())
        self.assertFalse(rp.is_keyword())
        self.assertFalse(rp.is_catchall())

    def test_positional_2(self):
        def foo(*args): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        self.assertEqual("args", rp.name)
        self.assertTrue(rp.is_positional())
        self.assertFalse(rp.is_keyword())
        self.assertTrue(rp.is_catchall())

    def test_param_1(self):
        def foo(a: int): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        self.assertEqual("a", rp.name)
        self.assertTrue(rp.is_param())
        self.assertTrue(rp.is_positional())
        self.assertTrue(rp.is_keyword())
        self.assertFalse(rp.is_catchall())
        self.assertIsNotNone(rp.reflect_type())

    def test_keyword_1(self):
        def foo(*, a): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        self.assertEqual("a", rp.name)
        self.assertFalse(rp.is_positional())
        self.assertTrue(rp.is_keyword())
        self.assertFalse(rp.is_catchall())

    def test_positional_2(self):
        def foo(**kwargs): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        self.assertEqual("kwargs", rp.name)
        self.assertFalse(rp.is_positional())
        self.assertTrue(rp.is_keyword())
        self.assertTrue(rp.is_catchall())

    def test_get_docblock(self):
        def foo(a):
            """
            :param a: the desc of a
            """
            pass

        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        doc = rp.get_docblock()
        self.assertEqual("the desc of a", doc)

    def test_get_argparse_keywords_choices(self):
        def foo(a: Literal["foo", "bar"]): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual(2, len(flags["choices"]))

    def test_get_argparse_keywords_bool(self):
        def foo(a = True): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual("store_false", flags["action"])

        def foo(a = False): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual("store_true", flags["action"])

        def foo(a: bool = False): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual("store_true", flags["action"])

        def foo(a: bool): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual("store_true", flags["action"])

        def foo(a: bool = True): pass
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertEqual("store_false", flags["action"])

    def test_get_argparse_keywords_help(self):
        def foo(bar: str):
            """
            :param bar: the help description for bar
            """
        rm = ReflectCallable(foo)
        rp = next(rm.reflect_params())
        flags = rp.get_argparse_keywords()
        self.assertTrue("help" in flags)


class ReflectABCTest(TestCase):
    def test___init_subclass___simple(self):
        classes = self.create_module_classes("""
            from datatypes.reflection.inspect import (
                ReflectClass,
                ReflectCallable,
            )

            class RC(ReflectClass):
                pass

            class RM(ReflectCallable):
                pass
        """)

        RC = classes["RC"]

        reflect_class = RC.find_reflect_class(ReflectCallable)
        self.assertEqual(classes["RM"], reflect_class)

        reflect_class = RC.find_reflect_class(ReflectDocblock)
        self.assertEqual(ReflectDocblock, reflect_class)

    def test___init_subclass___multi(self):
        classes1 = self.create_module_classes("""
            from datatypes.reflection.inspect import (
                ReflectClass,
                ReflectCallable,
            )

            class RM1(ReflectCallable):
                pass

            class RC1(ReflectClass):
                pass
        """)

        modpath = classes1["RC1"].__module__
        classes2 = self.create_module_classes(f"""
            from {modpath} import RC1

            class RC2(RC1):
                pass
        """)

        RC = classes2["RC2"]

        reflect_class = RC.find_reflect_class(ReflectCallable)
        self.assertEqual(classes1["RM1"], reflect_class)

