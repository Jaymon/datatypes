# -*- coding: utf-8 -*-
import re
from configparser import RawConfigParser
import math

from .compat import *
from .string import String


class Shorten(object):
    """Converts an integer to a base58-like string and vice versa

    This code was used in Undrip for its link shortener and was originally
    written by Cahlan Sharp and Ryan Johnson (I believe) and based off of this:

        https://stackoverflow.com/a/2549514/5006

    any ambiguous characters were removed from BASE_LIST (notice no I, 1, or l)
    to make it easier for humans to copy the url by hand

    this is a version of base58 that takes strings:
        https://github.com/keis/base58
    """
    BASE_LIST = (
        "23456789"
        "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
        "_-"
    )
    BASE_DICT = dict((c, i) for i, c in enumerate(BASE_LIST))

    def __new__(cls, val):
        if isinstance(val, basestring):
            ret = cls.decode(val)

        elif isinstance(val, int):
            ret = cls.encode(val)

        else:
            raise TypeError("Unknown type {}".format(type(val)))

        return ret

    @classmethod
    def encode(cls, integer, encoding="", baselist=None):
        base = cls.BASE_LIST
        length = len(base)
        ret = ''
        while integer != 0:
            ret = base[integer % length] + ret
            integer //= length
        return String(ret)

    @classmethod
    def decode(cls, s, encoding="", basedict=None):
        reverse_base = cls.BASE_DICT
        length = len(reverse_base)
        ret = 0
        for i, c in enumerate(s[::-1]):
            ret += (length ** i) * reverse_base[c]
        return ret


class Integer(int):
    def hex(self, length=0, prefix=""):
        if length:
            format_str = "{}{{:0>{}X}}".format(prefix, length)

        else:
            format_str = "{}{{:X}}".format(prefix)

        return format_str.format(self)

    def binary(self, length=0, prefix=""):
        if length:
            format_str = "{}{{:0>{}b}}".format(prefix, length)

        else:
            format_str = "{}{{:b}}".format(prefix)

        return format_str.format(self)

    def range(self, start=0):
        """iterate from 0 to self, if self is negative it goes from self to 0

        I honestly have no idea why this is useful but it was in my notes for
        this module, so here it is
        """
        if self > start:
            r = range(0, self)
        else:
            r = range(self, start)

        for i in r:
            yield i

    def __new__(cls, v, base=None):
        if not isinstance(v, int):
            if isinstance(v, str):
                sub = True
                if base is None:
                    # NOTE: if you have an ambiguous value like "0001" or
                    # "0010" this will assume it is binary
                    if (
                        re.match(r"^[-+]?0b", v)
                        or re.search(r"^[-+]?[01]+$", v)
                    ):
                        # https://stackoverflow.com/questions/8928240/convert-base-2-binary-number-string-to-int
                        base = 2
                        sub = False

                    elif (
                        re.match(r"^[-+]?0x", v)
                        or (
                            re.search(r"[a-fA-F]", v)
                            and re.search(r"[a-fA-F0-9]+$", v)
                        )
                    ):
                        base = 16
                        sub = False

                    else:
                        base = 10

                else:
                    if base != 10:
                        sub = False

                if sub:
                    subs = [
                        (" ", ""),
                        (",", ""),
                        ("K", "000"),
                        ("k", "000"),
                        ("mn", "000000"),
                        ("M", "000000"),
                        ("m", "000000"),
                        ("bn", "000000000"),
                        ("B", "000000000"),
                        ("b", "000000000"),
                    ]
                    for s in subs:
                        v = v.replace(s[0], s[1])

            try:
                v = int(v, base)

            except TypeError:
                if len(v) == 1:
                    v = ord(v)

                else:
                    raise

        return super().__new__(cls, v)


class Hex(Integer):
    def __new__(cls, v):
        return super().__new__(cls, v, 16)


class Binary(Integer):
    def __new__(cls, v):
        return super().__new__(cls, v, 2)


