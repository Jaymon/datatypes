# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.config import (
    Config,
    Environ,
    Settings,
    MultiSettings,
)
from datatypes.config.environ.token import EnvironTokenizer

from . import TestCase, testdata


class EnvironTokenizerTest(TestCase):
    def test_next_simple(self):
        ts = EnvironTokenizer("FOO=foobar")

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foobar", t.value)

    def test_escaped(self):
        ts = EnvironTokenizer("FOO=foo\\$bar")

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foo$bar", t.value)

    def test_string(self):
        ts = EnvironTokenizer("FOO=foo\"bar\"")

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foobar", t.value)

    def test_variable(self):
        environ = Environ(environ={})
        buffer = "\n".join([
            "FOO=foobar",
            "BAR=che$FOO",
            "BAZ=boo${BAR}",
            ""
        ])
        ts = EnvironTokenizer(buffer, environ)

        t = ts.next()
        environ.set(t.name, t.value)

        t = ts.next()
        environ.set(t.name, t.value)
        self.assertEqual("BAR", t.name)
        self.assertEqual("chefoobar", t.value)

        t = ts.next()
        self.assertEqual("BAZ", t.name)
        self.assertEqual("boochefoobar", t.value)

    def test_next_multiline_1(self):
        buffer = "\n".join([
            "FOO=foobar \\",
            "  che bar \\ # comment",
            "baz",
            ""
        ])
        ts = EnvironTokenizer(buffer)

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foobar che bar baz", t.value)

        t = ts.next()
        self.assertIsNone(t)

    def test_next_multiline_2(self):
        buffer = "\n".join([
            "FOO=foobar \\ # comment 1",
            "  che # comment 2",
            "BAZ=barfoo",
            ""
        ])

        ts = EnvironTokenizer(buffer)

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foobar che ", t.value)

        t = ts.next()
        self.assertEqual("BAZ", t.name)
        self.assertEqual("barfoo", t.value)

    def test_export(self):
        buffer = "export FOO=foobar"
        ts = EnvironTokenizer(buffer)

        t = ts.next()
        self.assertEqual("FOO", t.name)
        self.assertEqual("foobar", t.value)


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

    def test_setdefault(self):
        environ = Environ()
        self.assertFalse("BAR" in environ)

        environ.setdefault("BAR", 1)
        self.assertTrue("BAR" in environ)
        self.assertEqual(1, environ["BAR"])

        environ.setdefault("BAR", 2)
        self.assertEqual(1, environ["BAR"])

        environ.setdefault("BAR", 2, override=True)
        self.assertEqual(2, environ["BAR"])

    def test_load_path(self):
        environ = Environ(environ={})

        p = self.create_file("""
            FOO=bar"che"
        """)
        environ.load_path(p)
        self.assertEqual("barche", environ["FOO"])

        p = self.create_file("""
            BAR=boo$FOO"
        """)
        environ.load_path(p)
        self.assertEqual("boobarche", environ["BAR"])


class SettingsTest(TestCase):
    def test_preference(self):
        with self.environ(FOO=5, BAR=6):
            s = Settings({"BAR": 7}, prefix="")

            self.assertEqual("5", s.FOO)
            self.assertEqual(7, s.BAR)

        with self.assertRaises(KeyError):
            s.FOO

    def test_config(self):
        config_file = self.create_file([
            "[Common]",
            "home_dir: /Users",
            "library_dir: /Library",
        ])

        s = Settings(config=config_file)

        self.assertEqual("/Users", s.Common["home_dir"])

        s["Common"] = {
            "home_dir": "/Foo/Bar",
        }

        self.assertEqual("/Foo/Bar", s.Common["home_dir"])

        with self.assertRaises(KeyError):
            s.Common["library_dir"]

    def test_get(self):
        with self.environ(FOO_BAR=5):
            s = Settings(prefix="FOO_")
            v1 = s.get("BAR", "bah")
            v2 = s["BAR"]
            self.assertEqual(v1, v2)

            self.assertIsNone(s.get("klsfjdkfl"))


class MultiSettingsTest(TestCase):
    def test_multi(self):
        s = MultiSettings({"foo": 1})

        with self.assertRaises(KeyError):
            s.bar

        self.assertEqual(1, s.foo)

    def test_environ_key(self):
        s = MultiSettings(prefix="FOOBAR_")
        self.assertIsNotNone(s.foobar)

        s = Settings(prefix="FOOBAR_")
        self.assertIsNotNone(s.foobar)

    def test_config_key(self):
        config_file = self.create_file([
            "[Common]",
            "home_dir: /Users",
        ])
        fileroot=config_file.fileroot

        s = Settings(config=config_file)
        self.assertIsNotNone(s[fileroot])

        s = MultiSettings(config=config_file)
        self.assertIsNotNone(s[fileroot])

    def test_add_environ(self):
        s = MultiSettings(prefix="FOO_")

        with self.environ(FOO_BAR=1, CHE_BOO=2):
            self.assertEqual("1", s.BAR)
            self.assertIsNone(s.get("BOO", None))

            environ = Environ("CHE_")
            s.add_environ(environ)
            self.assertEqual("2", s.BOO)

    def test_add_settings(self):
        sub_s = MultiSettings(prefix="BAR_")
        s = MultiSettings(prefix="FOO_", settings=[sub_s])

        with self.environ(FOO_BAR=1, BAR_BOO=2):
            self.assertEqual("1", s.BAR)
            self.assertEqual("2", s.BOO)

    def test_conflicting_values(self):
        environs = [Environ("FOO_"), Environ("BAR_")]
        s = MultiSettings(environs=environs)
        with self.environ(FOO_BOO=1, BAR_BOO=2):
            # less information goes to the first and since FOO_ is the first
            # environ in the list it will beat BAR_
            self.assertEqual(s.BOO, s.FOO_BOO)
            # giving more information is how the later value can be pulled
            self.assertEqual("2", s.BAR_BOO)

    def test_keyerror(self):
        with self.assertRaises(KeyError):
            s = MultiSettings()
            s["FOO"]

    def test_methods(self):
        class FooSettings(MultiSettings):
            def is_working(self):
                return True

        s = MultiSettings(settings=[FooSettings()])
        self.assertTrue(s.is_working())

    def test_get(self):
        with self.environ(FOO_BAR=5):
            environs = [Environ("FOO_")]
            s = MultiSettings(environs=environs)
            v1 = s.get("BAR", "bah")
            v2 = s["BAR"]
            self.assertEqual(v1, v2)

