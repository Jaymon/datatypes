# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.csv import (
    CSV,
    TempCSV,
)

from . import TestCase, testdata


class CSVTest(TestCase):
    def test_header_1(self):
        path = testdata.create_file()
        csv = CSV(path)
        with csv:
            for index in range(2):
                csv.add({"foo": index, "bar": testdata.get_words()})

        self.assertEqual(2, len(csv.fieldnames))

        count = 0
        for row in csv:
            count += 1
        self.assertEqual(2, count)

        csv2 = CSV(path, fieldnames=csv.fieldnames)
        self.assertEqual(2, len(csv.fieldnames))
        count = 0
        for row in csv2:
            count += 1
        self.assertEqual(2, count)

        csv2 = CSV(path)
        self.assertEqual(2, len(csv.fieldnames))
        count = 0
        for row in csv2:
            count += 1
        self.assertEqual(2, count)

    def test_header_unicode(self):
        row = {
            testdata.get_unicode_word(): testdata.get_words(),
            testdata.get_unicode_word(): testdata.get_words(),
        }
        path = testdata.create_file()
        csv = CSV(path, fieldnames=row.keys())
        with csv:
            csv.add(row)

        csv2 = CSV(path)
        row2 = csv2.rows()[0]
        return
        self.assertEqual(row, row2)

    def test_read_unicode(self):
        """make sure we can read a utf encoded csv file"""
        csvfile = testdata.create_csv({
            "foo": testdata.get_unicode_name,
            "bar": testdata.get_unicode_words,
            "che": testdata.get_int,
        })

        c = CSV(csvfile.path)
        for count, row in enumerate(c, 1):
            for k in ["foo", "bar", "che"]:
                self.assertTrue(k in row)
                self.assertTrue(bool(row[k]))
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
        c = CSV(csvfile.path)
        self.assertEqual(["foo", "bar", "che"], c.find_fieldnames())

    def test_continue_error(self):
        counter = testdata.get_counter()
        csvfile = testdata.create_csv({
            "foo": counter,
            "bar": testdata.get_words,
        }, count=10)

        class ContinueCSV(CSV):
            def normalize_reader_row(self, row):
                if int(row["foo"]) % 2 == 0:
                    raise self.ContinueError()
                return row

        r1 = ContinueCSV(csvfile.path).rows()
        r2 = CSV(csvfile.path).rows()
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

        c = CSV(csvfile.path, reader_row_class=Row)
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

        c = CSV(csvfile.path, reader_row_class=Row)
        for row in c:
            self.assertTrue(isinstance(row, Row))
            count += 1
        self.assertLess(0, count)

    def test_strict(self):
        csv = TempCSV(["foo", "bar"], strict=True)

        with csv:
            with self.assertRaises(ValueError):
                csv.add({"foo": 1})

            with self.assertRaises(ValueError):
                csv.add({"foo": 1, "che": 3})

        csv = TempCSV(["foo", "bar"], strict=False)
        with csv:
            csv.add({"foo": 1})
            csv.add({"foo": 1, "che": 3})