class Exponential(object):
    """Model exponential growth or decay over a period

    https://math.libretexts.org/Bookshelves/Applied_Mathematics/Applied_Finite_Mathematics_(Sekhon_and_Bloom)/05%3A_Exponential_and_Logarithmic_Functions/5.02%3A_Exponential_Growth_and_Decay_Models
    https://en.wikipedia.org/wiki/Exponential_decay
    """
    def __init__(self, initial, rate):
        """
        :param initial: int|float, the initial value
        :param rate: int|float, the growth rate, if an integer this will be
            converted to a float (eg, 10 would be converted to 0.1)
        """
        self.initial = initial

        if isinstance(rate, int):
            self.rate = rate / 100
        else:
            self.rate = rate

    def growth(self, period):
        """Model exponential growth over period

        :param period: int, how many periods you want to model initial and rate
        :returns: list, the values for each period
        """
        ret = []
        rate = 1.0 + self.rate
        for i in range(period):
            ret.append(self.initial * pow(rate, i))

        return ret

    def decay(self, period):
        """Model exponential decay over period

        :param period: int, how many periods you want to model initial and rate
        :returns: list, the values for each period
        """
        ret = []
        rate = 1.0 - self.rate
        for i in range(period):
            ret.append(self.initial * pow(rate, i))

        return ret


class BooleanMeta(type):
    """This class enables Boolean to quack like a boolean

    Sadly, no matter how hard I try, I don't think it is possible to get
    Boolean to pass `issubclass(Boolean, bool)` because the python C
    implementation of `issubclass` uses ->tp_mro which is what is used to
    originally set the .__mro__ attribute, but that means you can't override
    the functionality anywhere in actual python

    This metaclass isn't strictly necessary, I just find it kind of
    interesting
    """
    @property
    def __base__(self):
        return bool

    @property
    def __bases__(self):
        return (bool,) + bool.__bases__

    @property
    def __mro__(self):
        return (Boolean,) + bool.__mro__


class Boolean(int, metaclass=BooleanMeta):
    """A casting class that allows for more values to be considered True or
    False

    This differs from a normal bool(x) cast in that:

        * Any int/float > 0 will be True and any int/float <= 0 will be False,
            so negative values are False
        * Yes/no, on/off, and things like that evaluate to True/False, see

            https://github.com/python/cpython/blob/3.11/Lib/configparser.py

            RawConfigParser.BOOLEAN_STATES for what string values are True and
            False
        * A string of all whitespace is False

    This isn't a real class but is more akin to a method, the __new__ method
    returns a builtin bool instance because bool can't be subclassed:

        https://stackoverflow.com/questions/2172189/why-i-cant-extend-bool-in-python
    """
    @classmethod
    def isbool(cls, v):
        """Return True if v is considered a valid boolean-ish value"""
        try:
            cls.getbool(v)
            return True

        except TypeError:
            return False

    @classmethod
    def getbool(cls, v):
        """Try and convert v to a bool value, raise TypeError on failure"""
        if not isinstance(v, bool):
            if isinstance(v, (int, float)):
                v = True if v > 0 else False

            elif isinstance(v, str):
                k = v.lower()
                if k in RawConfigParser.BOOLEAN_STATES:
                    v = RawConfigParser.BOOLEAN_STATES[k]

                else:
                    if k.isdigit():
                        v = True if int(v) > 0 else False

                    else:
                        if k == "t":
                            v = True

                        elif k == "f":
                            v = False

                        else:
                            raise TypeError(f"{k} is not a bool")

        return v

    def __new__(cls, v):
        try:
            v = cls.getbool(v)

        except TypeError:
            if isinstance(v, str):
                v = True if v.strip() else False

            else:
                raise

        return bool(v)


