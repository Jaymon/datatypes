# -*- coding: utf-8 -*-
"""
Container and membership like objects (eg, sets)

https://docs.python.org/3/library/collections.abc.html#collections.abc.Container
"""

from ..compat import *

from .sequence import PriorityQueue


class MembershipSet(set):
    """A set with all the AND, OR, and UNION operations disabled, making it
    really only handy for testing membership

    This is really more of a skeleton for the few times I've had to do this in a
    project, usually we are implementing custom functionality that acts like a
    set and so it will be nice to just be able to extend this and not have to
    worry about disabling the unsupported methods

    If you need a readonly set, use frozenset:
        https://docs.python.org/3/library/stdtypes.html#frozenset
    """
    def __init__(self, iterable=None):
        if not iterable:
            iterable = []

        super(MembershipSet, self).__init__(iterable)

    def add(self, elem):
        super(MembershipSet, self).add(perm)

    def remove(self, elem):
        super(MembershipSet, self).remove(perm)

    def discard(self, elem):
        try:
            self.remove(elem)
        except KeyError:
            pass

    def clear(self):
        super(MembershipSet, self).clear()

    def update(self, *others):
        for iterable in others:
            super(MembershipSet, self).update(iterable)

    def noimp(self, *args, **kwargs):
        raise NotImplementedError()

    pop = noimp
    __sub__ = noimp
    __and__ = noimp
    __or__ = noimp
    __xor__ = noimp
    __isub__ = noimp
    __iand__ = noimp
    __ior__ = noimp
    __ixor__ = noimp
    intersection_update = noimp
    difference_update = noimp
    symmetric_difference_update = noimp
    symmetric_difference = noimp
    difference = noimp
    intersection = noimp
    union = noimp = noimp


class HotSet(MembershipSet):
    """Similar to Pool, this holds maxsize elems and keeps it at that size"""
    def __init__(self, maxsize=0):
        super().__init__()
        self.pq = PriorityQueue(maxsize, key=lambda value: value)

    def add(self, elem):
        super().add(elem)
        try:
            self.pq.put(elem)

        except OverflowError:
            self.pop()
            self.pq.put(elem)

    def remove(self, elem):
        if elem in self:
            self.pq.remove(elem)
        super().remove(elem)

    def clear(self):
        self.pq.clear()
        super().clear()

    def update(self, *others):
        for iterable in others:
            for elem in iterable:
                self.add(elem)

    def pop(self):
        elem = self.pq.get()
        self.discard(elem)
        return elem


class Trie(object):
    """https://en.wikipedia.org/wiki/Trie"""
    def __init__(self, *values):
        self.values = {}

        for value in values:
            self.add(value)

    def add(self, value):
        if value:
            ch = value[0]
            remainder = value[1:]
            if ch not in self.values:
                self.values[ch] = None

            if remainder:
                if self.values[ch] is None:
                    self.values[ch] = type(self)(remainder)

                else:
                    self.values[ch].add(self.normalize_value(remainder))

    def has(self, value):
        ret = True
        ch = self.normalize_value(value[0])
        remainder = value[1:]
        if ch in self.values:
            if remainder:
                if self.values[ch] is None:
                    ret = False
                else:
                    ret = self.values[ch].has(remainder)

        else:
            ret = False

        #pout.v(ch, ret, self.values.keys())
        return ret

    def __contains__(self, value):
        return self.has(value)

    def normalize_value(self, value):
        return value.lower()

