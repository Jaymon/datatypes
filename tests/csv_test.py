# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.csv import (
    CSV,
)

from . import TestCase, testdata


class CSVTest(TestCase):
    def test_read(self):
        """make sure we can read a utf encoded csv file"""
        csvfile = testdata.create_csv({
            "foo": testdata.get_name,
            "bar": testdata.get_words,
            "che": testdata.get_int,
        })

        c = CSV(csvfile)
        for count, row in enumerate(c):
            for k in ["foo", "bar", "che"]:
                self.assertTrue(k in row)
        self.assertLess(0, count)

    def test_write(self):
        filepath = testdata.get_file(testdata.get_filename(ext="csv"))
        with CSV(filepath) as c:
            for x in range(10):
                d = {
                    "foo": testdata.get_name(),
                    "bar": testdata.get_words(),
                }
                c.add(d)

        c = CSV(filepath)
        for count, row in enumerate(c):
            for k in ["foo", "bar"]:
                self.assertTrue(k in row)
                self.assertEqual(2, len(row))
        self.assertLess(0, count)

    def test_find_fieldnames(self):
        csvfile = testdata.create_csv({
            "foo": testdata.get_name,
            "bar": testdata.get_words,
            "che": testdata.get_int,
        })
        c = CSV(csvfile)
        self.assertEqual(["foo", "bar", "che"], c.find_fieldnames())

