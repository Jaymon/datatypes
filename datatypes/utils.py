# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

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

    :param *args: list, vals should always be a list or tuple (eg, *args passed as args)
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

                    elif isinstance(val, (list, tuple)):
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
    """Combine all key/vals in *args into one dict with later values taking precedence

    Yanked from prom.utils on 6-7-2021

    https://docs.python.org/3/library/stdtypes.html#dict

    :params *args: dictionaries, or tuples (key, val) or lists of tuples to be
        combined into one dictionary
    :returns: dict
    """
    ret = {}

    for d in args:
        if isinstance(d, Mapping):
            ret.update(d)

        else:
            try:
                ret.update(dict(d))
            except ValueError:
                ret.update(dict([d]))

    return ret


