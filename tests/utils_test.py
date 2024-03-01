# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.utils import (
    cbany,
    cball,
    make_list,
    make_dict,
    infer_type,
)

from . import TestCase, IsolatedAsyncioTestCase


class CBAnyTest(TestCase):
    def test_any(self):
        d = {"foo": "foo", "bar": "bar"}
        self.assertFalse(cbany(lambda r: r[0] != r[1], d.items()))


class CBAllTest(TestCase):
    def test_all(self):
        d = {"foo": "foo", "bar": "bar"}
        self.assertFalse(cball(lambda r: r[0] != r[1], d.items()))


class MakeListTest(TestCase):
    def test_list(self):

        a = [
            [1, 2, 3],
            4,
        ]
        self.assertEqual([1, 2, 3, 4], make_list(a))

        a = [
            "one",
            "two",
            "three",
        ]
        self.assertEqual(a, make_list(a))

        a = "one"
        self.assertEqual([a], make_list([a]))

        a = 1
        self.assertEqual([a], make_list([a]))

    def test_non_list(self):
        r = make_list(1)
        self.assertEqual([1], r)

        r = make_list("foo")
        self.assertEqual(["foo"], r)

        r = make_list(self.get_past_datetime())
        self.assertEqual(1, len(r))


class MakeDictTest(TestCase):
    def test_combining(self):
        d = make_dict(
            {"foo": 1},
            ("bar", 2),
            [("che", 3), ("baz", 4)],
        )
        self.assertEqual({"foo": 1, "bar": 2, "che": 3, "baz": 4}, d)

    def test_precedence(self):
        d = make_dict(
            {"foo": 1},
            {"foo": 2}
        )
        self.assertEqual({"foo": 2}, d)


class InferTypeTest(TestCase):
    def test_int(self):
        v = infer_type("1234")
        self.assertEqual(1234, v)

    def test_float(self):
        v = infer_type("1234.56")
        self.assertEqual(1234.56, v)

    def test_bool(self):
        v = infer_type("True")
        self.assertTrue(v)

