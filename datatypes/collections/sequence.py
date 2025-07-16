# -*- coding: utf-8 -*-
"""
List like objects

https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence
"""
import bisect

from ..compat import *


# class FrozenList(list): # a read only list that can only be set via constructor


class AppendList(list):
    """A READ ONLY list that does all adding of items through the append method
    To customize this list just extend the append() method

    https://docs.python.org/3/tutorial/datastructures.html#more-on-lists
    """
    def __init__(self, iterable=None):
        """
        https://docs.python.org/3/library/stdtypes.html?highlight=list#list
        """
        super().__init__()

        if iterable:
            self.extend(iterable)

    def append(self, x):
        return super().append(x)

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def pop(self, i):
        raise NotImplementedError()
    def insert(self, i, x):
        raise NotImplementedError()
    def __setitem__(self, i, x):
        raise NotImplementedError()
    def __delitem__(self, i):
        raise NotImplementedError()
    def remove(self, x):
        raise NotImplementedError()


class SortedList(list):
    """Keep a list sorted as you append or extend it

    A sorted list, this sorts items from smallest to largest using key, so
    if you want MaxQueue like functionality use negative values: .pop(-1) and
    if you want MinQueue like functionality use positive values: .pop(0)

    :Example:
        # max sorted list
        sl = SortedList(key=lambda x: -x, maxsize=3)
        sl.extend([5, 10, 1, 4, 16, 20, 25])
        print(sl) # [25, 20, 16]

    https://docs.python.org/3/tutorial/datastructures.html#more-on-lists
    """
    def __init__(self, iterable=None, key=None, maxsize=None):
        """
        :param iterable: Sequence, the initial values
        :param key: Callable[[Any], Any], this takes in the item and returns
            the value used for sorting
        :param maxsize: int, the maximum number of items the list can have
        """
        if key:
            self.key = key

        self.maxsize = maxsize if (maxsize and maxsize > 0) else None

        super().__init__()
        if iterable:
            for x in iterable:
                self.append(x)

    def key(self, x):
        """Returns the key that will be used to order x

        You can override this method to customize ordering

        :param x: Any, the object being inserted
        :returns: str|int|Any, the hashable object that will be used for
            ordering
        """
        return x

    def inserted(self, i, x):
        """Called after x is inserted at position i

        This is handy if you want to do some post insertion manipulation of
        the list

        :param i: int, the position x was inserted in the list, will be None
            if x was inserted at the end of the list
        :param x: Any, the object inserted into the list
        """
        if self.maxsize:
            if len(self) > self.maxsize:
                self.pop(-1)

    def append(self, x):
        # https://docs.python.org/3/library/bisect.html#bisect.bisect_right
        i = bisect.bisect_right(self, self.key(x), key=self.key)
        if i is None:
            super().append(x)

        else:
            super().insert(i, x)

        self.inserted(i, x)

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def __reversed__(self):
        index = len(self)
        while index > 0:
            index -= 1
            yield self[index]

    def insert(self, i, x):
        raise NotImplementedError()
    def __setitem__(self, i, x):
        raise NotImplementedError()
    def reverse(self):
        raise NotImplementedError()
    def sort(self):
        raise NotImplementedError()

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


class Stack(list):
    """An incredibly simple stack implementation"""
    def push(self, v):
        self.append(v)

    def pop(self):
        return super().pop(-1)

    def peek(self):
        return self[-1]

    def __iter__(self):
        """By default stacks are LIFO"""
        for i in reversed(range(0, len(self))):
            yield self[i]

    def __reversed__(self):
        """calling reverse on a stack would switch to normal list FIFO"""
        return super().__iter__()

    def insert(self, i, x):
        raise NotImplementedError()
    def __setitem__(self, i, x):
        raise NotImplementedError()
    def __delitem__(self, i):
        raise NotImplementedError()
    def reverse(self):
        raise NotImplementedError()
    def sort(self):
        raise NotImplementedError()
    def remove(self, x):
        raise NotImplementedError()


class ListIterator(list):
    """A base interface for iterators that should quack like a builtin list

    it defines the list interface as much as possible

    Taken from prom.query.BaseIterator on 12-15-2020

    list interface methods:
        https://docs.python.org/3/tutorial/datastructures.html#more-on-lists

    http://docs.python.org/2/library/stdtypes.html#iterator-types
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __next__(self):
        """needed for py3 api compatibility"""
        return self.next()

    def __iter__(self):
        return self

    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        for _ in self:
            return True
        return False

    def __len__(self):
        return self.count()

    def __deepcopy__(self, *args, **kwargs):
        return self.copy()

    def __getslice__(self, i, j):
        """required for slicing in python 2 when extending built-in types like list

        https://docs.python.org/2/reference/datamodel.html#object.__getslice__
        https://stackoverflow.com/questions/2936863/implementing-slicing-in-getitem#comment39878974_2936876
        """
        return self.__getitem__(slice(i, j))

    def __reversed__(self):
        it = self.copy()
        it.reverse()
        return it

    def __iter__(self):
        return self

    def __getitem__(self, i):
        if isinstance(i, slice):
            return self.get_slice(i)

        else:
            return self.get_index(i)

    def get_slice(self, s):
        """s is a slice object

        * s.start - lower bound
        * s.stop - uppder bound
        * s.step - step value

        Any property of the slice instance can be None:

        * [:N:N] - start is None
        * [N:] - stop and step are None
        * [:N] - start and step are None
        * [N:N] - step is None
        * [N::N] - stop and step are None

        slice objects are described here: https://docs.python.org/3/reference/datamodel.html
        under section 3.2 in the "slice objects" section
        """
        raise NotImplementedError()

    def get_index(self, i):
        raise NotImplementedError()

    def next(self):
        raise NotImplementedError()

    def count(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def reverse(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def sort(self, *args, **kwargs):
        """list interface compatibility"""
        raise NotImplementedError()

    def copy(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def index(self, x, start=None, end=None):
        """list interface compatibility"""
        raise NotImplementedError()

    def append(self, x):
        """list interface compatibility"""
        raise NotImplementedError()

    def extend(self, iterable):
        """list interface compatibility"""
        raise NotImplementedError()

    def remove(self, x):
        """list interface compatibility"""
        raise NotImplementedError()

    def pop(self, i=-1):
        """list interface compatibility"""
        raise NotImplementedError()

    def clear(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def insert(self, i, x):
        """list interface compatibility"""
        raise NotImplementedError()

