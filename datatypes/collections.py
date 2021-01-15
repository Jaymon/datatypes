# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import heapq
import itertools
import bisect

from .compat import *


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is reached
    then the least used item will be silently dropped from the pool.

    This class gets interesting when you extend it and add __missing__() so you
    can use this as kind of a hotcache of the maxsize most used items in the Pool

    :Example:
        class HotPool(Pool):
            def __missing__(self, key):
                value = get_some_value_here(key)
                self[key] = value # save the found value at key so it will cache
                return value
    """
    def __init__(self, maxsize=0):
        super(Pool, self).__init__()
        self.pq = PriorityQueue(maxsize, key=lambda value: value)

    def __getitem__(self, key):
        shuffle = key in self
        value = super(Pool, self).__getitem__(key)

        # since this is being accessed again, we move it to the end
        if shuffle:
            self.pq.put(key)

        return value

    def __setitem__(self, key, value):
        super(Pool, self).__setitem__(key, value)
        try:
            self.pq.put(key)

        except OverflowError:
            self.popitem()
            self.pq.put(key)

    def popitem(self):
        dead_val, dead_key, dead_priority = self.pq.popitem()
        del self[dead_key]
        return dead_key, dead_val

    def pop(self, key, *args):
        if key in self:
            self.pq.remove(key)
        return super(Pool, self).pop(key, *args)

    def setdefault(self, key, value):
        if key not in self:
            self[key] = value

    def get(self, key, default=None):
        value = default
        if key in self:
            value = self[key]
        return value

    def update(self, d):
        for k, v in d.items():
            self[k] = v


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
        self.pq = []
        self.item_finder = {}
        self.key_counter = itertools.count()
        self.priority_counter = itertools.count()
        self.maxsize = maxsize
        self.removed_count = 0

        if key:
            self.key = key

        if priority:
            self.priority = priority

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


class NormalizeDict(dict):
    """A normalizing dictionary, taken from herd.utils.NormalizeDict"""
    def __init__(self, *args, **kwargs):
        super(NormalizeDict, self).__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, k, v):
        k = self.normalize_key(k)
        v = self.normalize_value(v)
        return super(NormalizeDict, self).__setitem__(k, v)

    def __delitem__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__delitem__(k)

    def __getitem__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__getitem__(k)

    def __contains__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__contains__(k)

    def setdefault(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).setdefault(k, v)

    def update(self, *args, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        d = dict(*args, **kwargs)
        for k, v in d.items():
            self[k] = v

    def pop(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).pop(k, v)

    def get(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).get(k, v)

    def normalize_key(self, k):
        return k

    def normalize_value(self, v):
        return v


class idict(NormalizeDict):
    """A case insensitive dictionary, adapted from herd.utils.NormalizeDict, naming
    convention is meant to mimic python's use of i* for case-insensitive functions and
    python's built-in dict class (which is why the classname is all lowercase)"""
    def __init__(self, *args, **kwargs):
        self.ikeys = {} # hold mappings from normalized keys to the actual key
        super(idict, self).__init__(*args, **kwargs)

    def normalize_key(self, k):
        nk = k.lower()
        if nk in self.ikeys:
            k = self.ikeys[nk]
        self.ikeys[nk] = k
        return k
Idict = idict
IDict = idict
iDict = idict


class Trie(object):
    """https://en.wikipedia.org/wiki/Trie"""
    def __init__(self, *values):
        self.values = {} #defaultdict(list)

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
        return super(AppendList, self).append(x)

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def __setitem__(self, *args, **kwargs):
        raise NotImplementedError()
    insert = __setitem__
    remove = __setitem__
    pop = __setitem__
    clear = __setitem__
    __delitem__ = __setitem__


class OrderedList(list):
    """Keep a list sorted as you append or extend it

    An ordered list, this sorts items from smallest to largest using key, so
    if you want MaxQueue like functionality use negative values: .pop(-1) and
    if you want MinQueue like functionality use positive values: .pop(0)
    """
    def __init__(self, iterable=None, key=None):
        if key:
            self.key = key
        self._keys = []
        super(OrderedList, self).__init__()
        if iterable:
            for x in iterable:
                self.append(x)

    def key(self, x):
        return x

    def append(self, x):
        k = self.key(x)
        # https://docs.python.org/3/library/bisect.html#bisect.bisect_right
        i = bisect.bisect_right(self._keys, k)
        if i is None:
            super(OrderedList, self).append((self.key(x), x))
            self._keys.append(k)
        else:
            super(OrderedList, self).insert(i, (self.key(x), x))
            self._keys.insert(i, k)

    def extend(self, iterable):
        for x in iterable:
            self.append(x)

    def remove(self, x):
        k = self.key(x)
        self._keys.remove(k)
        super(OrderedList, self).remove((k, x))

    def pop(self, i=-1):
        self._keys.pop(i)
        return super(OrderedList, self).pop(i)[-1]

    def clear(self):
        super(OrderedList, self).clear()
        self._keys.clear()

    def __iter__(self):
        for x in super(OrderedList, self).__iter__():
            yield x[-1]

    def __getitem__(self, i):
        return super(OrderedList, self).__getitem__(i)[-1]

    def insert(self, i, x):
        raise NotImplementedError()
    def __setitem__(self, x):
        raise NotImplementedError()
    def reverse(self):
        raise NotImplementedError()
    def sort(self):
        raise NotImplementedError()


class MembershipSet(set):
    """A set with all the AND, OR, and UNION operations disabled, making it really
    only handy for testing membership

    This is really more of a skeleton for the few times I've had to do this in a
    project, usually we are implementing custom functionality that acts like a set
    and so it will be nice to just be able to extend this and not have to worry
    about disabling the unsupported methods

    I thought of the name HotSet also

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


class ListIterator(list):
    """A base interface for iterators that should quack like a builtin list

    it defines the list interface as much as possible

    Taken from prom.query.BaseIterator on 12-15-2020

    list interface methods:
        https://docs.python.org/3/tutorial/datastructures.html#more-on-lists

    http://docs.python.org/2/library/stdtypes.html#iterator-types
    """
    def __init__(self, *args, **kwargs):
        super(Iterator, self).__init__(*args, **kwargs)

    def next(self):
        raise NotImplementedError()

    def __next__(self):
        """needed for py3 api compatibility"""
        return self.next()

    def __iter__(self):
        return self

    def __nonzero__(self):
        return True if self.count() else False

    def __len__(self):
        return self.count()

    def count(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def __getslice__(self, i, j):
        """required for slicing in python 2 when extending built-in types like list

        https://docs.python.org/2/reference/datamodel.html#object.__getslice__
        https://stackoverflow.com/questions/2936863/implementing-slicing-in-getitem#comment39878974_2936876
        """
        return self.__getitem__(slice(i, j))

    def __getitem__(self, k):
        raise NotImplementedError()

    def reverse(self):
        """list interface compatibility"""
        raise NotImplementedError()

    def __reversed__(self):
        it = self.copy()
        it.reverse()
        return it

    def sort(self, *args, **kwargs):
        """list interface compatibility"""
        raise NotImplementedError()

    def __getattr__(self, k):
        """
        this allows you to focus in on certain fields of results

        It's just an easier way of doing: (getattr(x, k, None) for x in self)
        """
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

    def index(self, x, start=None, end=None):
        """list interface compatibility"""
        raise NotImplementedError()

    def copy(self):
        """list interface compatibility"""
        raise NotImplementedError()

