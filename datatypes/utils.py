# -*- coding: utf-8 -*-
import re
import itertools

from .compat import *


def cbany(callback, iterable):
    """Return True if any callback(row) of the iterable is true. If the iterable
    is empty, return False

    :param callback: callable
    :param iterable: Sequence
    :returns: bool
    """
    for v in iterable:
        if callback(v):
            return True
    return False


def cball(callback, iterable):
    """Return True if all elements of the iterable are true (or if the iterable
    is empty)

    :param callback: callable
    :param iterable: Sequence
    :returns: bool
    """
    for v in iterable:
        if not callback(v):
            return False
    return True


def make_list(*args):
    """make vals a list, no matter what

    Yanked from prom.utils on 6-7-2021

    :param *args: list, vals should always be a list or tuple (eg, *args passed
        as args)
    :returns: list
    """
    ret = []
    for vals in args:
        if isinstance(vals, basestring):
            ret.append(vals)

        else:
            try:
                for val in vals:
                    if isinstance(val, basestring):
                        ret.append(val)

                    elif isinstance(val, (list, tuple, Sequence, Collection)):
                        ret.extend(val)

                    else:
                        try:
                            r = list(val)
                            ret.extend(r)

                        except TypeError:
                            ret.append(val)

            except TypeError:
                # TypeError: * is not iterable
                ret.append(vals)

    return ret


def make_dict(*args):
    """Combine all key/vals in *args into one dict with later values taking
    precedence

    Yanked from prom.utils on 6-7-2021

    https://docs.python.org/3/library/stdtypes.html#dict

    :params *args: dictionaries, or tuples (key, val) or lists of tuples to be
        combined into one dictionary
    :returns: dict
    """
    ret = {}

    for d in args:
        if not d: continue

        if isinstance(d, Mapping):
            ret.update(d)

        else:
            try:
                ret.update(dict(d))
            except ValueError:
                ret.update(dict([d]))

    return ret


class Singleton(object):
    """Helper class that turns your class into a singleton where the same
    instance is always returned on each creation

    :Example:
        s = Singleton()
        s2 = Singleton()
        print(s is s2) # True
    """
    instance = None
    """The singleton class instance is stored here"""

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super().__new__(cls, *args, **kwargs)
        return cls.instance


def batched(iterable, n):
    """Batch data from the iterable into tuples of length n. The last batch may
    be shorter than n

    :Example:
        # py 3.12+
        itertools.batched('ABCDEFG', 3) --> ABC DEF G

    Copy of itertools.batched in 3.12+

    https://docs.python.org/3.12/library/itertools.html?highlight=batched#itertools.batched

    """
    # https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
    #for repeat, elem in itertools.zip_longest(*[iter(self.values)] * 2):

    if n < 1:
        raise ValueError("n must be at least one")

    it = iter(iterable)
    while batch := tuple(itertools.islice(it, n)):
        yield batch


def infer_type(v):
    """Given some value do its best to infer the type, this method is very
    conservative so if it isn't sure it will just return the original value

    :param v: Any,
    :returns: Any, for example, if v="1234" then it will return an int of 1234
    """
    ret = v

    if isinstance(v, basestring):
        if m := re.match(r"^\d+(\.\d+)?$", v):
            if m.group(1):
                ret = float(v)

            else:
                ret = int(v)

        elif v in ["True", "true"]:
            ret = True

        elif v in ["False", "false"]:
            ret = False

    elif isinstance(v, Mapping):
        ret = {}
        for k, v in v.items():
            ret[k] = infer_type(v)

    elif isinstance(v, Sequence):
        ret = []
        for item in v:
            ret.append(infer_type(item))

    return ret

