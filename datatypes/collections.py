# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import heapq
import itertools
import bisect

from .compat import *


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is reached
    then the least used item will be silently dropped from the pool.

    In order to use this class you must extend it and implement the create_value
    method 
    """
    def __init__(self, size=0):
        super(Pool, self).__init__()
        self.pq = KeyQueue(size)

    def __getitem__(self, key):
        shuffle = key in self
        val = super(Pool, self).__getitem__(key)

        # since this is being accessed again, we move it to the end
        if shuffle:
            self.pq.put(key, val)

        return val

    def __setitem__(self, key, val):
        super(Pool, self).__setitem__(key, val)
        try:
            self.pq.put(key, val)
        except OverflowError:
            self.get()
            self.pq.put(key, val)

    def popitem(self):
        dead_key, dead_val, dead_priority = self.pq.popitem()
        del self[dead_key]
        return dead_key, dead_val

    def __missing__(self, key):
        val = self.create_value(key)
        self[key] = val
        return val

    def create_value(self, key):
        raise NotImplementedError()


class PriorityQueue(object):
    """A simple priority queue

    if passing in a tuple (priority, value) then...

        * MinQueue: lambda x: x[0]
        * MaxQueue: lambda x: -x[0]

    based off of https://stackoverflow.com/a/3311765/5006

    https://en.wikipedia.org/wiki/Priority_queue

    :Example:
        pq = PriorityQueue(lambda x: x[0])
        pq.put((30, "che"))
        pq.put((1, "foo"))
        pq.put((4, "bar"))
        pq.get() # (1, "foo")
    """
    def __init__(self, key=None):
        self.pq = []
        if key:
            self.key = key

    def key(self, x):
        return x

    def __len__(self):
        return len(self.pq)

    def __bool__(self):
        return bool(len(self))
    __nonzero__ = __bool__

    def put(self, x):
        heapq.heappush(self.pq, (self.key(x), x))

    def get(self):
        return heapq.heappop(self.pq)[-1]


class KeyQueue(object):
    """A semi-generic priority queue, if you never pass in priorities it defaults to
    a FIFO queue, this allows you to pass in keys to add() to set uniqueness and move
    items back to the top of the queue if they have the same key, another name for this
    might be RefreshQueue since a value with the same key will move to the top of the
    list

    This is basically an implementation of the example on this page:
    https://docs.python.org/2/library/heapq.html#priority-queue-implementation-notes
    """
    def __init__(self, size=0):
        """create an instance

        :param size: int, 0 means the queue is unbounded, otherwise it will raise an
            OverflowError when you try and add more than size values"""
        self.pq = []
        self.item_finder = {}
        self.counter = itertools.count()
        self.size = size
        self.removed_count = 0

    def put(self, key, val, priority=None):
        """add a value to the queue with priority, using the key to know uniqueness

        :param val: mixed, the value to add to the queue
        :param key: string, this is used to determine if val already exists in the queue,
            if key is already in the queue, then the val will be replaced in the
            queue with the new priority
        :param priority: int, the priority of val
        """
        if key in self.item_finder:
            self.remove(key)

        else:
            # keep the queue contained
            if self.full():
                raise OverflowError("Queue is full")

        if priority is None:
            priority = next(self.counter)

        item = [priority, key, val]
        self.item_finder[key] = item
        heapq.heappush(self.pq, item)

    def remove(self, key):
        """remove the value found at key from the queue"""
        item = self.item_finder.pop(key)
        item[-1] = None
        self.removed_count += 1

    def popitem(self):
        """remove the next prioritized [key, val, priority] and return it"""
        pq = self.pq
        while pq:
            priority, key, val = heapq.heappop(pq)
            if val is None:
                self.removed_count -= 1

            else:
                del self.item_finder[key]
                return key, val, priority

        raise KeyError("Pop from an empty queue")

    def get(self):
        """remove the next prioritized val and return it"""
        key, val, priority = self.popitem()
        return val

    def full(self):
        """Return True if the queue is full"""
        if not self.size: return False
        return len(self.pq) == (self.size + self.removed_count)

    def keys(self):
        """return the keys in the order they are in the queue"""
        return [x[1] for x in self.pq if x[2] is not None]

    def values(self):
        """return the vals in the order they are in the queue"""
        return [x[2] for x in self.pq if x[2] is not None]

    def __contains__(self, key):
        return key in self.item_finder


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

    def setdefault(self, key, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).setdefault(k, v)

    def update(self, *args, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        d = dict(*args, **kwargs)
        for k, v in d.items():
            self[k] = v

    def pop(self, key, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).pop(k, v)

    def get(self, key, default=None):
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

