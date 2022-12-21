# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.parse import (
    ArgvParser,
    ArgParser,
)

from . import TestCase, testdata


class ArgvParserTest(TestCase):
    def test_extra_args(self):
        extra_args = [
            "--foo=1",
            "--che",
            '--baz="this=that"',
            "--bar",
            "2",
            "--foo=2",
            "-z",
            "3",
            "4"
        ]

        d = ArgvParser(extra_args)
        self.assertEqual(["1", "2"], d["foo"])
        self.assertEqual(["4"], d["*"])
        self.assertEqual(["2"], d["bar"])
        self.assertEqual(["3"], d["z"])
        self.assertEqual(["this=that"], d["baz"])
        self.assertEqual([True], d["che"])

    def test_binary(self):
        extra_args = [
            b"--foo=1",
            b"--bar=2"
        ]
        d = ArgvParser(extra_args)
        self.assertEqual(["1"], d["foo"])
        self.assertEqual(["2"], d["bar"])


class ArgParserTest(TestCase):
    def test_parse(self):
        d = ArgParser("--foo=1 --che --baz=\"this=that\" --bar 2 --foo=2 -z 3 4")
        self.assertEqual(["1", "2"], d["foo"])
        self.assertEqual(["4"], d["*"])
        self.assertEqual(["2"], d["bar"])
        self.assertEqual(["3"], d["z"])
        self.assertEqual(["this=that"], d["baz"])
        self.assertEqual([True], d["che"])

