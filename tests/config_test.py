# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
#from unittest import TestCase

from datatypes.compat import *
from datatypes.config import (
    Environ,
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
        self.assertEqual(set(["FOOBAR_CHE", "FOOBAR_CHE_1", "FOOBAR_CHE2"]), nkeys)

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

