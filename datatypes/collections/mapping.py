# -*- coding: utf-8 -*-
"""
Dict and Map like objects

https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping
"""
from contextlib import contextmanager

from ..compat import *
from .sequence import PriorityQueue, Stack


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
        super().__init__()
        self.pq = PriorityQueue(maxsize, key=lambda value: value)

    def __getitem__(self, key):
        shuffle = key in self
        value = super().__getitem__(key)

        # since this is being accessed again, we move it to the end
        if shuffle:
            self.pq.put(key)

        return value

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
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
        return super().pop(key, *args)

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


class Dict(dict):
    def __init__(self, *args, **kwargs):
        if len(args) > 1:
            super().__init__(args[0], **kwargs)
            for arg in args[1:]:
                self.update(arg)

        else:
            super().__init__(*args, **kwargs)

    def ritems(self, *keys):
        """Iterate through the dict and all sub dicts

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: tuple, (list, mixed), the list is the key path, all the keys
            it would take to get to this key (eg, ["foo", "bar"]) and mixed is
            the value found at the end of the key path
        """
        def iterdict(d, keypath, keys):
            for k, v in d.items():
                kp = keypath + [k]
                if k in keys:
                    yield kp, v

                else:
                    if not keys:
                        yield kp, v

                    if isinstance(v, Mapping):
                        for kp, d in iterdict(v, kp, keys):
                            yield kp, d

        keys = set(keys)
        for kp, d in iterdict(self, [], keys):
            yield kp, d

    def rkeys(self, *keys):
        """Iterate through all key paths

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: list, the key paths
        """
        for kp, _ in self.ritems(*keys):
            yield kp

    def rvalues(self, *keys):
        """Iterate through all values

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: mixed, the found values
        """
        for _, v in self.ritems(*keys):
            yield v

    def rget(self, key, default=None):
        """Return the first matching value found at key anywhere in the dict or
        sub dicts

        :param key: string, the key to find in this or any sub dicts
        :param default: mixed, if key isn't found, return this value
        :returns: mixed, the value found at the first key/subkey
        """
        v = default
        for v in self.rvalues(key):
            break
        return v

    def gets(self, keys, default=None):
        """Check every key in the keys list, first found key is returned, if none
        of the keys exist then return default

        :Example:
            d = Dict({
                "foo": 1,
                "bar": 2,
                "che": 3,
            })

            d.get(["does", "not", "exist", "foo"], 5) # 1
            d.get(["does", "bar", "exist", "foo"], 5) # 2

        :param keys: list, a list of keys to check in the order they should be checked
        :param *default: mixed, what to return if none of the keys exist
        :returns: mixed, either the value of the first key that exists or default_val
        """
        for k in keys:
            if k in self:
                return self[k]
        return default

    def pops(self, keys, *default):
        """Check every key in the keys list, first found key will be returned, if none
        of the keys exist then return default, all keys in the keys list will be
        popped, even the ones after a value is found

        :Example:
            d = Dict({
                "foo": 1,
                "bar": 2,
                "che": 3,
            })

            d.pop(["foo"], 5) # 1
            d.pop(["foo", "bar"], 5) # 2

        :param keys: list, a list of keys to check in the order they should be checked
        :param *default: mixed, what to return if none of the keys exist
        :returns: mixed, either the value of the first key that exists or default_val
        """
        ret = None
        key = None
        for k in keys:
            if k in self:
                if key is None:
                    key = k
                    ret = self.pop(k)

                else:
                    self.pop(k)

        if key is None:
            if default:
                ret = default[0]
            else:
                raise KeyError(", ".join(keys))

        return ret

    def merge(self, other):
        """Very similar to .update() but merges the dicts instead of overriding

        :Example:
            d = {
                "foo": {
                    "bar": 1
                }
            }
            d2 = {
                "foo": {
                    "che": 2
                }
            }

            d.merge(d2)
            print(d["foo"]["che"]) # 2
            print(d["foo"]["bar"]) # 1

        :param other: Mapping, the other dict to merge into this dict, if self[key]
            is not a Mapping, then other[key] will override, if both self[key] and
            other[key] are Mapping instances then they will be merged
        """
        for k in other.keys():
            if isinstance(other[k], Mapping) and (k in self):
                if isinstance(self[k], Dict):
                    self[k].merge(other[k])

                elif isinstance(self[k], Mapping):
                    self[k] = Dict(self[k])
                    self[k].merge(other[k])

                else:
                    self[k] = other[k]

            else:
                self[k] = other[k]