class Partitions(Sequence):
    """Partition funciton. Generate all the partitions for pass in n

    https://en.wikipedia.org/wiki/Partition_function_(number_theory)
    via https://www.reddit.com/r/maths/comments/1h0lssh/comment/lz5bkxv/

    All of these algorithms come from here:
        https://stackoverflow.com/questions/10035752/elegant-python-code-for-integer-partitioning
        https://code.activestate.com/recipes/218332-generator-for-integer-partitions/
        https://jeromekelleher.net/generating-integer-partitions.html

    Which I found while trying to convert the math in the wikipedia article
    into actual code (which I failed at which is why I was trying to find
    some examples)

    References:
        https://mathworld.wolfram.com/PartitionFunctionP.html
        https://mathoverflow.net/questions/47611/exact-formulas-for-the-partition-function

    Related:
        https://docs.python.org/3/library/itertools.html#itertools.permutations
        https://www.reddit.com/r/math/comments/11t6l6y/breakthrough_in_ramsey_theory_the_longstanding/
    """
    def __init__(self, n):
        if n < 0:
            raise ValueError(f"{n=} which is less than zero")

        self.n = n

    def __getitem__(self, index):
        raise NotImplementedError()

    def __len__(self):
        if self.n < 2:
            return 1

        else:
            return len([_ for _ in self])

    def __iter__(self):
        yield from self.ap()

    def lower_bound(self):
        """There are guarranteed to be more partitions than this bound

        via: https://math.stackexchange.com/a/4852015
        """
        one = math.exp(math.pi * math.sqrt((2 * self.n) / 3))
        two = 4 * self.n * math.sqrt(3)
        three = 1 - (1 / (2 * math.sqrt(self.n)))
        return int((one / two) * three)

    def upper_bound(self):
        """There are guarranteed to be less partitions than this bound

        via:
            * https://math.stackexchange.com/a/4852015
            * https://math.stackexchange.com/a/4752148
            * Ramanujan's upper bound for number of partitions of n:
                https://code.activestate.com/recipes/218332-generator-for-integer-partitions/#c2
        """
        one = math.exp(math.pi * math.sqrt((2 * self.n) / 3))
        two = 4 * self.n * math.sqrt(3)
        three = 1 - (1 / (3 * math.sqrt(self.n)))
        return int((one / two) * three)

    def ap(self):
        """Generate partitions of .n as ordered lists in ascending
        lexicographical order.

        This highly efficient routine is based on the delightful
        work of Kelleher and O'Sullivan.

        .. Example:

            >>> for i in aP(6): i
            ...
            [1, 1, 1, 1, 1, 1]
            [1, 1, 1, 1, 2]
            [1, 1, 1, 3]
            [1, 1, 2, 2]
            [1, 1, 4]
            [1, 2, 3]
            [1, 5]
            [2, 2, 2]
            [2, 4]
            [3, 3]
            [6]

            >>> for i in aP(0): i
            ...
            []

        References
        ----------

        .. [1] Generating Integer Partitions, [online],
            Available: http://jeromekelleher.net/generating-integer-partitions.html
        .. [2] Jerome Kelleher and Barry O'Sullivan, "Generating All
            Partitions: A Comparison Of Two Encodings", [online],
            Available: http://arxiv.org/pdf/0909.2331v2.pdf
        ..  [3] via: https://code.activestate.com/recipes/218332-generator-for-integer-partitions/#c9

        :returns: Generator[list[int]]
        """
        # The list `a`'s leading elements contain the partition in which
        # y is the biggest element and x is either the same as y or the
        # 2nd largest element; v and w are adjacent element indices
        # to which x and y are being assigned, respectively.
        n = self.n
        a = [1]*n
        y = -1
        v = n
        while v > 0:
            v -= 1
            x = a[v] + 1
            while y >= 2 * x:
                a[v] = x
                y -= x
                v += 1
            w = v + 1
            while x <= y:
                a[v] = x
                a[w] = y
                yield a[:w + 1]
                x += 1
                y -= 1
            a[v] = x + y
            y = a[v] - 1
            yield a[:w]

    def accel_asc(self):
        """This is the default fast method that .ap takes inspiration from

        https://jeromekelleher.net/generating-integer-partitions.html

        :returns: Generator[list[int]]
        """
        n = self.n
        a = [0 for i in range(n + 1)]
        k = 1
        y = n - 1
        while k != 0:
            x = a[k - 1] + 1
            k -= 1
            while 2 * x <= y:
                a[k] = x
                y -= x
                k += 1
            l = k + 1
            while x <= y:
                a[k] = x
                a[l] = y
                yield a[:k + 2]
                x += 1
                y -= 1
            a[k] = x + y
            y = x + y - 1
            yield a[:k + 1]

    def kpartitions(self, k=None):
        """Generate all partitions of integer n (>= 0) using integers no
        greater than k (default, None, allows the partition to contain n).

        Each partition is represented as a multiset, i.e. a dictionary
        mapping an integer to the number of copies of that integer in
        the partition.  For example, the partitions of 4 are {4: 1},
        {3: 1, 1: 1}, {2: 2}, {2: 1, 1: 2}, and {1: 4} corresponding to
        [4], [1, 3], [2, 2], [1, 1, 2] and [1, 1, 1, 1], respectively.
        In general, sum(k * v for k, v in a_partition.iteritems()) == n, and
        len(a_partition) is never larger than about sqrt(2*n).

        Note that the _same_ dictionary object is returned each time.
        This is for speed:  generating each partition goes quickly,
        taking constant time independent of n. If you want to build a list
        of returned values then use .copy() to get copies of the returned
        values:

        >>> p_all = []
        >>> for p in partitions(6, 2):
        ...     p_all.append(p.copy())
        ...
        >>> print(p_all)
        [{2: 3}, {1: 2, 2: 2}, {1: 4, 2: 1}, {1: 6}]

        Reference
        ---------

        Modified from Tim Peter's posting to accomodate a k value:
        http://code.activestate.com/recipes/218332/

        via: https://code.activestate.com/recipes/218332-generator-for-integer-partitions/#c7
        via: https://code.activestate.com/recipes/218332-generator-for-integer-partitions/#c5

        :param k: int, the upper bound value that values in the partition can't
            be greater than
        :returns: Generator[dict[int, int]], where the keys are the integer and
            the values are the number of times the integer/key appears in the
            partition
        """
        n = self.n
        if n == 0:
            yield {}
            return

        if k is None or k > n:
            k = n

        q, r = divmod(n, k)
        ms = {k : q}
        keys = [k]
        if r:
            ms[r] = 1
            keys.append(r)
        yield ms

        while keys != [1]:
            # Reuse any 1's.
            if keys[-1] == 1:
                del keys[-1]
                reuse = ms.pop(1)
            else:
                reuse = 0

            # Let i be the smallest key larger than 1.  Reuse one
            # instance of i.
            i = keys[-1]
            newcount = ms[i] = ms[i] - 1
            reuse += i
            if newcount == 0:
                del keys[-1], ms[i]

            # Break the remainder into pieces of size i-1.
            i -= 1
            q, r = divmod(reuse, i)
            ms[i] = q
            keys.append(i)
            if r:
                ms[r] = 1
                keys.append(r)

            yield ms

    def perm(k=None):
        """Wrapper around math.perm

        https://docs.python.org/3/library/math.html#math.perm
        """
        return math.perm(self.n, k)

    def strict(self):
        """Yield all the strict partitions where there are no repeating
        numbers

        https://en.wikipedia.org/wiki/Partition_function_(number_theory)#Strict_partition_function
            A partition in which no part occurs more than once is called
            strict, or is said to be a partition into distinct parts. The
            function q(n) gives the number of these strict partitions of the
            given sum n. For example, q(3) = 2 because the partitions 3 and 1 +
            2 are strict, while the third partition 1 + 1 + 1 of 3 has repeated
            parts

        :returns: Generator[list[int]]
        """
        for p in self.kpartitions():
            rp = []
            for n, count in p.items():
                if count > 1:
                    break

                rp.append(n)

            else:
                # only yield if the for loop completely finished
                yield rp

