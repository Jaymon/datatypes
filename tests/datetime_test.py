# -*- coding: utf-8 -*-
import pickle
import datetime
import time

from datatypes.compat import *
from datatypes.datetime import (
    Datetime,
    ISO8601,
)
from datatypes.string import String

from . import TestCase, testdata


class ISO8601Test(TestCase):
    def test_year_month(self):
        d = ISO8601("2024-12")
        self.assertEqual(2024, d.year)
        self.assertEqual(12, d.month)

        d = ISO8601("2024")
        self.assertEqual(2024, d.year)

    def test_tzoffset_1(self):
        d = ISO8601("2011-11-04T00:05:23+00")
        self.assertEqual(2011, d.year)
        self.assertEqual(0, d.hour)
        self.assertEqual(None, d.microsecond)
        self.assertEqual("UTC", d.tzinfo.tzname(None))

    def test_tzoffset_2(self):
        d = ISO8601("2011-11-04T01:30+05")
        td = d.tzinfo.utcoffset(None)
        self.assertEqual(-1, td.days)
        self.assertEqual(68400, td.seconds)

    def test_datetimetuple(self):
        d = ISO8601("2019-11-05T23:35:04Z")
        t = d.datetimetuple()
        self.assertEqual(0, t[6])
        self.assertEqual("UTC", t[7].tzname(None))

        d = ISO8601("2011-11-04T00:05:23+00")
        t = d.datetimetuple()
        self.assertEqual(8, len(t))
        self.assertEqual(0, t[3])
        self.assertEqual(0, t[6])


