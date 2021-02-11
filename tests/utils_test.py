# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.utils import (
    cbany,
    cball,
)

from . import TestCase, testdata


class CBAnyTest(TestCase):
    def test_any(self):
        d = {"foo": "foo", "bar": "bar"}
        self.assertFalse(cbany(lambda r: r[0] != r[1], d.items()))


class CBAllTest(TestCase):
    def test_all(self):
        d = {"foo": "foo", "bar": "bar"}
        self.assertFalse(cball(lambda r: r[0] != r[1], d.items()))

