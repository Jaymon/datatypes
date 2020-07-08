# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import heapq
import itertools

from .compat import *


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is reached
    then the least used item will be silently dropped from the pool.

    In order to use this class you must extend it and implement the create_value
    method 
    """
    def __init__(self, size=0):
        super(Pool, self).__init__()
        self.pq = PriorityQueue(size)

    def __getitem__(self, key):
        shuffle = key in self
        val = super(Pool, self).__getitem__(key)

        # since this is being accessed again, we move it to the end
        if shuffle:
            self.pq.add(val, key=key)

        return val

    def __setitem__(self, key, val):
        super(Pool, self).__setitem__(key, val)
        try:
            self.pq.add(val, key=key)
        except OverflowError:
            self.popitem()
            self.pq.add(val, key=key)

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
    """A semi-generic priority queue, if you never pass in priorities it defaults to
    a FIFO queue

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

    def add(self, val, key="", priority=None):
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

        raise KeyError("pop from an empty priority queue")

    def pop(self):
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
        super(idict, self).__init__()

    def normalize_key(self, k):
        nk = k.lower()
        if nk in self.ikeys:
            k = self.ikeys[nk]
        self.ikeys[nk] = k
        return k
Idict = idict
IDict = idict
iDict = idict


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