class DatetimeTest(TestCase):
    def test_datetime(self):
        d = Datetime()
        d2 = d.datetime()
        self.assertEqual(d, d2)

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

    def test_has_time(self):
        d = Datetime(2019, 11, 5)
        self.assertFalse(d.has_time())

        d = Datetime()
        self.assertTrue(d.has_time())

    def test_create_1(self):
        d1 = Datetime.utcnow()
        self.assertTrue(isinstance(d1, Datetime))

        d2 = Datetime()

        self.assertEqual(d1.isoseconds(), d2.isoseconds())

        d3 = Datetime(2018, 10, 5)
        d4 = Datetime(String(d3))
        self.assertEqual(d3.isoseconds(), d4.isoseconds())

    def test_create_precision(self):
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

    def test_timestamp_1(self):
        d = Datetime()
        ts = d.timestamp()
        self.assertTrue(isinstance(ts, float))

        d2 = Datetime(ts)
        self.assertEqual(d, d2)

        d3 = Datetime(int(ts))
        self.assertEqual(d.isoseconds(), d3.isoseconds())

    def test_timestamp_2(self):
        epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        td = datetime.datetime.now(datetime.timezone.utc) - epoch
        timestamp = td.total_seconds()

        dt = Datetime(timestamp)
        self.assertEqual(timestamp, dt.timestamp())

        dt = Datetime(String(timestamp))
        self.assertEqual(timestamp, dt.timestamp())

        utc = dt.datetime()
        self.assertEqual(utc, dt)

    def test_timestamp_3(self):
        with self.assertRaises(ValueError):
            dt = Datetime(10775199116899)

        with self.assertRaises(ValueError):
            dt = Datetime(-62167219200)

    def test_strings(self):
        d = Datetime(2018, 10, 5, 23, 35, 4)
        self.assertEqual("2018-10-05", d.isodate())
        self.assertEqual("2018-10-05T23:35:04Z", d.isoseconds())

    def test___str__(self):
        ss = [
            "2019-11-05",
            "2019-11-05T23:35:04Z",
            "2019-11-05T23:35:04.546123Z",
        ]

        for s in ss:
            d = Datetime(s)
            self.assertEqual(s, str(d))

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
        self.assertEqual(
            "2020-03-25T19:34:05.000050Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.05Z"
        dt = Datetime(s)
        self.assertEqual(50000, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.050000Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.0506Z"
        dt = Datetime(s)
        self.assertEqual(50600, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.050600Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.050060Z"
        dt = Datetime(s)
        self.assertEqual(50060, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.050060Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.000057Z"
        dt = Datetime(s)
        self.assertEqual(57, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.000057Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.057Z"
        dt = Datetime(s)
        self.assertEqual(57000, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.057000Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-25T19:34:05.057035Z"
        dt = Datetime(s)
        self.assertEqual(57035, dt.microsecond)
        self.assertEqual(
            "2020-03-25T19:34:05.057035Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

        s = "2020-03-19 00:00:00.000000000"
        dt = Datetime(s)
        self.assertEqual(
            "2020-03-19T00:00:00.000000Z",
            dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        )

    def test_within(self):
        now = Datetime()

        self.assertTrue(now.within(-10000, 10000))
        self.assertFalse(now.within(-10000, -50000))

        start = datetime.timedelta(seconds=-1000)
        stop = datetime.timedelta(seconds=1000)
        self.assertTrue(now.within(start, stop))
        self.assertTrue(now.within(Datetime(start), Datetime(stop)))

    def test_timezone_from_naive(self):
        d = datetime.datetime.now()
        d2 = Datetime(d)
        self.assertEqual(d.astimezone(datetime.timezone.utc), d2)

    def test_timezone_formats(self):
        d = Datetime('2019-10-08 20:18:59.')
        self.assertEqual('2019-10-08T20:18:59Z', d.isoformat())

        d = Datetime('2011-11-04T00:05:23+00')
        self.assertEqual('2011-11-04T00:05:23Z', d.isoformat())

        d = Datetime('2011-11-04')
        self.assertEqual('2011-11-04', d.isoformat())

        d = Datetime('2011-11-04T01Z')
        self.assertEqual('2011-11-04T01:00:00Z', d.isoformat())

        d = Datetime('2011-11-04T01:30+05')
        self.assertEqual('2011-11-03T20:30:00Z', d.isoformat())

        d = Datetime('2011-11-04T01+05')
        self.assertEqual('2011-11-03T20:00:00Z', d.isoformat())

        d = Datetime('2011-11-04T01')
        self.assertEqual('2011-11-04T01:00:00Z', d.isoformat())

        d = Datetime('2011-11-04T00:05:23.601')
        self.assertEqual('2011-11-04T00:05:23.601000Z', d.isoformat())

        d = Datetime('2011-11-04T00:05:23.601-04:00')
        self.assertEqual('2011-11-04T04:05:23.601000Z', d.isoformat())

        d = Datetime('2011-11-04T00:05:23.601Z')
        self.assertEqual('2011-11-04T00:05:23.601000Z', d.isoformat())

    def test_timezone_all(self):
        d = Datetime(2021, 8, 16)
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(2021, 8, 30, weeks=-2)
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime()
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(None)
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime("")
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(datetime.datetime.now())
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(datetime.datetime.now().date())
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(int(Datetime().timestamp()))
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime(Datetime().timestamp())
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

        d = Datetime('2011-11-04T00:05:23Z')
        self.assertEqual(datetime.timezone.utc, d.tzinfo)

    def test_time_ns(self):
        ts = time.time_ns()
        d = Datetime(ts)
        self.assertEqual(ts, d.timestamp_ns())

    def test_datehash(self):
        d1 = Datetime(microsecond=0)
        h = d1.datehash()
        self.assertIsInstance(h, str)

        d2 = Datetime.fromdatehash(h)
        self.assertEqual(d1, d2)

    def test_since_1(self):
        now = Datetime(month=8, day=1, year=2023)

        d = Datetime(now, months=-24)
        self.assertEqual(
            "1 year, 23 months, 4 weeks, 3 days",
            d.since(now, chunks=0)
        )

        d = Datetime(now, seconds=-30)
        self.assertEqual("30 seconds", d.since(now))

        d = Datetime(now, months=-5, days=-3)
        self.assertEqual("5 months, 3 days", d.since(now))

        d = Datetime(now, months=-5, days=-10)
        self.assertEqual("5 months, 1 week", d.since(now))

        now = Datetime(month=8, day=1, year=2023)

        d = Datetime(now, months=-24, hours=12, minutes=30, seconds=14)
        self.assertEqual(
            "1 year, 23 months, 4 weeks, 2 days, 11 hours, 29 minutes, 46 seconds",
            d.since(now, chunks=0)
        )

    def test_estsince(self):
        now = Datetime(month=8, day=1, year=2023)

        d = Datetime(now, months=-5, days=-3)
        self.assertEqual("5 months, 6 days", d.estsince(now))

        d = Datetime(now, seconds=-30)
        self.assertEqual("30 seconds", d.estsince(now))

        d = Datetime(now, months=-5, days=-10)
        self.assertEqual("5 months, 1 week", d.estsince(now))

    def test_now(self):
        d = Datetime()
        d2 = Datetime.now()
        self.assertEqual(d.tzinfo, d2.tzinfo)

        d3 = Datetime.utcnow()
        self.assertEqual(d.tzinfo, d3.tzinfo)

    def test_next_month(self):
        d = Datetime(2023, 12, 1)
        d2 = d.next_month()
        self.assertEqual(2024, d2.year)
        self.assertEqual(1, d2.month)
        self.assertEqual(1, d2.day)

        d = Datetime(2023, 8, 1)
        d2 = d.next_month()
        self.assertEqual(2023, d2.year)
        self.assertEqual(9, d2.month)
        self.assertEqual(1, d2.day)

    def test_current_month(self):
        d = Datetime(2023, 8, 10)
        d2 = d.current_month()
        self.assertEqual(2023, d2.year)
        self.assertEqual(8, d2.month)
        self.assertEqual(1, d2.day)

    def test_prev_month(self):
        d = Datetime(2023, 1, 10)
        d2 = d.prev_month()
        self.assertEqual(2022, d2.year)
        self.assertEqual(12, d2.month)
        self.assertEqual(1, d2.day)

        d = Datetime(2023, 8, 1)
        d2 = d.prev_month()
        self.assertEqual(2023, d2.year)
        self.assertEqual(7, d2.month)
        self.assertEqual(1, d2.day)

    def test_months_1(self):
        d = Datetime()

        count = len(list(d.months(d)))
        self.assertEqual(1, count)

        count = len(list(d.months(d, inclusive=False)))
        self.assertEqual(0, count)

    def test_months_2(self):
        d = Datetime(month=1, year=2023)
        now = Datetime(month=8, year=2023)

        count = len(list(d.months(now, inclusive=False)))
        self.assertEqual(6, count)

        count = 0
        for month in d.months(now):
            count += 1
        self.assertEqual(8, count)

    def test___add__(self):
        d = Datetime()

        d2 = d + 1000
        td = d2 - d
        self.assertEqual(1000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(0, td.microseconds)

        d2 = d + 2000.345
        td = d2 - d
        self.assertEqual(2000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(345000, td.microseconds)

        d2 = d + datetime.timedelta(seconds=3000)
        td = d2 - d
        self.assertEqual(3000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(0, td.microseconds)

    def test___iadd__(self):
        d = Datetime()
        d2 = d.replace() # clone d so we have something to compare

        d2 += 1000
        td = d2 - d
        self.assertEqual(1000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(0, td.microseconds)

    def test___sub__(self):
        d = Datetime()

        d2 = d - 1000
        td = d - d2
        self.assertEqual(1000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(0, td.microseconds)

        d2 = d - 2000.345
        td = d - d2
        self.assertEqual(1999, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(655000, td.microseconds)

        d2 = d - datetime.timedelta(seconds=3000)
        td = d - d2
        self.assertEqual(3000, td.seconds)
        self.assertEqual(0, td.days)
        self.assertEqual(0, td.microseconds)

    def test_parse_subseconds(self):
        #parts is: ms, us, mstr, ustr
        parts = Datetime.parse_subseconds("123456")
        self.assertEqual(123, parts[0])
        self.assertEqual(456, parts[1])

        parts = Datetime.parse_subseconds("0205")
        self.assertEqual(20, parts[0])
        self.assertEqual(500, parts[1])

        parts = Datetime.parse_subseconds("00005")
        self.assertEqual(0, parts[0])
        self.assertEqual(50, parts[1])

    def test_plus(self):
        ttl = 1000
        d1 = Datetime(datetime.timedelta(seconds=ttl)).isoseconds()

        now = Datetime()
        d2 = Datetime(now, seconds=ttl).isoseconds()

        d3 = Datetime(None, seconds=ttl).isoseconds()

        self.assertTrue(d1 == d2 == d3)

    def test_iso_methods(self):
        d = Datetime()
        day = d.isodate()[:-1]

        hour = d.isohours()[:-1]
        self.assertTrue(hour.startswith(day))

        minute = d.isominutes()[:-1]
        self.assertTrue(minute.startswith(day))

        seconds = d.isoseconds()[:-1]
        self.assertTrue(seconds.startswith(minute))

        mseconds = d.isomilliseconds()[:-1]
        self.assertTrue(mseconds.startswith(seconds))

        useconds = d.isomicroseconds()[:-1]
        self.assertTrue(useconds.startswith(mseconds))

    def test___init___keywords(self):
        pt = 0x7FFFFFFF + 20
        td = datetime.timedelta(seconds=pt)
        dt1 = datetime.datetime(year=1904, month=1, day=1) + td
        dt2 = Datetime(year=1904, month=1, day=1, seconds=pt)
        dt3 = Datetime(year=1904, month=1, day=1) + td
        self.assertTrue(dt1.date() == dt2.date() == dt3.date())
        self.assertEqual(dt1, dt2.datetime().replace(tzinfo=None))

    def test_itermonthdays(self):
        for total, dt in enumerate(Datetime.itermonthdays(2025, 10), 1):
            self.assertTrue(1 <= dt.day <= 31)

        self.assertEqual(31, total)

    def test_iteryeardays(self):
        for total, dt in enumerate(Datetime.iteryeardays(2025), 1):
            self.assertTrue(1 <= dt.month <= 12)
            self.assertTrue(1 <= dt.day <= 31)

        self.assertEqual(365, total)

    def test_iterdays(self):
        for total, dt in enumerate(Datetime.iterdays(2025, week=2), 1):
            if total == 1:
                self.assertEqual("2025-01-06", str(dt))

            if total == 7:
                self.assertEqual("2025-01-12", str(dt))

        self.assertEqual(7, total)

        self.assertEqual(31, len([dt for dt in Datetime.iterdays(2025, 10)]))
        self.assertEqual(365, len([dt for dt in Datetime.iterdays(2025)]))

    def test_week_1(self):
        dt = Datetime(2025, 1, 1, 0, 0, 0, week=1)
        self.assertEqual("2024-12-30", str(dt))

        dt = Datetime(2025, 1, 1, 0, 0, 0, week=2)
        self.assertEqual("2025-01-06", str(dt))

    def test_iso8601_date_init(self):
        ds = "2025-11-25"
        dt = Datetime(ds)
        self.assertEqual(ds, str(dt))
        self.assertEqual(ds, str(dt.date()))