class NormalizeDict(Dict):
    """A normalizing dictionary, taken from herd.utils.NormalizeDict

    You can override the .normalize_key and .normalize_value methods, which get 
    called anytime you set/get a value. You can check out the idict class for an
    implementation that uses those methods to allow case-insensitive keys
    """
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

    def pop(self, k, *default):
        k = self.normalize_key(k)
        if default:
            default = [self.normalize_value(default[0])]
        return super(NormalizeDict, self).pop(k, *default)

    def get(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).get(k, v)

    def normalize_key(self, k):
        return k

    def normalize_value(self, v):
        return v

    def ritems(self, *keys):
        keys = map(self.normalize_key, keys)
        return super(NormalizeDict, self).ritems(*keys)


class idict(NormalizeDict):
    """A case insensitive dictionary, adapted from herd.utils.NormalizeDict, naming
    convention is meant to mimic python's use of i* for case-insensitive functions and
    python's built-in dict class (which is why the classname is all lowercase)"""
    def __init__(self, *args, **kwargs):
        self.ikeys = {} # hold mappings from normalized keys to the actual key
        super().__init__(*args, **kwargs)

    def normalize_key(self, k):
        nk = k.lower()
        if nk in self.ikeys:
            k = self.ikeys[nk]
        self.ikeys[nk] = k
        return k
Idict = idict
IDict = idict
iDict = idict


class Namespace(NormalizeDict):
    """Allows both dictionary syntax (eg foo["keyname"]) and object syntax
    (eg foo.keyname)
    """
    def __setattr__(self, k, v):
        return self.__setitem__(k, v)

    def __getattr__(self, k):
        try:
            return self.__getitem__(k)
        except KeyError as e:
            raise AttributeError(e) from e

    def __delattr__(self, k):
        return self.__delitem__(k)


