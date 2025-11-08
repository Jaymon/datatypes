# -*- coding: utf-8 -*-
"""
Dict and Map like objects

https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping
https://docs.python.org/3/library/stdtypes.html#dict

class Dictionary(dict):
    def __init__(self, iterable_or_mapping=None, **kwargs):
        if iterable_or_mapping:
            super().__init__(iterable_or_mapping, **kwargs)

        else:
            super().__init__(**kwargs)

    def clear(self):
        return super().clear()

    def copy(self):
        return super().copy()

    def get(key, default=None, /):
        return super().get(key, default)

    def items(self):
        return super().items()

    def keys(self):
        return super().keys()

    def values(self):
        return super().values()

    def pop(self, key, *default):
        return super().pop(key, *default)

    def popitem(self):
        return super().popitem()

    def setdefault(self, key, default=None, /):
        return super().setdefault(key, default)

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)

    def __setitem__(self, key, value, /):
        return super().__setitem__(key, value)

    def __getitem__(self, key, /):
        return super().__getitem__(key)

    def __delitem__(self, key, /):
        return super().__delitem__(key)

"""
from __future__ import annotations
from contextlib import contextmanager, AbstractContextManager

from ..compat import *
from .container import HotSet
from .sequence import Stack
from collections.abc import Mapping, Generator, Iterable
from typing import Any


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is
    reached then the least used item will be silently dropped from the pool.

    This class gets interesting when you extend it and add __missing__() so
    you can use this as kind of a hot cache of the maxsize most used items in
    the Pool

    :Example:
        class HotPool(Pool):
            def __missing__(self, key):
                value = get_some_value_here(key)
                self[key] = value # cache value at key
                return value
    """
    def __init__(self, maxsize=0):
        super().__init__()
        self.pq = HotSet(maxsize=maxsize)

    def __getitem__(self, key):
        shuffle = key in self
        value = super().__getitem__(key)

        # since this is being accessed again, we refresh it
        if shuffle:
            self.pq.add(key)

        return value

    def __setitem__(self, key, value):
        if len(self.pq) == self.pq.maxsize:
            self.popitem()

        super().__setitem__(key, value)

        self.pq.add(key)

    def __delitem__(self, key):
        super().__delitem__(key)
        self.pq.remove(key)

    def popitem(self):
        if self:
            dead_key = self.pq.pop()
            dead_value = super().__getitem__(dead_key)
            super().__delitem__(dead_key)
            return dead_key, dead_value

        else:
            raise KeyError("Pool is empty")

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
        """Check every key in the keys list, first found key is returned, if
        none of the keys exist then return default

        :Example:
            d = Dict({
                "foo": 1,
                "bar": 2,
                "che": 3,
            })

            d.get(["does", "not", "exist", "foo"], 5) # 1
            d.get(["does", "bar", "exist", "foo"], 5) # 2

        :param keys: list, a list of keys to check in the order they should be
            checked
        :param *default: mixed, what to return if none of the keys exist
        :returns: mixed, either the value of the first key that exists or
            default_val
        """
        for k in keys:
            if k in self:
                return self[k]
        return default

    def pops(self, keys, *default):
        """Check every key in the keys list, first found key will be returned,
        if none of the keys exist then return default, all keys in the keys
        list will be popped, even the ones after a value is found

        :Example:
            d = Dict({
                "foo": 1,
                "bar": 2,
                "che": 3,
            })

            d.pop(["foo"], 5) # 1
            d.pop(["foo", "bar"], 5) # 2

        :param keys: list, a list of keys to check in the order they should be
            checked
        :param *default: mixed, what to return if none of the keys exist
        :returns: mixed, either the value of the first key that exists or
            default_val
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

        :param other: Mapping, the other dict to merge into this dict, if
            self[key] is not a Mapping, then other[key] will override, if both
            self[key] and other[key] are Mapping instances then they will be
            merged
        """
        for k in other.keys():
            if isinstance(other[k], Mapping) and (k in self):
                if isinstance(self[k], Dict):
                    self[k].merge(other[k])

                elif isinstance(self[k], Mapping):
                    self[k] = type(self)(self[k])
                    self[k].merge(other[k])

                else:
                    self[k] = other[k]

            else:
                self[k] = other[k]


class NormalizeMixin(object):
    """Mixin to create a normalizing dictionary

    This class must come before the mapping base class when defining the
    custom child class

    :example:
        class Foo(NormalizeMixin, dict):
            def normalize_key(self, k):
                return k

            def normalize_value(self, v):
                return v

    You can override the .normalize_key and .normalize_value methods, which get
    called anytime you set/get a value. You can check out the idict class for
    an implementation that uses those methods to allow case-insensitive keys

    Taken from `herd.utils.NormalizeDict`
    """
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.update(*args, **kwargs)

    def __setitem__(self, k, v):
        k = self.normalize_key(k)
        v = self.normalize_value(v)
        return super().__setitem__(k, v)

    def __delitem__(self, k):
        k = self.normalize_key(k)
        return super().__delitem__(k)

    def __getitem__(self, k):
        k = self.normalize_key(k)
        return super().__getitem__(k)

    def __contains__(self, k):
        k = self.normalize_key(k)
        return super().__contains__(k)

    def setdefault(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super().setdefault(k, v)

    def update(self, *args, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        d = dict(*args, **kwargs)
        for k, v in d.items():
            self[k] = v

    def pop(self, k, *default):
        k = self.normalize_key(k)
        if default:
            default = [self.normalize_value(default[0])]
        return super().pop(k, *default)

    def get(self, k, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super().get(k, v)

    def normalize_key(self, k):
        return k

    def normalize_value(self, v):
        return v

    def ritems(self, *keys):
        keys = map(self.normalize_key, keys)
        return super().ritems(*keys)


class idict(NormalizeMixin, Dict):
    """A case insensitive dictionary, adapted from `herd.utils.NormalizeDict`,
    naming convention is meant to mimic python's use of i* for case-insensitive
    functions and python's built-in dict class (which is why the classname is
    all lowercase)"""
    def __init__(self, *args, **kwargs):
        # lookup table holding key variations to the actual key
        self.key_lookup = {}

        super().__init__(*args, **kwargs)

    def normalize_key(self, k):
        if k in self.key_lookup:
            k = self.key_lookup[k]

        else:
            self.key_lookup[k] = k

            nk = k.lower()
            if nk in self.key_lookup:
                k = self.key_lookup[nk]
            self.key_lookup[nk] = k

        return k


class NamespaceMixin(object):
    """Mixin to create an attribute dictionary

    This makes `self.foo` work like `self["foo"]

    This class must come before the mapping base class when defining the
    custom child class

    :example:
        class Foo(NamespaceMixin, dict):
            pass
    """
    def __setattr__(self, k, v):
        if k.startswith("__"):
            return super().__setattr__(k, v)

        else:
            return self.__setitem__(k, v)

    def __getattr__(self, k):
        """Treat a missing attribute like a `.__getitem__` key request

        :raises KeyError: When the attribute `k` is missing, this is to
            hint to the developer that a dictionary key using an alternate
            syntax was being requested and means that `self.foo` and
            `self["foo"]` can be handled the same way
        """
        if k.startswith("__"):
            return super().__getattr__(k)

        else:
            return self.__getitem__(k)

    def __delattr__(self, k):
        if k.startswith("__"):
            return super().__delattr__(k)

        else:
            return self.__delitem__(k)


class Namespace(NamespaceMixin, Dict):
    """Allows both dictionary syntax (eg foo["keyname"]) and object syntax
    (eg foo.keyname)
    """
    pass


class StackNamespace(Mapping):
    """Nested namespaces that can be changed for the given context and then
    reverted to the previous context when the context is done

    :example:
        n = StackNamespace()
        n["foo"] = 1
        with n:
            n["foo"] = 2
            with n("named context"):
                n["foo"] = 3
                print(n["foo"]) # 3

            print(n["foo"]) # 2

        print(n["foo"]) # 1

    Internally, an instance keeps track of a stack of contexts and pops off
    the last context created every time a context block is finished. This
    class quacks like a mapping and always references the last context on
    the stack
    """
    def __init__(self, name: str = "", cascade: bool = True):
        """
        :param name: str, If you want to customize the default context name
        then pass it in
        :param cascade: bool, if True then gets cascade through the stack of
            contexts, if False then this contexts completely switch
        """
        super().__init__()

        self._contexts = {
            "active": [],
            "cascade": cascade,
        }

        self.push_context(name, source="__init__")

    def __enter__(self) -> ContextNamespace:
        """Allow `with instance:` context invocation"""
        context_tuple = self._contexts["active"][-1]
        if context_tuple[2] == "__call__":
            context_tuple[2] = "__enter__"

        else:
            self.push_context("", source="__enter__")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.pop_context()
        return None

    def __call__(self, name: str = "", **kwargs):
        """Allow `with instance(...):` context invocation"""
        self.push_context(name, kwargs, "__call__")
        return self

    @contextmanager
    def context(
        self,
        name: str = "",
        **kwargs
    ) -> AbstractContextManager[ContextNamespace]:
        """This is meant to be used with the "with ..." command, its purpose is
        to make it easier to change the context and restore it back to the
        previous context when it is done

        :example:
            with instance.context("foo"):
                # anything in this block will use the foo configuration
                pass
            # anything outside this block will *NOT* use the foo configuration
        """
        with self(name, **kwargs) as s:
            yield s

    def context_name(self) -> str:
        """Get the current context name"""
        return self._current_context_tuple()[0]
        #return self._contexts["active"][-1][0]

    def _current_context_tuple(self) -> tuple[str, Mapping, str]:
        """Internal method. Gets the full context tuple for the current
        context"""
        #return self._contexts["active"][-1]
        # we pull directly from the __dict__ so __setattr__
        # doesn't infinite loop
        if contexts := self.__dict__.get("_contexts", None):
            return contexts["active"][-1]
        raise IndexError("No current contexts")

    def current_context(self) -> Mapping:
        """get the current context"""
        return self._current_context_tuple()[1]
        #return self._contexts["active"][-1][1]

    def has_context(self) -> bool:
        try:
            self._current_context_tuple()
            return True

        except IndexError:
            return False

#         if contexts := self.__dict__.get("_contexts", None):
#             return len(contexts["active"]) > 0
#         return False

    def push_context(
        self,
        name: str,
        context: Mapping|None = None,
        source: str = "",
    ) -> str:
        """push a context named name onto the context stack"""
        self._contexts["active"].append([name, context or {}, source])
        return name

    def pop_context(self) -> tuple[str, Mapping, str]:
        """Pop the last context from the stack"""
        if self.has_context():
            return self._contexts["active"].pop(-1)

    def active_contexts(self) -> Generator[Mapping]:
        """yield all the contexts taking into account the cascade setting
        """
        for context_tuple in reversed(self._contexts["active"]):
            yield context_tuple[1]

            if not self._contexts["cascade"]:
                break

    def __setattr__(self, k, v):
        if self.has_context():
            self.__setitem__(k, v)

        else:
            super().__setattr__(k, v)

    def __setitem__(self, k, v):
        self.current_context().__setitem__(k, v)

    def __delattr__(self, k):
        if self.has_context():
            self.__delitem__(k)

        else:
            super().__delattr__(k)

    def __delitem__(self, k):
        self.current_context().__delitem__(k)

    def __getattr__(self, k):
        if self.has_context():
            return self.__getitem__(k)

        else:
            raise KeyError(k)
            #return super().__getattr__(k)

    def __getitem__(self, k):
        """Most of the context LIFO magic happens here, this will work through
        the contexts looking for k"""
        for context in self.active_contexts():
            try:
                return context[k]

            except KeyError:
                pass

        return self.__missing__(k)

    def __missing__(self, k):
        raise KeyError(k)

    def __contains__(self, k):
        for context in self.active_contexts():
            if k in context:
                return True

        return False

    def __len__(self):
        """Unlike a normal dict this is O(n)"""
        return len(list(self.keys()))

    def __ior__(self, other):
        """self |= other"""
        self.update(other)
        return self

    def __or__(self, other):
        """self | other"""
        d = {i[0]: i[1] for i in self.items()}
        d.update(other)
        return d

    def setdefault(self, k, v):
        if k not in self:
            self[k] = v

    def get(self, k, default=None):
        try:
            return self[k]

        except KeyError:
            return default

    def pop(self, k, *default):
        """Pop works a little differently than other key access methods, pop
        will only return a value if it is actually in the current context, if
        `k` is not in the current context then this will return default. It
        does this because it would violate the principal of least surprise if
        popping something in the current context actually popped it from a
        previous context
        """
        try:
            d = self.current_context()
            v = d[k]
            del d[k]

        except (KeyError, IndexError):
            if default:
                v = default[0]

            else:
                raise

        return v

    def popitem(self):
        return self.current_context().popitem()

    def clear(self):
        return self.current_context().clear()

    def update(self, *args: Iterable[tuple[Any, Any]]|Mapping, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        self.current_context().update(*args, **kwargs)

    def copy(self):
        """return a dict of all active values in the config at the moment"""
        return dict(item for item in self.items())

    def items(self):
        seen_keys = set()
        for context in self.active_contexts():
            for k, v in context.items():
                if k not in seen_keys:
                    yield k, v
                    seen_keys.add(k)

    def __iter__(self):
        yield from self.keys()

    def keys(self):
        for k, _ in self.items():
            yield k

    def values(self):
        for _, v in self.items():
            yield v


class ContextNamespace(StackNamespace):
    """A context aware namespace where you can override values in later
    contexts and then revert back to the original context when the with
    statement is done

    values are retrieved in LIFO order of the pushed contexts when
    `cascade=True`

    Based on `bang.config.Config` moved here and expanded on 1-10-2023

    Similar to a ChainMap:
        https://docs.python.org/3/library/collections.html#chainmap-objects

    :example:
        n = ContextNamespace()

        n.foo = 1
        with n.context("one"):
            n.foo # 1
            n.foo = 2
            n.foo # 2
            with n.context("two"):
                n.foo # 2
                n.foo = 3
                n.foo #3

            n.foo # 2

        n.foo # 1

        # calling the context again restores the values
        with n.context("one"):
            n.foo # 2

        n.foo # 1

        # you can also turn cascading off, so it switches contexts but doesn't 
        # cascade the values

        n = ContextNamespace(cascade=False)

        n.foo = 1
        with n.context("one"):
            "foo" in n.foo # False
            n.foo = 2
            "foo" in n.foo # True

        n.foo # 1

    Internally, this class keeps a stack of active contexts and when the
    context blocks are done, the context is moved to an inactive mapping,
    if the context name is used again, that context will be moved from the
    inactive mapping back to the active stack
    """
    def push_context(
        self,
        name: str,
        context: Mapping|None = None,
        source: str = "",
    ) -> str:
        inactive = self._contexts.get("inactive", {})
        d = inactive.get(name, {})

        if context:
            d.update(context)

        return super().push_context(name, d, source)

    def pop_context(self) -> Mapping:
        """Pop the last context from the stack"""
        context_tuple = super().pop_context()
        self._contexts.setdefault("inactive", {})

        self._contexts["inactive"][context_tuple[0]] = context_tuple[1]
        return context_tuple


class DictTree(Dict):
    """A dict/tree hybrid, what that means is you can pass in a list of keys
    and it will create sub DictTrees at each key so you can nest values. This
    could also be called a NestingDict, hierarchyDict, or something like that

    https://github.com/Jaymon/datatypes/issues/29

    :example:
        d = DictTree()

        d.set(["foo", "bar", "che"], 1)
        d.get(["foo", "bar", "che"]) # 1

        d.set([], 2) # set a value on the root node
        d.value # 2
        d[[]] # 2

    This is the terminology (with tree_ prefix) I'm trying to adhere to:
        https://en.wikipedia.org/wiki/Tree_(data_structure)#Terminology

    Each tree node in the tree has these properties:

        * .parent: DictTree, points to the tree node above this tree, this
            will be None if this is the absolute head tree
        * .key: str, the name of the key this tree is in (so 
            `self == self.parent[self.name]`), this will be "" if this
            node is the absolute .root node of the tree
        * .pathkeys: list[str], similar to .name but returns the entire set of
            names in the order needed to traverse from the .root node back
            to this node. This isn't named .keys to avoid a naming collision
            with the dict.keys method
        * .root: DictTree, the absolute head node of the tree
        * .value: Any, the value at this node of the tree, None if the node
            has no value
    """
    @property
    def pathkeys(self):
        """Get the path of keys from the absolute head tree to this tree

        :returns: list[str]
        """
        keys = [self.key]
        parent = self
        while parent := parent.parent:
            keys.append(parent.key)
        return list(reversed(keys[:-1]))

    def __init__(self, *args, **kwargs):
        """This should support all the standard dict init signatures"""
        self.root = self
        self.parent = None
        self.key = None
        self.value = None

        super().__init__()
        self.update(*args, **kwargs)

    def update(self, mapping_or_iterable=None, **kwargs):
        """
        https://docs.python.org/3/library/stdtypes.html#dict.update
        """
        if mapping_or_iterable:
            if isinstance(mapping_or_iterable, Mapping):
                mapping_or_iterable = mapping_or_iterable.items()

            for k, v in mapping_or_iterable:
                self.set(k, v)

        if kwargs:
            for k, v in kwargs.items():
                self.set(k, v)

    def create_instance(self):
        """Internal method. Called from .add_node and is only responsible
        for creating an instance of this class.

        The reason this exists is because the __init__ might be customized
        in a child class and so this can also be customized so nothing fails
        and .add_node can be left alone since it sets the node properties

        :returns: DictTree instance
        """
        return type(self)()

    def __getitem__(self, keys):
        """Allow list access in normal dict interactions

        :param keys: list[hashable]|hashable
        :returns: Any, the value found at the end of keys
        """
        node = self.get_node(keys)
        return node.value

    def __setitem__(self, keys, value):
        """Allow list access in normal dict interactions"""
        self.set(keys, value)

    def __delitem__(self, keys):
        """Allow list access in normal dict interactions"""
        self.pop_node(keys)

    def __contains__(self, keys):
        """Allow list access when checking a key"""
        try:
            self.get_node(keys)
            ret = True

        except KeyError:
            ret = False

        return ret

    def set(self, keys, value):
        """Set value into the last key in keys, creating intermediate dicts 
        along the way

        :param keys: list[hashable]|hashable, a list of keys or the key you
            want to set value in
        :param value: Any
        """
        keys = self.normalize_keys(keys)

        if len(keys) > 1:
            key = self.normalize_key(keys[0])
            if key not in self:
                self.add_node(key, self.create_instance(), None)

            super().__getitem__(key).set(keys[1:], value)

        else:
            if keys:
                key = self.normalize_key(keys[0])
                value = self.normalize_value(value)
                if key not in self:
                    self.add_node(key, self.create_instance(), value)

                else:
                    self.update_node(
                        key,
                        super().__getitem__(key),
                        value
                    )

            else:
                # root of the tree
                self.update_node(
                    self.key,
                    self,
                    self.normalize_value(value)
                )

    def add_node(self, key, node, value):
        """Add `node` into `self` at `key` with `value`

        NOTE -- this is never called for the root node since the root node
        is never added into another node

        :param key: Hashable, already ran through .normalize_key
        :param node: ClasspathFinder, freshly created with .create_instance
        :param value: Any, already ran through .normalize_value
        """
        node.parent = self
        node.key = key
        node.root = self.root
        node.value = value
        super().__setitem__(key, node)

    def update_node(self, key, node, value):
        """Update `node` of `self` at `key` with `value`

        NOTE -- this only updates the value of node, the key is only here to
        keep the signature the same as .add_node and self and node can be the
        same node when the root node is being updated

        :param key: Hashable, already ran through .normalize_key
        :param node: ClasspathFinder, the node to update
        :param value: Any, already ran through .normalize_value
        """
        node.value = value

    def normalize_keys(self, keys):
        """Internal method. This makes sure keys is a sequence

        Called on both set and get

        :param keys: list[hashable]|tuple[hashable, ...]|hashable
        :returns: sequence[hashable]
        """
        if not isinstance(keys, (list, tuple)):
            keys = [keys]

        return keys

    def normalize_key(self, key):
        """Internal method. Hook that is called right before key is used
        to access

        Called on both set and get

        :param key: Hashable
        :returns: Hashable
        """
        return key

    def normalize_value(self, value):
        """Internal method. Hook that is called right before value is set
        into the node.

        Called *only* on set

        :param value: Any
        :returns: Any
        """
        return value

    def get_node(self, keys):
        """Gets the node found at keys, most of the magic happens in this
        method and is a key building block of all the other methods

        This method is recursive

        :param keys: see .normalize_key
        :returns: DictTree
        :raises: KeyError, if the key doesn't exist
        """
        keys = self.normalize_keys(keys)
        if keys:
            node = super().__getitem__(self.normalize_key(keys[0]))

            if len(keys) > 1:
                node = node.get_node(keys[1:])

        else:
            node = self

        return node

    def get(self, keys, default=None):
        """Get the value of the last key in keys, otherwise return default

        :param keys: list[hashable]|hashable, the path to return
        :param default: Any, if value isn't found at the end of keys then
            return this value
        :returns: Any
        """
        try:
            return self[keys]

        except KeyError:
            return default

    def pop(self, keys, *default):
        """Pop a value from the tree

        This does not trim the tree if it isn't a leaf, so if this is a
        waypoint value it will just be set to None and the branches will remain
        intact. 

        :param keys: Hashable|list[Hashable], As with .set and .get this allows
            a list of keys or key
        :param *default: Any, if present returned instead of rasing a KeyError
        :returns: Any, whatever was the value
        :raises: KeyError, if keys isn't found in the tree or if the node's
            value is None (meaning it didn't have a value)
        """
        try:
            node = self.get_node(keys)

            if len(node) == 0:
                # we trim the node since it has no children
                node.parent.pop_node(node.key)

            if node.value is None:
                raise KeyError(keys)

            v = node.value
            node.value = None
            return v

        except KeyError:
            if default:
                return default[0]

            else:
                raise

    def pop_node(self, keys, *default):
        """Pop the node and trim the tree

        NOTE -- this trims the tree, so if you pop a tree node it will trim
        all the leaves of that node from the root tree. In fact, I first named
        this .trim, then .trim_node, but I think it is more cohesive to be
        named .pop_node, like .get/.get_node

        :param keys: Hashable|list[Hashable], As with .set and .get this allows
            a list of keys or key
        :param *default: Any, if present returned instead of rasing a KeyError
        :returns: DictTree, the returned node is completely intact with all
            down stream keys and pointers but .root will no longer contain this
            node
        :raises: KeyError, if keys isn't found in the tree
        """
        keys = self.normalize_keys(keys)

        try:
            if len(keys) > 1:
                return self.get_node(keys[:-1]).pop_node(keys[-1])

            else:
                return super().pop(self.normalize_key(keys[-1]))

        except KeyError:
            if default:
                return default[0]

            else:
                raise

    def setdefault(self, keys, default=None):
        """As with .set and .get this allows a list of keys or key"""
        if keys in self:
            return self[keys]

        else:
            self.set(keys, default)
            return default

    def trees(self, depth=-1):
        """Iterate through the trees in this tree

        A tree is a node that contains other trees

        :param depth: int, If above 0 only proceed to that depth. If -1 then
            don't worry about depth
        :returns: generator[tuple(list, DictTree)], index 0 is the path of keys
            to get to this tree, and empty list is the root tree. Index 1 is
            the tree
        """
        if depth > 0 or depth < 0:
            if len(self):
                yield [], self

                for k, d in self.items():
                    for sk, sd in d.trees(depth=depth-1):
                        if sk:
                            yield [k] + sk, sd

                        else:
                            yield [k], sd

    def leaves(self, depth=-1):
        """Iterate through the leaves in this tree

        A leaf is a node that is the end of a tree

        :param depth: int, see .trees
        :returns: generator[tuple(list, DictTree)], Index 0 is the path of
            keys.  Index 1 is the value of the leaf node
        """
        for ks, tree in self.trees(depth=depth):
            for k, d in tree.items():
                if not len(d):
                    yield ks + [k], d

    def walk(self, keys, set_missing=False):
        """Walk each node of the tree in keys.

        Basically, if you passed in ["foo", "bar", "che"] it would first
        yield the node at ["foo"], then ["foo", "bar"], and finally the
        node at ["foo", "bar", "che"]

        :param keys: list[str]|str, the path key(s) to walk
        :returns: generator[DictTree]
        """
        keys = self.normalize_keys(keys)

        d = self
        i = -(len(keys) - 1)
        while i < 1:
            if i < 0:
                ks = keys[:i]

            else:
                ks = keys

            i += 1

            k = ks[-1]
            if k in d:
                d = d.get_node(k)
                yield ks, d

            else:
                if set_missing:
                    d.setdefault(k)
                    d = d.get_node(k)
                    yield ks, d

                else:
                    raise KeyError(k)

    def nodes(self, depth=-1):
        """Iterate all the rows in depth order, so do the first row of keys,
        then the second row of keys, etc. It's similar to how you would
        recursively iterate a folder, first you do all the files in the
        root folder, then you do all the files of all the folders in the
        root folder, etc.

        :param depth: int, see .trees
        :returns: generator[DictTree], each row of nodes starting from the
            root node and iteratin all keys of each level of nodes until the
            leaf nodes
        """
        if depth > 0 or depth < 0:
            yield [], self

            nodes = []
            for k, d in self.items():
                yield [k], d

                if len(d):
                    nodes.append((k, d))

            for k, n in nodes:
                for sk, sd in n.nodes(depth=depth-1):
                    if sk:
                        yield [k] + sk, sd

