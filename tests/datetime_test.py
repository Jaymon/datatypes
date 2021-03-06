# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import pickle
import datetime

from datatypes.compat import *
from datatypes.datetime import (
    Datetime,
)
from datatypes.string import String

from . import TestCase, testdata


class DatetimeTest(TestCase):
    def test_hash(self):
        dt = Datetime()
        hash(dt) # if there isn't an error then the test passes

    def test_years(self):
        dt = Datetime(2021, 11, 30, years=-2)
        self.assertEqual(Datetime(2019, 11, 30), dt)

        dt = Datetime(2021, 11, 30, years=2)
        self.assertEqual(Datetime(2023, 11, 30), dt)

    def test_months(self):
        dt = Datetime(2021, 11, 30, months=-24)
        self.assertEqual(Datetime(2019, 11, 30), dt)

        dt = Datetime(2021, 11, 30, months=24)
        self.assertEqual(Datetime(2023, 11, 30), dt)

        dt = Datetime(2021, 12, 30, months=12)
        self.assertEqual(Datetime(2022, 12, 30), dt)

        dt = Datetime(2021, 8, 30, months=-6)
        self.assertEqual(Datetime(2021, 3, 2), dt)

        dt = Datetime(2021, 5, 23, months=-6)
        self.assertEqual(Datetime(2020, 11, 23), dt)

        dt = Datetime(2021, 6, 23, months=-6)
        self.assertEqual(Datetime(2020, 12, 23), dt)

        dt = Datetime(2021, 6, 5, months=6)
        self.assertEqual(Datetime(2021, 12, 5), dt)

        dt = Datetime(2020, 8, 30, months=-6)
        self.assertEqual(Datetime(2020, 3, 1), dt)

    def test_weeks(self):
        dt = Datetime(2021, 8, 30, weeks=-2)
        self.assertEqual(Datetime(2021, 8, 16), dt)

        dt = Datetime(2021, 8, 2, weeks=2)
        self.assertEqual(Datetime(2021, 8, 16), dt)

    def test_days(self):
        dt = Datetime(2021, 8, 30, days=-2)
        self.assertEqual(Datetime(2021, 8, 28), dt)

        dt = Datetime(2021, 8, 2, days=2)
        self.assertEqual(Datetime(2021, 8, 4), dt)

    def test_hours(self):
        dt = Datetime(2021, 8, 30, 20, hours=-2)
        self.assertEqual(Datetime(2021, 8, 30, 18), dt)

        dt = Datetime(2021, 8, 30, 20, hours=2)
        self.assertEqual(Datetime(2021, 8, 30, 22), dt)

    def test_seconds(self):
        dt = Datetime(2021, 8, 30, 20, seconds=-7200)
        self.assertEqual(Datetime(2021, 8, 30, 18), dt)

        dt = Datetime(2021, 8, 30, 20, seconds=7200)
        self.assertEqual(Datetime(2021, 8, 30, 22), dt)

    def test_replace_timedelta_kwargs(self):
        dt = Datetime(2021, 11, 30)
        rdt = dt.replace(months=-2)
        self.assertEqual(Datetime(2021, 9, 30), rdt)

    def test_date_compare(self):
        dt = Datetime()
        d = datetime.date(dt.year, dt.month, dt.day)

        self.assertFalse(d < dt)
        self.assertFalse(d > dt)
        self.assertTrue(d <= dt)
        self.assertTrue(d >= dt)
        self.assertTrue(d == dt)
        self.assertFalse(d != dt)

        self.assertFalse(dt < d)
        self.assertFalse(dt > d)
        self.assertTrue(dt <= d)
        self.assertTrue(dt >= d)
        self.assertTrue(dt == d)
        self.assertFalse(dt != d)

    def test_strftime_str(self):
        dt = Datetime()
        s = dt.strftime("%m/%d/%Y")
        self.assertTrue(isinstance(s, Str))

    def test_strftime_old_date(self):
        fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
        dt = Datetime(1800, 1, 1)

        s1 = Datetime.strftime(dt, fmt)
        s2 = dt.strftime(fmt)
        self.assertEqual(s1, s2)
        self.assertEqual("1800-01-01T00:00:00.000000Z", s1)

    def test_empty(self):
        d1 = Datetime()
        d2 = Datetime(None)
        d3 = Datetime("")
        self.assertTrue(d1 < d2 < d3)

    def test_pickle(self):
        d = Datetime()

        p = pickle.dumps(d, pickle.HIGHEST_PROTOCOL)
        d2 = pickle.loads(p)

        self.assertEqual(d, d2)

    def test_create(self):
        d1 = Datetime.utcnow()
        self.assertTrue(isinstance(d1, Datetime))

        d2 = Datetime()

        self.assertEqual(
            d1.strftime(Datetime.FORMAT_PRECISION_SECONDS),
            d2.strftime(Datetime.FORMAT_PRECISION_SECONDS)
        )

        d3 = Datetime(2018, 10, 5)
        d4 = Datetime(String(d3))
        self.assertEqual(
            d3.strftime(Datetime.FORMAT_PRECISION_DAY),
            d4.strftime(Datetime.FORMAT_PRECISION_DAY)
        )

    def test_has_time(self):
        d = Datetime(2019, 11, 5)
        self.assertFalse(d.has_time())

        d = Datetime()
        self.assertTrue(d.has_time())

    def test_create_precision(self):
        d = Datetime("2019-11-5")
        self.assertEqual(2019, d.year)
        self.assertEqual(11, d.month)
        self.assertEqual(5, d.day)
        self.assertEqual(0, d.hour)
        self.assertEqual(0, d.minute)
        self.assertEqual(0, d.second)
        self.assertEqual(0, d.microsecond)

        d = Datetime("2019-11-05")
        self.assertEqual(2019, d.year)
        self.assertEqual(11, d.month)
        self.assertEqual(5, d.day)

        d = Datetime("2019-11-05T23:35:04Z")
        self.assertEqual(2019, d.year)
        self.assertEqual(11, d.month)
        self.assertEqual(5, d.day)
        self.assertEqual(23, d.hour)
        self.assertEqual(35, d.minute)
        self.assertEqual(4, d.second)
        self.assertEqual(0, d.microsecond)

        d = Datetime("2019-11-05T23:35:04.546Z")
        self.assertEqual(2019, d.year)
        self.assertEqual(11, d.month)
        self.assertEqual(5, d.day)
        self.assertEqual(23, d.hour)
        self.assertEqual(35, d.minute)
        self.assertEqual(4, d.second)
        self.assertEqual(546000, d.microsecond)

    def test_timestamp(self):
        d = Datetime()
        ts = d.timestamp()
        self.assertTrue(isinstance(ts, float))

        d2 = Datetime(ts)
        self.assertEqual(d, d2)

        d3 = Datetime(int(ts))
        self.assertEqual(
            d.strftime(Datetime.FORMAT_PRECISION_SECONDS),
            d3.strftime(Datetime.FORMAT_PRECISION_SECONDS)
        )

    def test_strings(self):
        d = Datetime(2018, 10, 5, 23, 35, 4)
        self.assertEqual("2018-10-05", d.iso_date())
        self.assertEqual("2018-10-05T23:35:04Z", d.iso_seconds())

    def test___str__(self):
        ss = [
            "2019-11-05",
            "2019-11-05T23:35:04Z",
            "2019-11-05T23:35:04.546123Z",
        ]

        for s in ss:
            d = Datetime(s)
            self.assertEqual(s, str(d))

    def test_format_subclass(self):
        class DT(Datetime):
            FORMAT_CUSTOM = "%Y-%m-%d %H:%M:%S.%f"

        dt = DT("2020-03-19 00:00:00.000000000")
        self.assertEqual(2020, dt.year)
        self.assertEqual(3, dt.month)
        self.assertEqual(19, dt.day)
        self.assertFalse(dt.has_time())

    def test_isoformat(self):
        dt = Datetime()
        self.assertFalse(dt.isoformat().endswith("ZZ"))

        dt = Datetime("2020-03-19")
        self.assertEqual("2020-03-19", dt.isoformat())
        self.assertTrue(dt.isoformat(timespec="hours").endswith("Z"))
        self.assertTrue(dt.isoformat(timespec="minutes").endswith("Z"))
        self.assertTrue(dt.isoformat(timespec="seconds").endswith("Z"))
        self.assertTrue(dt.isoformat(timespec="milliseconds").endswith("Z"))
        self.assertTrue(dt.isoformat(timespec="microseconds").endswith("Z"))

    def test_names(self):
        dt = Datetime("2020-03-19")
        self.assertEqual("2020", dt.yearname)
        self.assertEqual("March", dt.monthname)
        self.assertEqual("Thursday", dt.dayname)

    def test_convert(self):
        s = "2020-03-25T19:34:05.00005Z"
        dt = Datetime(s)
        self.assertEqual(50, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.000050Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.05Z"
        dt = Datetime(s)
        self.assertEqual(50000, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.050000Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.0506Z"
        dt = Datetime(s)
        self.assertEqual(50600, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.050600Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.050060Z"
        dt = Datetime(s)
        self.assertEqual(50060, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.050060Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.000057Z"
        dt = Datetime(s)
        self.assertEqual(57, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.000057Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.057Z"
        dt = Datetime(s)
        self.assertEqual(57000, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.057000Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-25T19:34:05.057035Z"
        dt = Datetime(s)
        self.assertEqual(57035, dt.microsecond)
        self.assertEqual("2020-03-25T19:34:05.057035Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

        s = "2020-03-19 00:00:00.000000000"
        dt = Datetime(s)
        self.assertEqual("2020-03-19T00:00:00.000000Z", dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))


    def test_within(self):
        now = Datetime()

        self.assertTrue(now.within(-10000, 10000))
        self.assertFalse(now.within(-10000, -50000))

        start = datetime.timedelta(seconds=-1000)
        stop = datetime.timedelta(seconds=1000)
        self.assertTrue(now.within(start, stop))
        self.assertTrue(now.within(Datetime(start), Datetime(stop)))


