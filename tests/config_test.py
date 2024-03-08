# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.config import (
    Config,
    Environ,
    Settings,
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


class SettingsTest(TestCase):
    def test_preference(self):
        with self.environ(FOO=5, BAR=6):
            s = Settings({"BAR": 7}, prefix="")

            self.assertEqual("5", s.FOO)
            self.assertEqual(7, s.BAR)

        with self.assertRaises(AttributeError):
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

