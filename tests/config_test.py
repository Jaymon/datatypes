# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
#from unittest import TestCase

from datatypes.compat import *
from datatypes.config import (
    Environ,
    TOML,
)

from . import TestCase, testdata


class EnvironTest(TestCase):
    def test_nkeys(self):
        environ = Environ("FOOBAR_", {})
        environ.set("CHE", "0")
        environ.set("CHE_1", "1")
        environ.set("CHE2", "2")
        environ.set("CHE_4", "4")

        nkeys = set(environ.nkeys("CHE"))
        self.assertEqual(
            set(["FOOBAR_CHE", "FOOBAR_CHE_1", "FOOBAR_CHE2"]),
            nkeys
        )

    def test_paths(self):
        environ = Environ("FOO_PATHS_", {})
        environ.set("PATHS", "/foo/bar:/che/:/baz/boo/faz")

        paths = list(environ.paths("PATHS"))
        self.assertEqual(["/foo/bar", "/che/", "/baz/boo/faz"], paths)

    def test_type(self):
        environ = Environ("TYPE_", {"TYPE_FOO": "1000"})

        environ.setdefault("FOO", 2000, type=int)

        n = environ["FOO"]
        self.assertEqual(1000, n)
        self.assertTrue(isinstance(n, int))

        del environ["FOO"]
        n = environ["FOO"]
        self.assertEqual(2000, n)
        self.assertTrue(isinstance(n, int))


class TOMLTest(TestCase):
    def create_instance(self, lines):
        fp = self.create_file(lines)
        return TOML(fp)

    def test_table_setup(self):
        t = self.create_instance([
            "[foo]",
            "[foo.bar]",
            "[foo.\"bar.che\".bam]",
        ])

        self.assertIsNotNone(t.foo.bar)
        self.assertIsNotNone(t.foo["bar.che"].bam)

    def test_parse_array(self):
        t = self.create_instance([
            "foo = [1, 2]",
        ])
        self.assertEqual([1, 2], t.foo)

    def test_parse_dict(self):
        t = self.create_instance([
            "foo = { bar = 1, che = \"two\" }",
        ])
        self.assertEqual({"bar": 1, "che": "two"}, t.foo)

    def test_parse_1(self):
        t = self.create_instance([
            "[foo.bar]",
            "foo = 1",
            "bar = \"two\"",
            "che = [1, 2]",
        ])
        self.assertEqual(1, t.foo.bar.foo)
        self.assertEqual("two", t.foo.bar.bar)
        self.assertEqual([1, 2], t.foo.bar.che)

    def test_write(self):
        t = self.create_instance([
            "one = 1",
            "",
            "[foo]",
            "two = 2",
            "three = { four = 4, five = \"five\" }",
            "",
            "[foo.bar]",
            "six = \"six\"",
            "seven = [8, 9, \"ten\"]",
            "",
            "[eleven]",
            "twelve = 12",
        ])

        t.write()

        t2 = self.create_instance(t.path.read_text())
        self.assertEqual(t.sections, t2.sections)

    def test_add_section(self):
        t = self.create_instance("")

        t.add_section("foo.\"bar.che\".bam")
        self.assertIsNotNone(t.foo["bar.che"].bam)
        self.assertEqual(1, len(t.sections_order))

