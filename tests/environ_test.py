# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.environ import (
    Environ,
)

from . import TestCase, testdata


class EnvironTest(TestCase):
    def test_nkeys(self):
        environ = Environ("FOOBAR_")
        environ.set("CHE", "0")
        environ.set("CHE_1", "1")
        environ.set("CHE2", "2")
        environ.set("CHE_4", "4")

        nkeys = set(environ.nkeys("CHE"))
        self.assertEqual(set(["FOOBAR_CHE", "FOOBAR_CHE_1", "FOOBAR_CHE2"]), nkeys)

    def test_paths(self):
        environ = Environ("FOO_PATHS_")
        environ.set("PATHS", "/foo/bar:/che/:/baz/boo/faz")

        paths = list(environ.paths("PATHS"))
        self.assertEqual(["/foo/bar", "/che/", "/baz/boo/faz"], paths)




