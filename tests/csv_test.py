# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.csv import (
    CSV,
    CSVRow,
    CSVRowDict,
    TempCSV,
)

from . import TestCase, testdata


class CSVRowTest(TestCase):
    def create_row(self):
        c = self.create_csv({
            "foo": self.get_name,
            "bar": self.get_int,
        })
        row = c.tolist()[0]
        self.assertTrue(isinstance(row, CSVRow))
        return row

    def test_crud(self):
        row = self.create_row()
        bar1 = int(row["bar"])
        row["bar"] = bar1 + 10
        self.assertLess(bar1, row["bar"])
        self.assertEqual(2, len(row))

        che1 = "che value"
        row["che"] = che1
        self.assertEqual(che1, row["che"])
        self.assertEqual(3, len(row))

        del row["bar"]
        self.assertEqual(2, len(row))
        with self.assertRaises(KeyError):
            row["bar"]

    def test_items(self):
        row = self.create_row()

        d = {}
        for k, v in row.items():
            d[k] = v
        self.assertEqual(d, row)

    def test_contains(self):
        row = self.create_row()
        self.assertTrue("foo" in row)

    def test_pop(self):
        row = self.create_row()

        with self.assertRaises(KeyError):
            row.pop("DOES-NOT-EXIST")

        self.assertEqual(None, row.pop("DOES-NOT-EXIST", None))

        v1 = row["bar"]
        v2 = row.pop("bar")
        self.assertEqual(v1, v2)

        with self.assertRaises(KeyError):
            row.pop("bar")

    def test_mutable(self):
        c = self.create_csv({
            "foo": self.get_name,
        })

        for i, row in enumerate(c, 1):
            self.assertTrue("foo" in row)
            self.assertFalse("bar" in row)

            row["bar"] = i
            self.assertTrue("bar" in row)

            del row["foo"]
            self.assertFalse("foo" in row)
        self.assertLess(0, i)

    def test_methods(self):
        row = self.create_row()
        drow = CSVRowDict(row.columns, row.lookup)

        self.assertFalse(isinstance(row, dict))
        self.assertTrue(isinstance(row, Mapping))

        self.assertTrue("foo" in row)

        r = row.copy()
        self.assertEqual(r, row)

        self.assertEqual(row["foo"], row.get("foo"))

        self.assertEqual([k for k in row], [k for k in row.keys()])
        self.assertEqual([k for k in drow], [k for k in row.keys()])

        self.assertEqual([v for v in row.values()], [v for v in row.values()])
        self.assertEqual([v for v in drow.values()], [v for v in row.values()])

        self.assertEqual(len(row), len([c for c in row.items()]))
        self.assertEqual(len(row), len([k for k in row.keys()]))
        self.assertEqual(len(row), len([k for k in reversed(row)]))
        self.assertEqual(len(row), len([v for v in row.values()]))

        row.setdefault("che", 1)
        self.assertEqual(1, row["che"])

        row.update({"che": 2})
        self.assertEqual(2, row["che"])
        self.assertEqual(3, len(row))

        r = row | {"che": 3}
        self.assertEqual(3, row["che"])
        self.assertEqual(3, len(row))

        row |= {"che": 4}
        self.assertEqual(4, row["che"])
        self.assertEqual(3, len(row))

        self.assertEqual(4, row.pop("che", None))

        r = row.popitem()
        self.assertTrue(r[0] in ["foo", "bar"])

        row.clear()
        self.assertEqual(0, len(row))

    def test_list_index_range_error(self):
        """The CSVRow was giving a different value than the CSVRowDict when
        the row was empty, this makes sure they act similar
        """
        csvfile = testdata.create_csv([{"foo": 1, "bar": 2}])
        csvfile.path.append_text("\n")

        csv1 = CSV(csvfile.path, reader_row_class=CSVRowDict)
        csv2 = CSV(csvfile.path)
        for rows in zip(csv1, csv2):
            self.assertEqual(bool(rows[0]), bool(rows[1]))

        csv3 = CSV(csvfile.path)
        for row in csv3:
            d1 = dict(row)
            d2 = {**row}
            self.assertEqual(d1, d2)
            self.assertEqual(bool(row), bool(d1))


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
        self.assertEqual(row, row2)

    def test_header_2(self):
        path = testdata.create_file()
        csv = CSV(path)

        csv.add({"foo": 1, "bar": 2})
        csv.add({"foo": 3, "bar": 4})
        self.assertEqual(1, csv.read_text().count("foo"))

        with path.open("a") as fp:
            csv = CSV(fp)
            csv.add({"foo": 5, "bar": 6})
        self.assertEqual(1, CSV(path).read_text().count("foo"))

    def test_fieldnames(self):
        path = testdata.create_file()
        fieldnames = ["foo", "bar"]
        csv = CSV(path, fieldnames=fieldnames)
        self.assertEqual(fieldnames, csv.fieldnames)
        self.assertEqual(set(fieldnames), set(csv.lookup.keys()))

    def test_find_fieldnames(self):
        csvfile = testdata.create_csv({
            "foo": testdata.get_name,
            "bar": testdata.get_words,
            "che": testdata.get_int,
        })
        c = CSV(csvfile.path)
        self.assertEqual(["foo", "bar", "che"], c.find_fieldnames())

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

    def test_write_1(self):
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

    def test_write_read_unicode(self):
        keys = [
            testdata.get_unicode_word(),
            testdata.get_unicode_word()
        ]
        row = {
            keys[0]: testdata.get_unicode_words(),
            keys[1]: testdata.get_unicode_words(),
        }
        path = testdata.create_file()
        csv = CSV(path, fieldnames=keys)
        with csv:
            csv.add(row)

        csv2 = CSV(path)
        row2 = csv2.rows()[0]
        self.assertEqual(row, row2)

        row3 = {
            keys[0]: testdata.get_unicode_words(),
            keys[1]: testdata.get_unicode_words(),
        }
        with path.open("a+") as fp:
            csv = CSV(fp, fieldnames=keys)
            csv.add(row3)

        rows = CSV(path).tolist()
        self.assertEqual(row, rows[0])
        self.assertEqual(row3, rows[1])

    def test_continue_error(self):
        counter = testdata.get_counter()
        csvfile = testdata.create_csv({
            "foo": counter,
            "bar": testdata.get_words,
        }, count=10)

        class ContinueCSV(CSV):
            def create_reader_row(self, columns, **kwargs):
                row = super().create_reader_row(columns, **kwargs)
                if row and int(row["foo"]) % 2 == 0:
                    row = None
                return row

        r1 = ContinueCSV(csvfile.path).rows()
        r2 = CSV(csvfile.path).rows()
        self.assertLess(len(r1), len(r2))

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

    def test_none(self):
        """By default, CSV subs "" for None as a row value, unless strict=True
        then it will error out
        """
        csv = TempCSV(["foo", "bar"])
        with csv:
            csv.add({"foo": "", "bar": None})
        rows = list(csv)
        self.assertEqual("", rows[0]["foo"])
        self.assertEqual("", rows[0]["bar"])

        csv = TempCSV(["foo", "bar"])
        with csv:
            csv.add({"foo": "1", "bar": None})
        rows = list(csv)
        self.assertEqual("", rows[0]["bar"])

        csv = TempCSV(["foo", "bar"], strict=True)
        with self.assertRaises(TypeError):
            with csv:
                csv.add({"foo": "1", "bar": None})

    def test_stringio(self):
        fp = StringIO()
        csv = CSV(fp)

        keys = [
            testdata.get_unicode_word(),
            testdata.get_unicode_word()
        ]

        row1 = {
            keys[0]: testdata.get_unicode_words(),
            keys[1]: testdata.get_unicode_words(),
        }
        csv.add(row1)

        row2 = {
            keys[0]: testdata.get_unicode_words(),
            keys[1]: testdata.get_unicode_words(),
        }
        csv.add(row2)

        rows = csv.rows()
        self.assertEqual(row1, rows[0])
        self.assertEqual(row2, rows[1])

    def test_reading(self):
        fp = StringIO()
        csv = CSV(fp)

        self.assertFalse(fp.closed)
        with csv.reading():
            pass
        self.assertFalse(fp.closed)

    def test_writing(self):
        fp = StringIO()
        csv = CSV(fp)

        self.assertFalse(fp.closed)
        with csv.writing():
            pass
        self.assertFalse(fp.closed)

        with csv:
            pass
        self.assertFalse(fp.closed)

