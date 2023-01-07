# -*- coding: utf-8 -*-
import time
from collections import defaultdict

from .compat import *
from .collections import Namespace


class Profile(Namespace):
    @property
    def elapsed(self):
        return self.get_elapsed(self.start, self.stop)

    @property
    def total(self):
        return "{:.1f} ms".format(self.elapsed)

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
            s += "> "
            ns = ns.get("child", None)

        s += self.total
        return s


class Profiler(object):
    profile_class = Profile

    def __init__(self, name=""):
        self.last = None
        self.stack = []
        self.name = name

    def __call__(self, name=""):
        pout.v("__call__")
        self.name = name
        #pout.v(name)
        #self.start(name)
        return self

    def __enter__(self):
        pout.v("__enter__")
        d = self.start(self.name)
        self.name = ""
        return d

    def __exit__(self, exception_type, exception_val, trace):
        pout.v("__exit__")
        self.stop()
#         self.stop = time.time()
#         multiplier = 1000.00
#         rnd = 2
#         self.elapsed = round(abs(self.stop - self.start) * float(multiplier), rnd)
#         self.total = "{:.1f} ms".format(self.elapsed)

    def __str__(self):
        return self.output()

    def output(self):
        return self.last.output() if self.last else ""

    def start(self, name=""):
        d = self.profile_class(
            name=name,
            start=time.time(),
        )
        self.stack.append(d)
        return d

    def stop(self):
        d = self.stack.pop(-1)
        d.stop = time.time()

        if self.stack:
            self.stack[-1].child = d

        self.last = d
        return d

# 
# 
#         if len(self.stack) > 0:
#             found = False
#             ds = []
#             for d in pr_class.stack:
#                 if self is d:
#                     found = True
#                     break
# 
#                 else:
#                     ds.append(d)
# 
#             if found and ds:
#                 name = ' > '.join((d.name for d in ds))
#                 name += ' > {}'.format(self.name)
# 
#         self.stop_call_info = call_info or self.reflect.info
#         self.name = name
#         self.stop = time.time()
#         self.elapsed = self.get_elapsed(self.start, self.stop, 1000.00, 1)
#         self.total = "{:.1f} ms".format(self.elapsed)


class AggregateProfile(Namespace):
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
    instance = None

    aprofile_class = AggregateProfile

    def __new__(cls, *args, **kwargs):
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


