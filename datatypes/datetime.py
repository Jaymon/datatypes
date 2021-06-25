# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import datetime
import inspect
import logging
import re

from .compat import *
from .string import String


logger = logging.getLogger(__name__)


class Datetime(datetime.datetime):
    """Wrapper around standard datetime.datetime class that assures UTC time and
    full ISO8601 date strings with Z timezone.

    You can create an object multiple ways:

        d = Datetime() # current utc time
        d = Datetime("2019-10-01T23:26:22.079296Z") # parses ISO8601 date from string
        d = Datetime(2019, 10, 1) # standard creation syntax

    https://docs.python.org/3/library/datetime.html#datetime-objects
    """
    FORMAT_ISO_8601 = "%Y-%m-%dT%H:%M:%S.%fZ"
    FORMAT_PRECISION_SECONDS = "%Y-%m-%dT%H:%M:%SZ"
    FORMAT_PRECISION_DAY = "%Y-%m-%d"

    @property
    def yearname(self):
        """return the full 4 digit year"""
        return self.strftime("%Y")

    @property
    def monthname(self):
        """return the full month name"""
        return self.strftime("%B")

    @property
    def dayname(self):
        """return the full day name"""
        return self.strftime("%A")

    @classmethod
    def formats(cls):
        is_valid = lambda k, v: k.startswith("FORMAT")
        formats = set(v for k, v in inspect.getmembers(cls) if is_valid(k, v))
        return formats

    @classmethod
    def parse(cls, d):
        dt = cls.parse_formats(d)

        if dt is None:
            dt = cls.parse_regex(d)

        if dt is None:
            raise ValueError("Cannot infer datetime value from {}".format(d))

        return dt

    @classmethod
    def parse_formats(cls, d):
        fs = cls.formats()
        for f in fs:
            try:
                logger.debug("Attempting to parse date: {} with format: {}".format(
                    d,
                    f,
                ))
                return cls.strptime(d, f)

            except ValueError as e:
                logger.debug(e)
                pass

    @classmethod
    def parse_regex(cls, d):
        dt = None
        if re.match(r"^\-?\d+\.\d+$", d):
            # account for unix timestamps with microseconds
            logger.debug("Date: {} parsed with integer unix timestamp regex".format(d))
            dt = cls.fromtimestamp(float(d))

        elif re.match(r"^\-?\d+$", d):
            # account for unix timestamps without microseconds
            logger.debug("Date: {} parsed with float unix timestamp regex".format(d))
            val = int(d)
            dt = cls.fromtimestamp(val)

        else:
            # ISO 8601 is not very strict with the date format and this tries to
            # capture most of that leniency, with the one exception that the
            # date must be in UTC
            # https://en.wikipedia.org/wiki/ISO_8601
            m = re.match(
                r"^(\d{4}).?(\d{2}).?(\d{2}).(\d{2}):?(\d{2}):?(\d{2})(?:\.(\d+))?Z?$",
                d
            )

            if m:
                logger.debug("Date: {} parsed with ISO regex".format(d))

                parsed_dateparts = m.groups()
                dateparts = list(map(lambda x: int(x) if x else 0, parsed_dateparts[:6]))
                dt = cls(*dateparts)

                # account for ms with leading zeros
                if parsed_dateparts[6]:
                    ms_len = len(parsed_dateparts[6])
                    if ms_len >= 3:
                        millis = parsed_dateparts[6][:3]
                        micros = parsed_dateparts[6][3:] or 0

                    else:
                        millis = parsed_dateparts[6] or 0
                        micros = 0

                    # make sure each part is 3 digits by zero padding on the right
                    if millis:
                        millis = "{:0<3.3}".format(millis)
                    if micros:
                        micros = "{:0<3.3}".format(micros)

                    dt += datetime.timedelta(
                        milliseconds=int(millis),
                        microseconds=int(micros)
                    )

        return dt

    @classmethod
    def parse_args(self, args, kwargs):
        """Parse out custom arguments so you can pass *args, **kwargs to the standard
        datetime class initializer

        :param args: tuple, the *args passed to a function
        :param kwargs: dict, the **kwargs passed to a function
        :returns: tuple, (args, kwargs, custom)
        """
        kw = {}
        for k in ["years", "months", "weeks", "days", "hours", "seconds"]:
            if k in kwargs:
                kw[k] = kwargs.pop(k)

        if args and isinstance(args[0], datetime.timedelta):
            kw["timedelta"] = args[0]
            args = args[1:]

        return args, kwargs, kw

    def __new__(cls, *args, **kwargs):
        # remove any custom keywords
        args, kwargs, kw = cls.parse_args(args, kwargs)

        if not args and not kwargs:
            instance = cls.utcnow()

        elif len(args) == 1 and not kwargs:
            if isinstance(args[0], datetime.datetime):
                instance = super(Datetime, cls).__new__(
                    cls,
                    args[0].year,
                    args[0].month,
                    args[0].day,
                    args[0].hour,
                    args[0].minute,
                    args[0].second,
                    args[0].microsecond,
                )

            elif isinstance(args[0], datetime.date):
                instance = super(Datetime, cls).__new__(
                    cls,
                    args[0].year,
                    args[0].month,
                    args[0].day,
                    0,
                    0,
                    0,
                    0,
                )

            elif isinstance(args[0], (int, float)):
                instance = cls.utcfromtimestamp(args[0])

            else:
                if args[0]:
                    try:
                        # if the object is pickled we would get the pickled string
                        # as our one passed in value
                        instance = super(Datetime, cls).__new__(cls, *args, **kwargs)

                    except TypeError:
                        fs = cls.parse(args[0])
                        if fs is None:
                            raise

                        else:
                            instance = fs

                else:
                    instance = cls.utcnow()

        else:
            instance = super(Datetime, cls).__new__(cls, *args, **kwargs)

        instance = instance.replace_timedelta(**kw)
        return instance

    def __str__(self):
        if self.has_time():
            if self.microsecond == 0:
                return self.strftime(self.FORMAT_PRECISION_SECONDS)

            else:
                return self.strftime(self.FORMAT_ISO_8601)

        else:
            return self.strftime(self.FORMAT_PRECISION_DAY)

    def __add__(self, other):
        return type(self)(super(Datetime, self).__add__(other))

    def __sub__(self, other):
        if isinstance(other, datetime.timedelta):
            return type(self)(super(Datetime, self).__sub__(other))
        else:
            return super(Datetime, self).__sub__(other)

    def __gt__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() > other
        else:
            return super(Datetime, self).__gt__(other)

    def __lt__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() < other
        else:
            return super(Datetime, self).__lt__(other)

    def __ge__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() >= other
        else:
            return super(Datetime, self).__ge__(other)

    def __le__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() <= other
        else:
            return super(Datetime, self).__le__(other)

    def __ne__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() != other
        else:
            return super(Datetime, self).__ne__(other)

    def __eq__(self, other):
        if isinstance(other, datetime.date) and not isinstance(other, datetime.datetime):
            return self.date() == other
        else:
            return super(Datetime, self).__eq__(other)

    def __hash__(self):
        # https://stackoverflow.com/questions/10254594/what-makes-a-user-defined-class-unhashable
        return super(Datetime, self).__hash__()

    def has_time(self):
        return not (
            self.hour == 0 and
            self.minute == 0 and
            self.second == 0 and 
            self.microsecond == 0
        )

    def timestamp(self):
        """
        return the current utc timestamp of self

        http://crazytechthoughts.blogspot.com/2012/02/get-current-utc-timestamp-in-python.html

        :returns: float, the current utc timestamp with microsecond precision
        """
        # this only returns second precision, which is why we don't use it
        #now = calendar.timegm(datetime.datetime.utcnow().utctimetuple())

        # this returns microsecond precision
        # http://bugs.python.org/msg180110
        epoch = datetime.datetime(1970, 1, 1)
        return (self - epoch).total_seconds()

    def iso_date(self):
        """returns datetime as ISO-8601 string with just YYYY-MM-DD"""
        return self.strftime(self.FORMAT_PRECISION_DAY)
    iso_day = iso_date
    isoday = iso_date
    isodate = iso_date

    def iso_seconds(self):
        """returns datetime as ISO-8601 string with no milliseconds"""
        return self.isoformat(timespec="seconds")
    isoseconds = iso_seconds

    def iso_8601(self):
        """returns datetime as a full ISO-8601 string with milliseconds"""
        return self.isoformat(timespec="microseconds")
    iso8691 = iso_8601

    def isofull(self):
        return self.isoformat(timespec="microseconds")

    def isoformat(self, sep="T", timespec="auto"):
        """provides python 3 compatible isoformat even for py2

        https://docs.python.org/3/library/datetime.html#datetime.datetime.isoformat

        Differences between this and builtin datetime.isoformat:

            * this will always include a timezone, defaulting to Z if no other 
            timezone is present
            * This will return YYYY-MM-DD if no time information is set and 
            timespec is "auto"

        :returns: string, the iso8604 date
        """
        add_tz = True
        if is_py2:
            if timespec == "auto":
                if self.has_time():
                    if self.microsecond == 0:
                        ret = self.strftime(self.FORMAT_PRECISION_SECONDS)

                    else:
                        ret = self.strftime(self.FORMAT_ISO_8601)

                else:
                    add_tz = False
                    ret = self.strftime(self.FORMAT_PRECISION_DAY)

            elif timespec == "hours":
                ret = self.strftime("%Y-%m-%d{}%H".format(sep))

            elif timespec == "minutes":
                ret = self.strftime("%Y-%m-%d{}%H:%M".format(sep))

            elif timespec == "seconds":
                ret = self.strftime("%Y-%m-%d{}%H:%M:%S".format(sep))

            elif timespec == "milliseconds":
                ret = self.strftime("%Y-%m-%d{}%H:%M:%S".format(sep))
                if self.microsecond == 0:
                    ret += ".000"

                else:
                    ret += ".{}".format(str(self.microsecond)[:3])

            elif timespec == "microseconds":
                ret = self.strftime("%Y-%m-%d{}%H:%M:%S.%f".format(sep))

        else:
            if timespec == "auto":
                if self.has_time():
                    ret = super(Datetime, self).isoformat(sep, timespec)
                else:
                    add_tz = False
                    ret = self.strftime(self.FORMAT_PRECISION_DAY)

            else:
                ret = super(Datetime, self).isoformat(sep, timespec)

        if add_tz and not self.tzinfo:
            if not ret.endswith("Z"):
                ret += "Z"

        return ret

    def within(self, start, stop, now=None):
        """return True if this datetime is within start and stop dates

        :param start: int|timedelta|datetime, if int, then seconds from now, so a
            negative integer would be in the past from now
        :param stop: int|timedelta|datetime, same as start
        :param now: datetime, what you want now to be
        :returns: boolean, True if self is between start and stop
        """
        if not now:
            now = type(self)()

        if isinstance(start, int):
            start = now + datetime.timedelta(seconds=start)
        start = type(self)(start)

        if isinstance(stop, int):
            stop = now + datetime.timedelta(seconds=stop)
        stop = type(self)(stop)

        return start <= self <= stop

    def strftime(self, *args, **kwargs):
        """Make sure strftime always returns a unicode object"""

        # this was moved here on 2021-5-5 from prom.config.Field.jsonable
        try:
            val = super(Datetime, self).strftime(*args, **kwargs)

        except ValueError as e:
            # strftime can fail on dates <1900
            # Note that Python 2.7, 3.0 and 3.1 have errors before the year 1900,
            # Python 3.2 has errors before the year 1000. Additionally, pre-3.2
            # versions interpret years between 0 and 99 as between 1969 and 2068.
            # Python versions from 3.3 onward support all positive years in
            # datetime (and negative years in time.strftime), and time.strftime
            # doesn't do any mapping of years between 0 and 99.
            # https://stackoverflow.com/a/32206673/5006
            logger.warning(e, exc_info=True)

            # we correct this issue by just giving it a dumb year,
            # creating the timestamp and then replacing the year, we can
            # do this semi-confidently because our format_str doesn't have
            # day of the week (eg, Monday), we account for leap years
            # just in case
            orig_year = self.year
            if (orig_year % 4) == 0:
                if (orig_year % 100) == 0:
                    if (orig_year % 400) == 0:
                        placeholder_year = 2000

                    else:
                        placeholder_year = 1900

                else:
                    placeholder_year = 2012

            else:
                placeholder_year = 1997

            dt = self.replace(year=placeholder_year)
            val = dt.strftime(*args, **kwargs)
            val = re.sub(r"^{}".format(placeholder_year), String(orig_year), val)

        return String(val)

    def replace_timedelta(self, timedelta=None, **kwargs):
        """Returns a new datetime instance with any time deltas applied

        :param timedelta: datetime.timedelta
        :param **kwargs:
            can have keyword values for months, weeks, days, hours, seconds that
            will be applied to self
        :returns: Datetime
        """
        dt = self
        if timedelta:
            dt = self + timedelta

        if "years" in kwargs:
            year = int(kwargs.pop("years"))
            dt = self.replace(self.year + year)

        if "months" in kwargs:
            months = int(kwargs.pop("months"))
            # https://stackoverflow.com/a/546354/5006
            year = self.year + (((self.month + (months - 1 if months else months)) or -1) // 12)
            month = ((self.month + months) % 12) or 12
            day = self.day - 1
            dt = self.replace(year, month, 1) + datetime.timedelta(days=day)

        if "weeks" in kwargs:
            weeks = int(kwargs.pop("weeks"))
            dt = self + datetime.timedelta(days=weeks * 7)

        if "days" in kwargs:
            days = int(kwargs.pop("days"))
            dt = self + datetime.timedelta(days=days)

        if "hours" in kwargs:
            hours = int(kwargs.pop("hours"))
            dt = self + datetime.timedelta(hours=hours)

        if "seconds" in kwargs:
            seconds = int(kwargs.pop("seconds"))
            dt = self + datetime.timedelta(seconds=seconds)

        return dt

    def replace(self, *args, **kwargs):
        """Overrides default behavior to account for custom behavior

        https://docs.python.org/3/library/datetime.html#datetime.datetime.replace
        """
        # remove any custom keywords
        args, kwargs, kw = self.parse_args(args, kwargs)
        dt = super(Datetime, self).replace(*args, **kwargs)
        return dt.replace_timedelta(**kw) if kw else dt

    def __pout__(self):
        """This just makes the object easier to digest in pout.v() calls

        more information on what pout is: https://github.com/Jaymon/pout
        """
        return self.__str__()

