# -*- coding: utf-8 -*-
"""
List like objects

https://docs.python.org/3/library/collections.abc.html#collections.abc.Sequence
"""
import heapq
import itertools
import bisect

from ..compat import *


class PriorityQueue(object):
    """A generic priority queue

    if passing in a tuple (priority, value) then...

        * MinQueue: priority=lambda x: x[0]
        * MaxQueue: priority=lambda x: -x[0]

    Inspiration:

        * https://stackoverflow.com/a/3311765/5006
        * https://docs.python.org/2/library/heapq.html#priority-queue-implementation-notes

    https://en.wikipedia.org/wiki/Priority_queue

    :Example:
        # MinQueue example
        pq = PriorityQueue(priority=lambda x: x[0])
        pq.put((30, "che"))
        pq.put((1, "foo"))
        pq.put((4, "bar"))
        pq.get() # (1, "foo")

    This uses .put() and .get() because that is the same interface as Python's built-in
    queue class.

    If you never pass in priorities it defaults to a FIFO queue, this allows you
    to pass in keys to .put() to set uniqueness and move items back to the top of
    the queue if they have the same key, another name for this might be RefreshQueue
    since a value with the same key will move to the bottom of the queue
    """
    def __init__(self, maxsize=0, key=None, priority=None):
        """create an instance

        :param maxsize: int, the size you want the key to be, 0 for unlimited
        :param key: callable, a callback that will be passed value on every
            call to .put() that doesn't have a key passed in
        :param priority: callable, a callback that will be passed value on every
            call to .put() that doesn't have a priority passed in
        """
        self.clear()

        self.maxsize = maxsize

        if key:
            self.key = key

        if priority:
            self.priority = priority

    def clear(self):
        self.pq = []
        self.item_finder = {}
        self.key_counter = itertools.count()
        self.priority_counter = itertools.count()
        self.removed_count = 0

    def key(self, value):
        """If key isn't passed into the constructor then this method will be called"""
        return next(self.key_counter)

    def priority(self, value):
        """If priority isn't passed into the constructor then this method will be called"""
        return next(self.priority_counter)

    def push(self, value, key=None, priority=None):
        """Same interface as .put() but will remove the next element if the queue
        is full so value can be placed into the queue"""
        try:
            self.put(value, key=key, priority=priority)

        except OverflowError:
            self.popitem()
            self.put(value, key=key, priority=priority)

    def put(self, value, key=None, priority=None):
        """add a value to the queue with priority, using the key to know uniqueness

        :param value: mixed, the value to add to the queue
        :param key: string|int, this is used to determine uniqueness in the queue,
            if key is already in the queue, then the val will be replaced in the
            queue with the new priority, if key is None then .key(value) will be
            called to determine a key for value
        :param priority: int, the priority of value, if None then .priority(value)
            will be called to determine a priority for the value, defaults to FIFO
        """
        deleted = False

        if key is None:
            key = self.key(value)

        if priority is None:
            priority = self.priority(value)

        if key in self.item_finder:
            self.remove(key)

        else:
            # keep the queue contained
            if self.full():
                raise OverflowError("Queue is full")

        item = [priority, key, value, deleted]
        self.item_finder[key] = item
        heapq.heappush(self.pq, item)

    def remove(self, key):
        """remove the value found at key from the queue"""
        item = self.item_finder.pop(key)
        item[-1] = True
        self.removed_count += 1

    def popitem(self):
        """remove the next prioritized (value, key, priority) and return it"""
        pq = self.pq
        while pq:
            priority, key, value, deleted = heapq.heappop(pq)
            if deleted:
                self.removed_count -= 1

            else:
                del self.item_finder[key]
                return value, key, priority

        raise KeyError("Pop from an empty queue")

    def get(self):
        """Remove the next prioritized val and return it"""
        value, key, priority = self.popitem()
        return value

    def full(self):
        """Return True if the queue is full"""
        if not self.maxsize: return False
        return len(self.pq) >= (self.maxsize + self.removed_count)

    def keys(self):
        """return the keys in the order they are in the queue"""
        for x in self.pq:
            if not x[3]:
                yield x[1]

    def values(self):
        """return the values in the order they are in the queue"""
        for x in self.pq:
            if not x[3]:
                yield x[2]

    def qsize(self):
        """for similarity to python's queue interface"""
        return self.maxsize

    def __len__(self):
        return len(self.item_finder)

    def __bool__(self):
        return bool(len(self))
    __nonzero__ = __bool__


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

    https://docs.python.org/3/tutorial/datastructures.html#more-on-lists
    """
    def __init__(self, iterable=None, key=None):
        if key:
            self.key = key
        self._keys = []
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

        This is handy if you want to do some post insertion manipulation of the
        list

        :param i: int, the position x was inserted in the list, will be None if
            x was inserted at the end of the list
        :param x: Any, the object inserted into the list
        """
        pass

    def append(self, x):
        k = self.key(x)
        # https://docs.python.org/3/library/bisect.html#bisect.bisect_right
        i = bisect.bisect_right(self._keys, k)
        if i is None:
            super().append((self.key(x), x))
            self._keys.append(k)

        else:
            super().insert(i, (self.key(x), x))
            self._keys.insert(i, k)

        self.inserted(i, x)

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def remove(self, x):
        k = self.key(x)
        self._keys.remove(k)
        super().remove((k, x))

    def pop(self, i=-1):
        self._keys.pop(i)
        return super().pop(i)[-1]

    def clear(self):
        super().clear()
        self._keys.clear()

    def __iter__(self):
        for x in super().__iter__():
            yield x[-1]

    def __reversed__(self):
        index = len(self)
        while index > 0:
            index -= 1
            yield self[index]

    def __getitem__(self, i):
        return super().__getitem__(i)[-1]

    def __delitem__(self, i):
        self.pop(i)

    def insert(self, i, x):
        raise NotImplementedError()
    def __setitem__(self, i, x):
        raise NotImplementedError()
    def reverse(self):
        raise NotImplementedError()
    def sort(self):
        raise NotImplementedError()


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

