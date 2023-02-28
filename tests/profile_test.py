# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.profile import (
    Profiler,
    Profile,
    AggregateProfiler,
)

from . import TestCase, testdata


class ProfilerTest(TestCase):
    def test_with(self):
        with Profiler() as total:
            pass
        self.assertTrue(isinstance(total, Profile))

    def test_with_variations(self):
        p = Profiler()

        with p("instance with call"):
            pass
        self.assertTrue("instance with call" in str(p))

        with p:
            pass
        self.assertTrue(str(p).startswith("> "))

        with Profiler("create with") as p:
            pass
        self.assertTrue("create with" in str(p))

    def test_nested(self):
        p = Profiler()

        with p("one"):
            with p("two"):
                with p("three"):
                    pass
        self.assertTrue("one > two > three >" in str(p))

        with p("four"):
            with p("five"):
                pass
        self.assertTrue("four > five >" in str(p))


class AggregateProfilerTest(TestCase):
    def test___new__(self):
        ap = AggregateProfiler()
        ap2 = AggregateProfiler()
        self.assertTrue(ap is ap2)

    def test_count(self):
        p = AggregateProfiler()

        with p("one"):
            with p("one"):
                with p("two"):
                    pass

        with p("one"):
            pass

        with p("two"):
            with p("one"):
                pass

        r = p.output()
        self.assertTrue("two ran 2 times" in r)
        self.assertTrue("one ran 4 times" in r)

