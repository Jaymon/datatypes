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

    This is really more of a skeleton for the few times I've had to do this in
    a project, usually we are implementing custom functionality that acts like
    a set and so it will be nice to just be able to extend this and not have to
    worry about disabling the unsupported methods

    https://docs.python.org/3/library/stdtypes.html#set

    If you need a readonly set, use frozenset:
        https://docs.python.org/3/library/stdtypes.html#frozenset
    """
    def __init__(self, iterable=None):
        super().__init__()

        if iterable:
            self.update(iterable)

    def discard(self, elem):
        try:
            self.remove(elem)

        except KeyError:
            pass

    # def add(self, elem):
    #     super().add(elem)

    # def remove(self, elem):
    #     super().remove(elem)

    # def clear(self):
    #     super().clear()

    # def update(self, *others):
    #     for iterable in others:
    #         super().update(iterable)

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
        self.remove(elem)
        return elem


class OrderedSet(MembershipSet):
    """An ordered set (a unique list)

    This keeps the order that elements were added in, so basically it is like a
    unique list, in fact, it could totally be called UniqueList. It is similar
    to OrderedDict.keys

    https://github.com/Jaymon/datatypes/issues/34

    This implementation based on a doubly-linked list is more big-Oh efficient
    than this implementation:

        https://code.activestate.com/recipes/576694/

    This implementation has O(1) for add and contains, but O(n) for remove
    """
    def __init__(self, iterable=None):
        self.order = []
        super().__init__(iterable)

    def update(self, *others):
        for other in others:
            for elem in other:
                self.add(elem)

    def add(self, elem):
        if elem not in self:
            super().add(elem)
            self.order.append(elem)

    def remove(self, elem):
        super().remove(elem)
        self.order.remove(elem)

    def pop(self):
        """Pop from the beginning of the set (this will always pop the oldest
        item added to the set"""
        try:
            elem = self.order[0]
            self.remove(elem)
            return elem

        except IndexError as e:
            raise KeyError("pop from an empty set") from e

    def clear(self):
        self.order = []
        super().clear()

    def __iter__(self):
        """iterate through the set in add order"""
        for elem in self.order:
            yield elem

    def __reversed__(self):
        for elem in reversed(self):
            yield elem


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

