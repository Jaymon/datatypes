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
            "foo": testdata.get_unicode_name,
            "bar": testdata.get_unicode_words,
            "che": testdata.get_int,
        })

        c = CSV(csvfile)
        for count, row in enumerate(c):
            for k in ["foo", "bar", "che"]:
                self.assertTrue(k in row)
                self.assertTrue(row[k])
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
                self.assertTrue(row[k])
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

    def test_continue_error(self):
        counter = testdata.get_counter()
        csvfile = testdata.create_csv({
            "foo": counter,
            "bar": testdata.get_words,
        })

        class ContinueCSV(CSV):
            def normalize_reader_row(self, row):
                if int(row["foo"]) % 2 == 0:
                    raise self.ContinueError()
                return row

        c = ContinueCSV(csvfile)
        r1 = c.rows()
        r2 = CSV(csvfile).rows()
        self.assertLess(len(r1), len(r2))

    def test_reader_row_class(self):
        count = 0
        counter = testdata.get_counter()
        csvfile = testdata.create_csv({
            "foo": counter,
            "bar": testdata.get_words,
        })

        class Row(dict):
            pass

        c = CSV(csvfile, reader_row_class=Row)
        for row in c:
            self.assertTrue(isinstance(row, Row))
            count = int(row["foo"])
        self.assertLess(0, count)

    def test___init___kwargs(self):
        count = 0
        counter = testdata.get_counter()
        csvfile = testdata.create_csv({
            "foo": counter,
            "bar": testdata.get_words,
        })

        class Row(dict):
            pass

        c = CSV(csvfile, reader_row_class=Row)
        for row in c:
            self.assertTrue(isinstance(row, Row))
            count += 1
        self.assertLess(0, count)

