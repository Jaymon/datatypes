# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.parse import (
    ArgvParser,
    ArgParser,
    Version,
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

    def test_hyphen_to_underscore(self):
        extra_args = [
            "--foo-bar=1",
            "--che-bar",
            "2",
            "--baz-bar",
        ]
        d = ArgvParser(extra_args, hyphen_to_underscore=True)
        self.assertEqual(3, len(d))
        for k in ["foo_bar", "che_bar", "baz_bar"]:
            self.assertTrue(k in d)

    def test_unwrap_optionals(self):
        extra_args = [
            "--foo=1",
            "--foo=2",
            "--foo", "3",
            "--bar", "4",
        ]
        d = ArgvParser(extra_args).unwrap_optionals()
        self.assertEqual(3, len(d["foo"]))
        self.assertEqual("4", d["bar"])

    def test_info(self):
        extra_args = [
            "--foo=1",
            "--foo=2",
            "--bar", "4",
            "--foo", "3",
        ]
        d = ArgvParser(extra_args)

        self.assertEqual([0, 1, 4, 5], d.info["foo"]["indexes"])
        self.assertEqual([2, 3], d.info["bar"]["indexes"])

    def test_infer_types(self):
        extra_args = [
            "--foo=1",
            "--bar=2.5",
            "--che", "True",
            "--bam", "normal string",
        ]
        d = ArgvParser(extra_args, infer_types=True)
        self.assertEqual(1, d["foo"][0])
        self.assertEqual(2.5, d["bar"][0])
        self.assertEqual(True, d["che"][0])
        self.assertEqual("normal string", d["bam"][0])

    def test_types_dict(self):
        extra_args = [
            "--foo=1",
            "--bar=2.5",
            "--che", "True",
            "--bam", "normal string",
        ]
        types = {
            "foo": int,
            "bar": float,
        }
        d = ArgvParser(extra_args, types=types)
        self.assertEqual(1, d["foo"][0])
        self.assertEqual(2.5, d["bar"][0])
        self.assertEqual("True", d["che"][0])
        self.assertEqual("normal string", d["bam"][0])



class ArgParserTest(TestCase):
    def test_parse(self):
        d = ArgParser(
            "--foo=1 --che --baz=\"this=that\" --bar 2 --foo=2 -z 3 4"
        )
        self.assertEqual(["1", "2"], d["foo"])
        self.assertEqual(["4"], d["*"])
        self.assertEqual(["2"], d["bar"])
        self.assertEqual(["3"], d["z"])
        self.assertEqual(["this=that"], d["baz"])
        self.assertEqual([True], d["che"])


class VersionParser(TestCase):
    def test_parts(self):
        v = Version("2.3.1")
        self.assertEqual([2, 3, 1], v.parts)

        v = Version("2.3.a1")
        self.assertEqual([2, 3, "a1"], v.parts)

    def test_compare(self):
        self.assertTrue(Version("6.2.7") > "6.2")
        self.assertFalse(Version("6.2.7") == "6.2")
        self.assertTrue("6.2" < Version("6.2.7"))
        self.assertTrue(Version("6.2") < Version("6.2.7"))

        self.assertTrue(Version("1.0.1-beta.1") > "1.0.0")
        self.assertTrue(Version("0.1.1rc1") < "0.1.1rc2")
        self.assertFalse(Version("0.34~") < "0.33")
        self.assertTrue(Version("0.2.2") == "0.2.*")
        self.assertTrue("0.2.*" == Version("0.2.2"))

        self.assertFalse(Version("1.3.a4") > "1.3.dev-1")
        self.assertFalse("1.3.dev-1" < Version("1.3.a4"))

        self.assertTrue(Version("2.3.1") < "10.1.2")
        self.assertTrue("10.1.2" > Version("2.3.1"))

        self.assertTrue(Version("1.3.a4") < "10.1.2")
        self.assertTrue("10.1.2" > Version("1.3.a4"))

        self.assertTrue(Version("1.3.a4") < "1.3.xy123")
        self.assertTrue("1.3.xy123" > Version("1.3.a4"))

        self.assertTrue(Version("1.3.10") > "1.3.dev-1")
        self.assertTrue("1.3.dev-1" < Version("1.3.10"))

        self.assertTrue(Version("1.3.10") >= "1.3.10")
        self.assertTrue("1.3.10" <= Version("1.3.10"))

        self.assertTrue(Version("1.3.10") <= "1.3.10")
        self.assertTrue("1.3.10" >= Version("1.3.10"))

        self.assertTrue(Version("1.3.10") == "1.3.10")
        self.assertTrue("1.3.10" == Version("1.3.10"))

        self.assertTrue(Version("1.a3.1") < "1.a3.2")
        self.assertTrue("1.a3.2" > Version("1.a3.1"))
        self.assertTrue(Version("1.a3.2") > Version("1.a3.1"))

