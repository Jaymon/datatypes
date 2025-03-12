# -*- coding: utf-8 -*-
"""
Container and membership like objects (eg, sets)

https://docs.python.org/3/library/collections.abc.html#collections.abc.Container
"""

from ..compat import *


class MembershipSet(set):
    """A set with all the AND, OR, and UNION operations disabled, making it
    really only handy for testing membership

    This is really more of a skeleton for the few times I've had to do this in
    a project, usually we are implementing custom functionality that acts like
    a set and so it will be nice to just be able to extend this and not have
    to worry about disabling the unsupported methods

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

    def pop(self, *args, **kwargs):
        raise NotImplementedError()

    def __sub__(self, *args, **kwargs):
        raise NotImplementedError()

    def __and__(self, *args, **kwargs):
        raise NotImplementedError()

    def __or__(self, *args, **kwargs):
        raise NotImplementedError()

    def __xor__(self, *args, **kwargs):
        raise NotImplementedError()

    def __isub__(self, *args, **kwargs):
        raise NotImplementedError()

    def __iand__(self, *args, **kwargs):
        raise NotImplementedError()

    def __ior__(self, *args, **kwargs):
        raise NotImplementedError()

    def __ixor__(self, *args, **kwargs):
        raise NotImplementedError()

    def intersection_update(self, *args, **kwargs):
        raise NotImplementedError()

    def difference_update(self, *args, **kwargs):
        raise NotImplementedError()

    def symmetric_difference_update(self, *args, **kwargs):
        raise NotImplementedError()

    def symmetric_difference(self, *args, **kwargs):
        raise NotImplementedError()

    def difference(self, *args, **kwargs):
        raise NotImplementedError()

    def intersection(self, *args, **kwargs):
        raise NotImplementedError()

    def union(self, *args, **kwargs):
        raise NotImplementedError()


class SortedSet(MembershipSet):
    """An ordered set (a unique list)

    This keeps the order that elements were added in, so basically it is like
    a unique list, in fact, it could totally be called UniqueList. It is
    similar to OrderedDict.keys

    https://github.com/Jaymon/datatypes/issues/34

    This implementation based on a doubly-linked list is more big-Oh efficient
    than this implementation:

        https://code.activestate.com/recipes/576694/

    This implementation has O(1) for add and contains, but O(n) for remove
    """
    def __init__(self, iterable=None, maxsize=None):
        self.order = []

        self.maxsize = maxsize if (maxsize and maxsize > 0) else None

        super().__init__(iterable)

    def update(self, *others):
        for other in others:
            for elem in other:
                self.add(elem)

    def add(self, elem):
        if elem not in self:
            super().add(elem)
            self.order.append(elem)
            self.added(elem)

    def added(self, elem):
        """Called after elem is added to the set

        This is handy if you want to do some post added manipulation of
        the set

        :param x: Any, the object added to the set
        """
        if self.maxsize:
            if len(self) > self.maxsize:
                # elem wasn't in the set and we are now over max capacity so
                # eject the oldest element
                self.pop()

    def remove(self, elem):
        super().remove(elem)
        self.order.remove(elem)

    def pop(self):
        """Pop from the beginning of the set (this will always pop the oldest
        item added to the set"""
        try:
            elem = self.order.pop(0)
            super().remove(elem)
            return elem

        except IndexError as e:
            raise KeyError("pop from an empty set") from e

    def clear(self):
        self.order = []
        super().clear()

    def __iter__(self):
        """iterate through the set in add order"""
        yield from self.order

    def __reversed__(self):
        yield from reversed(self)

    def full(self):
        """
        https://docs.python.org/3/library/queue.html#queue.Queue.full
        """
        return len(self) == self.maxsize

    def empty(self):
        """
        https://docs.python.org/3/library/queue.html#queue.Queue.empty
        """
        return len(self) == 0


class HotSet(SortedSet):
    """Holds maxsize unique elems and keeps it at that size, discarding
    the oldest elem when a new elem is added once maxsize is reached"""
    def __init__(self, maxsize=0):
        super().__init__(maxsize=maxsize)

    def add(self, elem):
        if elem in self:
            # elem is already in the list but we're going to refresh its
            # ordering since elem has just been "touched"
            self.order.remove(elem)
            self.order.append(elem)

        else:
            super().add(elem)


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

