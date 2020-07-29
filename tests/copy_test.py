# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.copy import (
    Deepcopy,
)

from . import TestCase, testdata


class DeepcopyTest(TestCase):
    def test_copy_class(self):

        class Foo(object):
            bar = 1

        f = Foo()
        f.che = list(range(5))

        f.baz = {"foo": 10, "bar": 20}

        f.fp = testdata.create_file().open()

        dc = Deepcopy()
        f2 = dc.copy(f)
        self.assertEqual(f.baz, f2.baz)
        self.assertEqual(f.che, f2.che)

        f2.che.extend(range(100, 200))
        self.assertNotEqual(f.che, f2.che)

        f2 = dc.copy(f, ignore_keys=["baz"])
        with self.assertRaises(AttributeError):
            f2.baz

        f.fp.close()
        f2.fp.close()

    def test_copy_dict(self):

        class Foo(object):
            def __init__(self, bar, che):
                self.bar = bar
                self.che = che

            def __getnewargs__(self):
                return (self.bar, self.che)

            def __getnewargs_ex__(self):
                return self.__getnewargs__(), {}


        f = Foo(100, {"che": 10})
        d = {"foo": f, "bar": 20}

        dc = Deepcopy()
        d2 = dc.copy(d)
        self.assertNotEqual(d, d2)

        d2["foo"].bar *= 2
        self.assertNotEqual(d["foo"].bar, d2["foo"].bar)

        d2["foo"].che["che"] *= 2
        self.assertNotEqual(d["foo"].che["che"], d2["foo"].che["che"])


