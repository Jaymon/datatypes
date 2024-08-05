# -*- coding: utf-8 -*-
import datetime
import inspect
import logging
import re
import time
import math
import calendar

from .compat import *
from .string import String


logger = logging.getLogger(__name__)


class Datetime(datetime.datetime):
    """Wrapper around standard datetime.datetime class that assures UTC time and
    full ISO8601 date strings with Z timezone.

    You can create an object multiple ways:

        d = Datetime() # current utc time
        d = Datetime("2019-10-01T23:26:22.079296Z") # parses ISO8601 date
        d = Datetime(2019, 10, 1) # standard creation syntax

    https://docs.python.org/3/library/datetime.html#datetime-objects
    """
    FORMAT_ISO8601_DAY = "%Y-%m-%d"
    FORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S.%f"
    FORMAT_ISO8601_TZ = "%Y-%m-%dT%H:%M:%S.%f%Z"
    FORMAT_ISO8601_SECONDS = "%Y-%m-%dT%H:%M:%S"
    FORMAT_ISO8601_SECONDS_TZ = "%Y-%m-%dT%H:%M:%S%Z"

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
                logger.debug(
                    "Attempting to parse date: {} with format: {}".format(
                        d,
                        f,
                    )
                )

                ret = cls.strptime(d, f)
                if ("%z" in f) or ("%Z" in f):
                    ret = ret.astimezone(datetime.timezone.utc)

                else:
                    ret = ret.replace(tzinfo=datetime.timezone.utc)

                logger.debug(f"Date: {d} parsed with format: {f}")
                return ret

            except ValueError as e:
                logger.debug(e)
                pass

    @classmethod
    def parse_regex(cls, d):
        dt = None
        if re.match(r"^\-?\d+\.\d+$", d):
            # account for unix timestamps with microseconds
            logger.debug(
                "Date: {} parsed with float unix timestamp regex".format(
                    d
                )
            )
            dt = cls.fromtimestamp(float(d), tz=datetime.timezone.utc)

        elif re.match(r"^\-?\d+$", d):
            # account for unix timestamps without microseconds
            logger.debug(
                "Date: {} parsed with integer unix timestamp regex".format(
                    d
                )
            )
            val = int(d)
            dt = cls.fromtimestamp(val, tz=datetime.timezone.utc)

        else:
            # in 3.11+ we can maybe replace this with:
            #    https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
            #
            # ISO 8601 is not very strict with the date format and this tries to
            # capture most of that leniency, with the one exception that the
            # date must be in UTC
            # https://en.wikipedia.org/wiki/ISO_8601
            m = re.match(
                r"""
                    ^               # match from the beginning of the string
                    (\d{4})         # 0 - YYYY (year)
                    .?              # deliminator
                    (\d{2})         # 1 - MM (month)
                    .?              # deliminator
                    (\d{2})         # 2 - DD (day)
                    .               # Date and time separator (usually T)
                    (\d{2})         # 3 - HH (hour)
                    (?::?(\d{2}))?  # 4 - MM (minute)
                    (?::?(\d{2}))?  # 5 - SS (second)
                    (?:\.(\d+))?    # 6 - MS (milliseconds)
                """,
                d,
                flags=re.X
            )

            if m:
                logger.debug("Date: {} parsed with ISO regex".format(d))

                parsed_dateparts = m.groups()
                dateparts = list(map(
                    lambda x: int(x) if x else 0, parsed_dateparts[:6]
                ))
                dt = cls(*dateparts, tzinfo=datetime.timezone.utc)

                # account for ms with leading zeros
                if parsed_dateparts[6]:
                    millis, micros, _, _ = cls.parse_subseconds(
                        parsed_dateparts[6]
                    )
                    dt += datetime.timedelta(
                        milliseconds=millis,
                        microseconds=micros
                    )

                tzoffset = d[m.regs[m.lastindex][1]:]
                if tzoffset:
                    # https://en.wikipedia.org/wiki/ISO_8601#Time_zone_designators
                    if tzoffset != "Z":
                        moffset = re.match(
                            r"""
                                ([+-])         # 1 - positive or negative offset
                                (\d{2})        # 2 - HH (hour)
                                (?::?(\d{2}))? # 3 - MM (minute)
                                $
                            """,
                            tzoffset,
                            flags=re.X
                        )

                        if moffset:
                            sign = moffset.group(1)
                            seconds = 0
                            if hours := moffset.group(2):
                                seconds += int(hours) * 3600

                            if minutes := moffset.group(3):
                                seconds += int(minutes) * 60

                            if seconds:
                                if sign == "+":
                                    dt -= datetime.timedelta(seconds=seconds)

                                else:
                                    dt += datetime.timedelta(seconds=seconds)

        return dt

    @classmethod
    def parse_args(self, args, kwargs):
        """Parse out custom arguments so you can pass *args, **kwargs to the
        standard datetime class initializer

        :param args: tuple, the *args passed to a function
        :param kwargs: dict, the **kwargs passed to a function
        :returns: tuple, (args, kwargs, custom)
        """
        timedelta_kwargs = {}
        replace_kwargs = {}

        timedelta_names = {
            "years": ["years", "yrs"],
            "months": ["months"],
            "weeks": ["weeks", "week"],
            "days": ["days"],
            "hours": ["hours"],
            "minutes": ["minutes", "mins"],
            "seconds": ["seconds", "secs"],
            "microseconds": ["microseconds", "usecs"],
            "milliseconds": ["milliseconds", "msecs"],
        }
        for nk, ks in timedelta_names.items():
            for k in ks:
                if k in kwargs:
                    timedelta_kwargs.setdefault(nk, 0)
                    timedelta_kwargs[nk] += kwargs.pop(k)

        if timedelta := kwargs.pop("timedelta", None):
            timedelta_kwargs["timedelta"] = timedelta

        if args and isinstance(args[0], datetime.timedelta):
            if "timedelta" in timedelta_kwargs:
                timedelta_kwargs["timedelta"] += args[0]

            else:
                timedelta_kwargs["timedelta"] = args[0]

            args = args[1:]

        replace_names = {
            "year": ["year", "yr", "y", "Y"],
            "month": ["month", "m"],
            "day": ["day", "d"],
            "hour": ["hour", "hr", "H"],
            "minute": ["minute", "min", "M"],
            "second": ["second", "sec", "S"],
            "microsecond": ["microsecond", "us", "usec"],
            "millisecond": ["millisecond", "ms", "msec"],
        }
        for nk, ks in replace_names.items():
            for k in ks:
                if k in kwargs:
                    replace_kwargs.setdefault(nk, 0)
                    replace_kwargs[nk] += kwargs.pop(k)

        if len(args) < 8:
            replace_kwargs.setdefault(
                "tzinfo",
                kwargs.pop("tzinfo", datetime.timezone.utc)
            )

        else:
            if tzinfo := kwargs.pop("tzinfo", None):
                replace_kwargs["tzinfo"] = tzinfo

        if not args and "now" in kwargs:
            args = [kwargs.pop("now")]

        return args, replace_kwargs, timedelta_kwargs

    @classmethod
    def parse_subseconds(cls, subseconds):
        r"""Parse the value to the right of the period on a floating point number

        123456
        \ /\ /
         |  |
         | microseconds
         |
        milliseconds

        :Example:
            ms, us, mstr, ustr = cls.parse_subseconds(012345)
            print(ms) # 12
            print(us) # 345
            print(mstr) # "012"
            print(ustr) # "345"

        :param subseconds: int|str, usually a 6-digit integer but can be a six
            digit string
        :returns tuple[int, int, str, str]
        """
        subseconds = str(subseconds)
        ms_len = len(subseconds)
        if ms_len >= 3:
            millis = subseconds[:3]
            micros = subseconds[3:] or 0

        else:
            millis = subseconds or 0
            micros = 0

        # make sure each part is 3 digits by zero padding on the right
        millis_str = millis.ljust(3, "0") if millis else "000"
        micros_str = micros.ljust(3, "0") if micros else "000"

        #millis_str = "{:0<3.3}".format(millis) if millis else "000"
        #micros_str = "{:0<3.3}".format(micros) if micros else "000"

        return int(millis_str), int(micros_str), millis_str, micros_str

    @classmethod
    def parse_seconds(cls, seconds):
        """Parse seconds into seconds, milliseconds, and microseconds

        :Example:
            s, ms, us, sstr, mstr, ustr = cls.parse_seconds(123456789.012345)
            print(s) # 123456789
            print(ms) # 12
            print(us) # 345
            print(sstr) # "123456789"
            print(mstr) # "012"
            print(ustr) # # "000345"

        :param seconds: int|str, the seconds with possible milliseconds and
            microseconds
        :returns tuple[int, int, int, str, str, str]
        """
        sstr = str(seconds)

        parts = sstr.split(".")
        s = parts[0]
        ms = 0
        if len(parts) > 1:
            ms = parts[1]

        msecs, usecs, mstr, ustr = cls.parse_subseconds(ms)
        return int(s), msecs, usecs, s, mstr, ustr

    def __new__(cls, *args, **kwargs):
        # remove any custom keywords
        args, replace_kwargs, timedelta_kwargs = cls.parse_args(args, kwargs)

        if not args:
            instance = cls.now(datetime.timezone.utc)

        elif len(args) == 1:
            if isinstance(args[0], datetime.datetime):
                dt = args[0].astimezone(datetime.timezone.utc)
                instance = super().__new__(
                    cls,
                    dt.year,
                    dt.month,
                    dt.day,
                    dt.hour,
                    dt.minute,
                    dt.second,
                    dt.microsecond,
                    tzinfo=dt.tzinfo,
                )

            elif isinstance(args[0], datetime.date):
                instance = super().__new__(
                    cls,
                    args[0].year,
                    args[0].month,
                    args[0].day,
                    0,
                    0,
                    0,
                    0,
                    tzinfo=datetime.timezone.utc,
                )

            elif isinstance(args[0], (int, float)):
                try:
                    instance = cls.fromtimestamp(
                        args[0],
                        tz=datetime.timezone.utc
                    )

                except ValueError as e:
                    raise ValueError(
                        f"timestamp {args[0]} is out of bounds"
                    ) from e

                except OSError:
                    if isinstance(args[0], int):
                        # We convert a really big int into seconds and
                        # milliseconds values. We use a time.time() to figure
                        # out how big the milliseconds part should be, so
                        # 1706726703601782 would become 1706726703 seconds and
                        # 3601782 milliseconds
                        timestamp = str(args[0])
                        s, ms = str(time.time()).split(".")

                        seconds = timestamp[:len(s)]
                        milliseconds = timestamp[len(s):]
                        instance = cls.fromtimestamp(
                            float(f"{seconds}.{milliseconds}"),
                            tz=datetime.timezone.utc
                        )

                    else:
                        raise

            else:
                if args[0]:
                    try:
                        # if the object is pickled we would get the pickled
                        # string as our one passed in value
                        instance = super().__new__(cls, *args)

                    except TypeError:
                        fs = cls.parse(args[0])
                        if fs is None:
                            raise

                        else:
                            instance = fs

                else:
                    instance = cls.now(datetime.timezone.utc)

        else:
            instance = super().__new__(cls, *args, **replace_kwargs)
            replace_kwargs = {} # we've consumed them

        #instance = instance.replace_timedelta(**kw)
        if replace_kwargs or timedelta_kwargs:
            instance = instance.replace(**replace_kwargs, **timedelta_kwargs)

        return instance

    def __str__(self):
        return self.isoformat()

    def __add__(self, other):
        if isinstance(other, (int, float)):
            seconds, msecs, usecs, *_ = self.parse_seconds(other)
            td = datetime.timedelta(
                seconds=seconds,
                milliseconds=msecs,
                microseconds=usecs
            )

            return super().__add__(td)

        else:
            return super().__add__(other)

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return self.__add__(-other)

        else:
            return super().__sub__(other)

    def __eq__(self, other):
        """We define this method so we can do some custom comparing

        We define all the other sub methods (eg, __lt__, __ne__) so that they
        will use this custom __eq__ method

        https://docs.python.org/3/reference/datamodel.html#object.__eq__

        :param other: datetime|int|float|str
        :returns: bool, True if other is equivalent, False otherwise
        """
        if (
            isinstance(other, datetime.date)
            and not isinstance(other, datetime.datetime)
        ):
            return self.date() == other

        elif isinstance(other, (int, float, str)):
            return self == type(self)(other)

        else:
            return super().__eq__(other.astimezone(self.tzinfo))

    def __lt__(self, other):
        if (
            isinstance(other, datetime.date)
            and not isinstance(other, datetime.datetime)
        ):
            return self.date() < other

        else:
            return super().__lt__(other.astimezone(self.tzinfo))

    def __gt__(self, other):
        return not self.__lt__(other) and not self.__eq__(other)

    def __ge__(self, other):
        return not self.__lt__(other) or self.__eq__(other)

    def __le__(self, other):
        return self.__lt__(other) or self.__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """In order to make an instance of this class hashable this method has
        to be defined, we can't rely on the parent's __hash__ method because we
        defined a custom __eq__ method I guess

        https://docs.python.org/3/reference/datamodel.html#object.__hash__
        https://stackoverflow.com/questions/10254594/
        """
        return super().__hash__()

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
        epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
        return (self - epoch).total_seconds()

    def timestamp_ns(self):
        """Similar to .timestamp() but returns time as an integer number of
        nanoseconds since the epoch

        see time.time_ns()

        :returns: int
        """
        size = len(str(time.time_ns()))
        timestamp = str(self.timestamp()).replace(".", "")
        return int("{{:0<{}}}".format(size).format(timestamp))

    def since(self, now=None, chunks=2):
        """Returns a description of the amount of time that has passed from self
        to now. This is more exact than .estsince() but does a lot more
        computation to make it accurate

        :param now: datetime, if None will default to the current datetime
        :param chunks: int, if a postive value only that many chunks will be
            returned, if None or -1 then all found chunks will be returned
        :returns: str, the elapsed time in english (eg, x years, xx months, or 
            x days, xx hours)
        """
        output = []

        # time period chunks that aren't variable
        period_chunks = [
            (60 * 60 * 24 * 7, 'week', 'weeks'),
            (60 * 60 * 24 , 'day', 'days'),
            (60 * 60 , 'hour', 'hours'),
            (60 , 'minute', 'minutes'),
            (1 , 'second', 'seconds'),
        ]

        # now will equal None if we want to know the time elapsed between self
        # and the current time, otherwise it will be between self and now
        if not chunks or chunks < 0:
            chunks = len(period_chunks) + 2

        now = Datetime(now)
        months = 0
        month_days = 0
        for month in self.months(now, inclusive=False):
            months += 1
            month_days += month.days_in_month()

        if months:
            years = months // 12
            if years:
                name = "year" if years == 1 else "years"
                output.append(f"{years} {name}")
                chunks -= 1

            if chunks > 0:
                name = "month" if months == 1 else "months"
                output.append(f"{months} {name}")
                chunks -= 1

        # difference in seconds
        since = (now - self).total_seconds()
        since -= (period_chunks[1][0] * month_days)

        for seconds, name, names in period_chunks:
            if count := math.floor(since / seconds):
                output.append(
                    f"1 {name}" if count == 1 else f"{count} {names}"
                )
                since -= (seconds * count)
                chunks -= 1
                if since <= 0 or chunks <= 0:
                    break

        return ", ".join(output) if output else ""

    def estsince(self, now=None, chunks=2):
        """Returns a ballpark/estimate description of the amount of time that
        has passed from self to now

        This is based on Plancast's Formatting.php timeSince method

        NOTE -- this can drift since it uses 30 days for the months, you can
        see this by doing:

            d = Datetime(months=-5, days=-3)
            d.since(now=Datetime(month=8, day=1, year=2023)) # 5 months, 6 days

        :param now: datetime, if None will default to the current datetime
        :param chunks: int, if a postive value only that many chunks will be
            returned, if None or -1 then all found chunks will be returned
        :returns: str, the elapsed time in english (eg, x years, xx months, or 
            x days, xx hours)
        """
        output = []

        # time period chunks
        period_chunks = [
            (60 * 60 * 24 * 365 , 'year', 'years'),
            (60 * 60 * 24 * 30 , 'month', 'months'),
            (60 * 60 * 24 * 7, 'week', 'weeks'),
            (60 * 60 * 24 , 'day', 'days'),
            (60 * 60 , 'hour', 'hours'),
            (60 , 'minute', 'minutes'),
            (1 , 'second', 'seconds'),
        ]

        # now will equal None if we want to know the time elapsed between self
        # and the current time, otherwise it will be between self and now
        now = now or self.now(self.tzinfo)
        if not chunks or chunks < 0:
            chunks = len(period_chunks)

        # difference in seconds
        since = (now - self).total_seconds()

        for seconds, name, names in period_chunks:
            if count := math.floor(since / seconds):
                output.append(
                    f"1 {name}" if count == 1 else f"{count} {names}"
                )
                since -= (seconds * count)
                chunks -= 1
                if since <= 0 or chunks <= 0:
                    break

        return ", ".join(output) if output else ""
    def esince(self, *args, **kwargs):
        return self.estsince(*args, **kwargs)

    def datehash(self):
        """Return a datehash, kind of similar to a geohash where each character
        represents a more exact time

        This is something I've noodled on since Plancast days, and I wanted to
        finally have a canonical place where I could mess with it and track
        changes

        :returns: str, A 7 character string, with indexes that represent:
            0,1 - the year
            2 - month
            3 - day
            4 - hour
            5 - minute
            6 - second
        """
        h = ""
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

        # year
        h += chars[self.year // 100]
        h += chars[self.year % 100]

        # month
        h += chars[self.month]

        # day
        h += chars[self.day]

        if self.has_time():
            h += chars[self.hour]
            h += chars[self.minute]
            h += chars[self.second]

        return h

    @classmethod
    def fromdatehash(cls, h):
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        indexes = {v:k for k, v in enumerate(chars)}

        year = int(str(indexes[h[0]]) + str(indexes[h[1]]))
        month = indexes[h[2]]
        day = indexes[h[3]]

        hour = minute = second = 0
        if len(h) >= 4:
            hour = indexes[h[4]]

            if len(h) >= 5:
                minute = indexes[h[5]]

                if len(h) >= 6:
                    second = indexes[h[6]]

        return cls(year, month, day, hour, minute, second)

    @classmethod
    def now(cls, tz=datetime.timezone.utc):
        """Passthrough but sets timezone to utc by default instead of None, so
        by default this now returns a timezone aware instance

        https://docs.python.org/3/library/datetime.html#datetime.datetime.now
        """
        return super().now(tz)

    @classmethod
    def utcnow(cls):
        """Overrides parent to return a timezone aware datetime instance with
        the timezone UTC set

        https://docs.python.org/3/library/datetime.html#datetime.datetime.utcnow
        """
        return cls.now(datetime.timezone.utc)

    def isodate(self):
        """returns datetime as ISO-8601 string with just YYYY-MM-DD"""
        return self.strftime(self.FORMAT_ISO8601_DAY)
    iso_day = isodate
    isoday = isodate
    iso_date = isodate

    def isoseconds(self):
        """returns datetime as ISO-8601 string with no milliseconds"""
        return self.isoformat(timespec="seconds")
    iso_seconds = isoseconds
    isosecond = isoseconds
    iso_second = isoseconds

    def isohours(self):
        """returns datetime as ISO-8601 string up to the hour"""
        return self.isoformat(timespec="hours")
    iso_hours = isohours
    isohour = isohours
    iso_hour = isohours

    def isominutes(self):
        """returns datetime as ISO-8601 string up to the minute"""
        return self.isoformat(timespec="minutes")
    iso_minutes = isominutes
    isominute = isominutes
    iso_minute = isominutes

    def isomilliseconds(self):
        """returns datetime as ISO-8601 string up to the milliseconds (.SSS)
        """
        return self.isoformat(timespec="milliseconds")

    def isomicroseconds(self):
        """returns datetime as ISO-8601 string up to the microseconds (.SSSSSS)
        """
        return self.isoformat(timespec="microseconds")

    def iso8601(self):
        """returns datetime as a full ISO-8601 string with milliseconds"""
        return self.isoformat(timespec="microseconds")
    iso_8601 = iso8601

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

        :returns: string, the iso8601 date
        """
        if self.has_time():
            if self.utcoffset():
                ret = super().isoformat(sep, timespec)

            else:
                ret = self.datetime().replace(tzinfo=None).isoformat(
                    sep,
                    timespec
                )
                ret += "Z"

        else:
            if timespec == "auto":
                ret = self.date().isoformat()

            else:
                ret = self.datetime().replace(tzinfo=None).isoformat(
                    sep,
                    timespec
                )
                ret += "Z"

        return ret

    def within(self, start, stop, now=None):
        """return True if this datetime is within start and stop dates

        :param start: int|timedelta|datetime, if int, then seconds from now, so
            a negative integer would be in the past from now
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
            # Note that Python 2.7, 3.0 and 3.1 have errors before the year
            # 1900, Python 3.2 has errors before the year 1000. Additionally,
            # pre-3.2 versions interpret years between 0 and 99 as between 1969
            # and 2068.  Python versions from 3.3 onward support all positive
            # years in datetime (and negative years in time.strftime), and
            # time.strftime doesn't do any mapping of years between 0 and 99.
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
            val = re.sub(
                r"^{}".format(placeholder_year),
                String(orig_year),
                val
            )

        return String(val)

    def replace(self, *args, **kwargs):
        """Overrides default behavior to account for custom behavior

        https://docs.python.org/3/library/datetime.html#datetime.datetime.replace

        Returns a new datetime instance with any time deltas applied

        :param timedelta: datetime.timedelta
        :param **kwargs: besides the standard keywords, this can also have
            keyword values for: months, weeks, days, hours, seconds, and
            timedelta
        :returns: Datetime
        """
        args, replace_kwargs, timedelta_kwargs = self.parse_args(args, kwargs)

        if replace_kwargs:
            dt = super().replace(*args, **replace_kwargs)

        else:
            dt = super().replace(*args)

        if timedelta := timedelta_kwargs.pop("timedelta", None):
            dt = dt + timedelta

        if timedelta_kwargs:
            if "years" in timedelta_kwargs:
                year = int(timedelta_kwargs.pop("years"))
                dt = dt.replace(self.year + year)

            if "months" in timedelta_kwargs:
                months = int(timedelta_kwargs.pop("months"))
                # https://stackoverflow.com/a/546354/5006
                year = self.year + (
                    (
                        (
                            self.month + (months - 1 if months else months)
                        ) or -1
                    ) // 12
                )
                month = ((self.month + months) % 12) or 12
                day = self.day - 1
                dt = dt.replace(year, month, 1) + datetime.timedelta(days=day)

            dt += datetime.timedelta(**timedelta_kwargs)

        return dt

    def datetime(self):
        """Similar to .date() but returns vanilla datetime instance"""
        return datetime.datetime(
            self.year,
            self.month,
            self.day,
            self.hour,
            self.minute,
            self.second,
            self.microsecond,
            tzinfo=self.tzinfo,
        )

    def days_in_month(self):
        """Return how many days there are in self.month

        Months with 28 or 20 days:
            * February

        Months with 30 days:
            * April
            * June
            * September
            * November

        Months with 31 days:
            * January
            * March
            * May
            * July
            * August
            * October
            * December
        """
        _, monthlen = calendar.monthrange(self.year, self.month)
        return monthlen

    def next_month(self):
        """Returns the first day of the next month from self"""
        month = self.month
        year = self.year
        if month == 12:
            month = 1
            year += 1

        else:
            month += 1

        return Datetime(year, month, 1)

    def prev_month(self):
        """Returns the first day of the previous month from self"""
        month = self.month
        year = self.year
        if month == 1:
            month = 12
            year -= 1

        else:
            month -= 1

        return Datetime(year, month, 1)

    def current_month(self):
        """Returns the first day of the current month from self"""
        return Datetime(self.year, self.month, 1)

    def months(self, now=None, inclusive=True):
        """Returns all the months between self and now

        :param now: datetime, if None then defaults to now
        :param inclusive: bool, by default, if self was Jan and now was Aug and
            you iterated through the months it would be: Jan, Feb, Mar, Apr, May
            June, July, Aug, because it includes the edges. If inclusive is 
            False then it would be: Feb, Mar, Apr, May, june, July
        :returns: generator[datetime], each datetime instance will be midnight
            on the first day of that month
        """
        now = Datetime(now)
        month = self.current_month() if inclusive else self.next_month()
        now_month = now.current_month() if inclusive else now.prev_month()

        if month >= now_month:
            if inclusive:
                yield self.current_month()

        else:
            while month < now_month:
                yield month
                month = month.next_month()

            yield month

