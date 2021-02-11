# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import


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