class ContextNamespace(Namespace):
    """A context aware namespace where you can override values in later contexts
    and then revert back to the original context when the with statement is done

    values are retrieved in LIFO order of the pushed contexts when cascade=True

    Based on bang.config.Config moved here and expanded on 1-10-2023

    Similar to a ChainMap:
        https://docs.python.org/3/library/collections.html#chainmap-objects

    :Example:
        n = ContextNamespace()

        n.foo = 1
        with n.context("<CONTEXT NAME>"):
            n.foo # 1
            n.foo = 2
            n.foo # 2
            with n.context("<CONTEXT NAME 2>"):
                n.foo # 2
                n.foo = 3
                n.foo #3

            n.foo # 2

        n.foo # 1

        # you can also turn cascading off, so it switches contexts but doesn't 
        # cascade the values

        n = ContextNamespace(cascade=False)

        n.foo = 1
        with n.context("<CONTEXT NAME>"):
            "foo" in n.foo # False
            n.foo = 2

        n.foo # 1
    """
    context_class = Namespace
    """Each context will be an instance of this class"""

    def __init__(self, name="", cascade=True):
        """
        :param name: str, If you want to customize the default context name then
            pass it in
        :param cascade: bool, if True then gets cascade through the stack of
            contexts, if False then this contexts completely switch
        """
        super().__init__()

        # we set support properties directly on the __dict__ so __setattr__
        # doesn't infinite loop, context properties can just be set normally

        # a stack of the context names
        self.__dict__["_context_names"] = Stack()
        self.__dict__["_cascade"] = cascade
        self.push_context(name)

    def normalize_context_name(self, name):
        """normalize the context name, this is meant to be customized in child
        classes if needed

        :param name: str, the context name
        :returns: str, the name, normalized
        """
        return name

    def push_context(self, name):
        """push a context named name onto the context stack"""
        name = self.normalize_context_name(name)

        # this is where all the magic happens, the keys are the context names
        # and the values are the set properties for that context, 
        super().setdefault(name, self.context_class())

        self._context_names.push(name)

        return name

    def pop_context(self):
        """Pop the last context from the stack"""
        if len(self._context_names) > 1:
            return self._context_names.pop()

    def switch_context(self, name):
        """Switch to context name, return the previous context_name"""
        ret = self.pop_context()
        self.push_context(name)
        return ret

    def clear_context(self, name):
        """Completely clear the context"""
        name = self.normalize_context_name(name)
        self.get_context(name).clear()

    def context_name(self):
        """Get the current context name"""
        return self._context_names.peek()

    def context_names(self):
        """yield all the _context_names taking into account the cascade setting"""
        for context_name in self._context_names:
            yield context_name

            if not self._cascade:
                break

    def current_context(self):
        """get the current context

        :returns: self.context_class instance
        """
        return self.get_context(self.context_name())

    def get_context(self, name):
        """Get the context at name

        :returns: self.context_class instance
        """
        name = self.normalize_context_name(name)
        return super().__getitem__(name)

    def is_context(self, name):
        """Return True if name matches the current context name"""
        return self.context_name() == self.normalize_context_name(name)

    @contextmanager
    def context(self, name, **kwargs):
        """This is meant to be used with the "with ..." command, its purpose is
        to make it easier to change the context and restore it back to the
        previous context when it is done

        :Example:
            with instance.context("foo"):
                # anything in this block will use the foo configuration
                pass
            # anything outside this block will *NOT* use the foo configuration
        """
        self.push_context(name)

        # passed in values get set on the instance directly
        for k, v in kwargs.items():
            self[k] = v

        yield self

        self.pop_context()

    def __setitem__(self, k, v):
        k = self.normalize_key(k)
        v = self.normalize_value(v)
        self.current_context().__setitem__(k, v)

    def __delitem__(self, k):
        k = self.normalize_key(k)
        self.current_context().__delitem__(k)

    def __getitem__(self, k):
        """Most of the context LIFO magic happens here, this will work through
        the contexts looking for k"""
        if k == "__missing__":
            # we need to avoid infinite recursion, if __missing__ gets to here
            # it doesn't exist so go ahead and fail fast
            raise KeyError(k)

        k = self.normalize_key(k)
        for context_name in self.context_names():
            try:
                return self.get_context(context_name)[k]

            except KeyError:
                pass

        # because we completely override __getitem__ we can't rely on the
        # descriptor protocol to call __missing__ for us
        try:
            return self.__missing__(k)

        except AttributeError as e:
            raise KeyError(k)

    def __contains__(self, k):
        for context_name in self.context_names():
            if k in self.get_context(context_name):
                return True
        return False

    def __len__(self):
        """Unlike a normal dict this is O(n)"""
        return len(list(self.keys()))

    def __reversed__(self):
        return reversed(list(self.keys()))

    def __ior__(self, other):
        """self |= other"""
        self.update(other)
        return self

    def __or__(self, other):
        """self | other"""
        d = self.context_class({i[0]: i[1] for i in self.items()})
        d.update(other)
        return d

    def setdefault(self, k, v):
        if k not in self:
            self[k] = v

    def get(self, k, default=None):
        # we have to do it this way to play nice with __missing__
        if k in self:
            return self[k]
        else:
            return default

    def pop(self, k, *default):
        """Pop works a little differently than other key access methods, pop will
        only return a value if it is actually in the current context, if k is not
        in the current context then this will return default
        """
        k = self.normalize_key(k)
        try:
            d = self.current_context()
            v = d[k]
            del d[k]

        except KeyError:
            if default:
                v = self.normalize_value(default[0])
            else:
                raise

        return v

    def popitem(self):
        return self.current_context().popitem()

    def clear(self):
        return self.current_context().clear()

    def copy(self):
        """return a dict of all active values in the config at the moment"""
        d = self.context_class()

        if self._cascade:
            for context_name in reversed(self._context_names):
                d.update(self.get_context(context_name))

        else:
            d.update(self.current_context())

        return d

    def items(self):
        seen_keys = set()
        for context_name in self._context_names:
            d = self.get_context(context_name)
            for k, v in d.items():
                if k not in seen_keys:
                    yield k, v
                    seen_keys.add(k)

            if not self._cascade:
                break

    def keys(self):
        for k, _ in self.items():
            yield k

    def values(self):
        for _, v in self.items():
            yield v

