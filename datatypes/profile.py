# -*- coding: utf-8 -*-
import time
from collections import defaultdict

from .compat import *
from .collections import Namespace


class Profile(Namespace):
    """This is the context object that is returned from the Profiler, it's main
    purpose is to allow printing of one atomic profiling session"""
    @property
    def elapsed(self):
        return self.get_elapsed(self.start, self.stop)

    @property
    def total(self):
        s = ""
        seconds = self.stop - self.start
        if seconds > 60:
            rundown = self.rundown
            if hours := rundown["hours"]:
                s += f"{hours}h"

            if mins := rundown["minutes"]:
                s += f"{mins}m"

            if seconds := rundown["seconds"]:
                s += f"{seconds}s"

            if ms := rundown["ms"]:
                s += f"{ms}ms"

            s = s.strip()

        else:
            s = "{:.1f} ms".format(self.elapsed)

        return s

    @property
    def rundown(self):
        """Breaks down start and stop into hours, minutes, seconds, and ms"""
        elapsed = self.stop - self.start
        hours = minutes = seconds = 0
        if elapsed > 60:
            minutes = int(elapsed // 60)
            seconds = int(elapsed - (minutes * 60))

        if minutes > 60:
            hours = int(minutes // 60)
            minutes = int(minutes - (hours * 60))


        ms = elapsed - (minutes * 60) - seconds
        ms = int(ms * 1000.0) // 10

        return {
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "ms": ms,
        }

    def get_elapsed(self, start, stop, multiplier=1000, rnd=2):
        return round(abs(stop - start) * float(multiplier), rnd)

    def __str__(self):
        return self.output()

    def output(self):
        s = ""
        ns = self
        while ns:
            name = ns.get("name", "")
            if name:
                s += name + " "

            if s:
                s += "> "
            ns = ns.get("child", None)

        s += self.total
        return s


class Profiler(object):
    """Allows you to profile some code.

    The best way to profile would be to use the with functionality, but you can
    .start() and .stop() a profiling session also

    :Example:
        # you can use an existing Profiler instance and pass a name
        p = Profiler()
        with p("<SESSION NAME>"):
            pass
        print(p)

        # you can give a name when creating the profiler in a with statement
        with Profiler("<SESSION NAME>) as p:
            pass
        print(p)

        # you don't have to give a name
        with p:
            pass
        print(p)

    This was moved from bang.utils.Profile on 1-6-2023, then it was
    updated/combined with pout.value.P
    """
    profile_class = Profile
    """The class that is used to track the actual profiling. An instance of this
    class is returned from the context manager"""

    @classmethod
    def get_output(cls, start, stop, **kwargs):
        """A quick way to get a nicely formatted elapsed time string

        Because sometimes I don't need the full functionality of the Profiler, I
        just need a nicely formatted elapsed time string

        :param start: float
        :param stop: float
        :returns: str, a formatted output total elapsed time string
        """
        p = cls.profile_class(start=start, stop=stop)
        return p.total

    def __init__(self, name="", logmethod=None):
        self.last = None
        self.stack = []
        self.name = name
        self.logmethod = logmethod

    def __call__(self, name="", logmethod=None):
        """Allows you to set a name when using the context manager on an existing
        instance. This must return self or the context manager won't run"""
        self.name = name
        if logmethod:
            self.logmethod = logmethod
        return self

    def __enter__(self):
        """Allows with statement support"""
        d = self.start(self.name)
        self.name = ""
        return d

    def __exit__(self, exception_type, exception_val, trace):
        self.stop()
        if self.logmethod:
            self.logmethod(self)

    def __str__(self):
        return self.output()

    def output(self):
        return self.last.output() if self.last else ""

    def start(self, name=""):
        """Start a profiling session

        :param name: str, the name of the session
        :returns: self.profile_class instance
        """
        d = self.profile_class(
            name=name,
            start=time.time(),
        )
        self.stack.append(d)
        return d

    def stop(self):
        """Stops a profiling session, this will error out if start hasn't been
        called previously

        :returns: self.profile_class instance that has the full session information
        """
        d = self.stack.pop(-1)
        d.stop = time.time()

        if self.stack:
            self.stack[-1].child = d

        self.last = d
        return d


class AggregateProfile(Namespace):
    """Used by the Agg profiler to record information for all sessions with the
    same name"""
    @property
    def total(self):
        return "{:.1f} ms".format(self.elapsed)

    @property
    def average(self):
        avg = self.elapsed / self.count
        return "{:.1f} ms".format(avg)

    def __init__(self):
        super().__init__(count=0, elapsed=0.0)

    def output(self):
        return f"{self.name} ran {self.count} times for a total of {self.total} ({self.average} avg)"


class AggregateProfiler(Profiler):
    """A singleton profiler that will keep totals of all the profile sessions
    that have been started so you can see sums and totals of all the profiling
    you did"""
    instance = None
    """Holds the singleton, see __new__"""

    aprofile_class = AggregateProfile

    def __new__(cls, *args, **kwargs):
        """Tricksy implementation that always returns cls.instance if it exists"""
        if cls.instance:
            cls.instance(*args, **kwargs)
        else:
            cls.instance = super().__new__(cls, *args, **kwargs)
        return cls.instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.profiles = defaultdict(self.aprofile_class)

    def stop(self):
        d = super().stop()

        self.profiles[d.name].count += 1
        self.profiles[d.name].name = d.name
        self.profiles[d.name].elapsed += d.elapsed

        return d

    def output(self):
        lines = ["Profiling: "]
        for d in self.profiles.values():
            lines.append(f" * {d.output()}")
        return "\n".join(lines)

