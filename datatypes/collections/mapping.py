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
from contextlib import contextmanager, AbstractContextManager

from ..compat import *
from .container import HotSet
from .sequence import Stack
from collections.abc import Mapping, Generator, Iterable, Hashable, Sequence
from typing import Any, Self, Never


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is
    reached then the least used item will be silently dropped from the pool.

    This class gets interesting when you extend it and add __missing__() so
    you can use this as kind of a hot cache of the maxsize most used items in
    the Pool

    :example:
        class HotPool(Pool):
            def __missing__(self, key):
                value = get_some_value_here(key)
                self[key] = value # cache value at key
                return value
    """
    def __init__(self, maxsize: int = 0):
        super().__init__()
        self.pq = HotSet(maxsize=maxsize)

    def __getitem__(self, key: Hashable) -> Any:
        shuffle = key in self
        value = super().__getitem__(key)

        # since this is being accessed again, we refresh it
        if shuffle:
            self.pq.add(key)

        return value

    def __setitem__(self, key: Hashable, value: Any):
        if len(self.pq) == self.pq.maxsize:
            self.popitem()

        super().__setitem__(key, value)

        self.pq.add(key)

    def __delitem__(self, key: Hashable):
        super().__delitem__(key)
        self.pq.remove(key)

    def popitem(self) -> tuple[Hashable, Any]:
        if self:
            dead_key = self.pq.pop()
            dead_value = super().__getitem__(dead_key)
            super().__delitem__(dead_key)
            return dead_key, dead_value

        else:
            raise KeyError("Pool is empty")

    def pop(self, key: Hashable, *args) -> Any:
        if key in self:
            self.pq.remove(key)
        return super().pop(key, *args)

    def setdefault(self, key: Hashable, value: Any):
        if key not in self:
            self[key] = value

    def get(self, key: Hashable, default: Any = None) -> Any:
        value = default
        if key in self:
            value = self[key]
        return value

    def update(self, d: Mapping):
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

    def ritems(self, *keys: Hashable) -> Generator[tuple[list[Hashable], Any]]:
        """Recursive items. Iterate through the dict and all sub dicts

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: tuple, the list is the key path, all the keys
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

    def rkeys(self, *keys: Hashable) -> Generator[list[Hashable]]:
        """Recursive keys. Iterate through all key paths

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: list, the key paths
        """
        for kp, _ in self.ritems(*keys):
            yield kp

    def rvalues(self, *keys: Hashable) -> Generator[Any]:
        """recursive values. Iterate through all values

        :param *keys: str, if you only want to find and iterate certain keys
        :yields: mixed, the found values
        """
        for _, v in self.ritems(*keys):
            yield v

    def rget(self, key: Hashable, default: Any = None) -> Any:
        """Recursive get. Return the first matching value found at key
        anywhere in the dict or sub dicts

        :param key: string, the key to find in this or any sub dicts
        :param default: mixed, if key isn't found, return this value
        :returns: mixed, the value found at the first key/subkey
        """
        v = default
        for v in self.rvalues(key):
            break
        return v

    def gets(self, keys: Sequence[Hashable], default: Any = None) -> Any:
        """Check every key in the keys list, first found key is returned, if
        none of the keys exist then return default

        :example:
            d = Dict({
                "foo": 1,
                "bar": 2,
                "che": 3,
            })

            d.get(["does", "not", "exist"], 5) # 5
            d.get(["does", "not", "exist", "foo"], 5) # 1 because "foo"
            d.get(["does", "bar", "exist", "foo"], 5) # 2 because "bar"

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

    def pops(self, keys: Sequence[Hashable], *default) -> Any:
        """Check every key in the keys list, first found key will be returned,
        if none of the keys exist then return default, all keys in the keys
        list will be popped, even the ones after a value is found

        :example:
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

    def getpath(self, keys: Sequence[Hashable], default: Any = None) -> Any:
        """Get the value at the end of the path of `keys`

        :example:
            d = Dict({
                "foo": {
                    "bar": {
                        "che": 1,
                    },
                },
            })
            d.getpath(["foo", "bar", "che"]) # 1

        https://github.com/Jaymon/datatypes/issues/29
        """
        ret = self
        for k in keys:
            if isinstance(ret, Mapping) and (k in ret):
                ret = ret[k]

            else:
                return default

        return ret

    def poppath(self, keys: Sequence[Hashable], *default: Any) -> Any:
        """pop the value at the end of the path of `keys`

        :example:
            d = Dict({
                "foo": {
                    "bar": {
                        "che": 1,
                    },
                },
            })
            d.poppath(["foo", "bar", "che"]) # 1

        https://github.com/Jaymon/datatypes/issues/29
        """
        keys = list(keys)
        d = self.getpath(keys[:-1], Never)
        if d is Never:
            if len(default):
                return default[0]

        else:
            try:
                return d.pop(keys[-1], *default)

            except Exception as e:
                raise KeyError(keys[-1]) from e

    def merge(self, other: Mapping):
        """Very similar to `.update()` but merges the dicts instead of
        overriding

        :example:
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


class NormalizeMappingMixin(object):
    """Mixin to create a normalizing dictionary

    This class must come before the mapping base class when defining the
    custom child class

    :example:
        class Foo(NormalizeKeyMixin, dict):
            def _normalize_key(self, k):
                return k

            def _normalize_value(self, k, v):
                return v

    You can override the `._normalize_key` or `_.normalize_value` methods,
    which get called anytime you set/get a value. You can check out the idict
    class for an implementation that uses those methods to allow
    case-insensitive keys

    Taken from `herd.utils.NormalizeDict`
    """
    def __init__(self, *args, **kwargs):
        super().__init__()
        if args or kwargs:
            self.update(*args, **kwargs)

    def __setitem__(self, k: Hashable, v: Any):
        k = self._normalize_key(k)
        v = self._normalize_value(k, v)
        return super().__setitem__(k, v)

    def __delitem__(self, k: Hashable):
        k = self._normalize_key(k)
        return super().__delitem__(k)

    def __getitem__(self, k: Hashable) -> Any:
        k = self._normalize_key(k)
        return super().__getitem__(k)

    def __contains__(self, k: Hashable) -> bool:
        k = self._normalize_key(k)
        return super().__contains__(k)

    def setdefault(self, k: Hashable, default: Any = None):
        k = self._normalize_key(k)
        v = self._normalize_value(k, default)
        return super().setdefault(k, v)

    def update(self, *args, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        d = dict(*args, **kwargs)
        for k, v in d.items():
            self[k] = v

    def pop(self, k: Hashable, *default: Any) -> Any:
        k = self._normalize_key(k)
        if default:
            default = [self._normalize_value(k, default[0])]
        return super().pop(k, *default)

    def get(self, k: Hashable, default: Any = None) -> Any:
        k = self._normalize_key(k)
        v = self._normalize_value(k, default)
        return super().get(k, v)

    def _normalize_key(self, k: Hashable) -> Hashable:
        return k

    def _normalize_value(self, k: Hashable, v: Any) -> Hashable:
        return v

    def ritems(self, *keys: Hashable) -> Generator[tuple[Hashable, Any]]:
        keys = map(self._normalize_key, keys)
        return super().ritems(*keys)


class idict(NormalizeMappingMixin, Dict):
    """A case insensitive dictionary, naming convention is meant to mimic
    python's use of i* for case-insensitive functions and python's built-in
    dict class (which is why the classname is all lowercase)

    Adapted from `herd.utils.NormalizeDict`
    """
    def __init__(self, *args, **kwargs):
        # lookup table holding key variations to the actual key
        self.key_lookup = {}

        super().__init__(*args, **kwargs)

    def _normalize_key(self, k: Hashable) -> Hashable:
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

    This is different than `ContextNamespace` in that it doesn't save the
    popped contexts, so once a context is popped it's gone

    Internally, an instance keeps track of a stack of contexts and pops off
    the last context created every time a context block is finished. This
    class quacks like a mapping and always references the last context on
    the stack.

    :example:
        n = StackNamespace()
        n["foo"] = 1
        with n:
            n["foo"] = 2
            with n("named context"):
                n["foo"] = 3
                print(n["foo"]) # 3

            print(n["foo"]) # 2

            with n("named context"):
                print(n["foo"]) # 2 because it forgot

        print(n["foo"]) # 1
    """
    def __init__(self, name: str = "", cascade: bool = True):
        """
        :param name: str, If you want to customize the default context name
        then pass it in
        :param cascade: bool, if True then gets cascade through the stack of
            contexts, if False then this contexts completely switch
        """
        super().__init__()

        self._active_contexts = []
        self._cascade = cascade

        self._push_context(name, source="__init__")

    def __enter__(self) -> Self:
        """Allow `with instance:` context invocation"""
        context_tuple = self._active_contexts[-1]
        if context_tuple[2] == "__call__":
            context_tuple[2] = "__enter__"

        else:
            self._push_context("", source="__enter__")

        return self

    def __exit__(
        self,
        exc_type: type[Exception],
        exc_val: Exception,
        exc_tb: list,
    ) -> None:
        self._pop_context()
        return None

    def __call__(self, name: str = "", **kwargs) -> Self:
        """Allow `with instance(...):` context invocation"""
        self._push_context(name, kwargs, "__call__")
        return self

    @contextmanager
    def context(
        self,
        name: str = "",
        **kwargs,
    ) -> AbstractContextManager[Self]:
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

    def _current_context_tuple(self) -> tuple[str, Mapping, str]:
        """Internal method. Gets the full context tuple for the current
        context"""
        # we pull directly from the __dict__ so __setattr__
        # doesn't infinite loop
        if contexts := self.__dict__.get("_active_contexts", None):
            return contexts[-1]
        raise IndexError("No current contexts")

    def current_context(self) -> Mapping:
        """get the current context"""
        return self._current_context_tuple()[1]

    def has_context(self) -> bool:
        try:
            self._current_context_tuple()
            return True

        except IndexError:
            return False

    def _push_context(
        self,
        name: str,
        context: Mapping|None = None,
        source: str = "",
    ):
        """push a `context` named `name` onto the context stack"""
        if context is None:
            context = {}

        self._active_contexts.append([name, context, source])

    def _pop_context(self) -> tuple[str, Mapping, str]:
        """Pop the last context from the stack"""
        if self.has_context():
            return self._active_contexts.pop(-1)

    def active_contexts(self) -> Generator[Mapping]:
        """yield all the contexts taking into account the cascade setting
        """
        for context_tuple in reversed(self._active_contexts):
            yield context_tuple[1]

            if not self._cascade:
                break

    def __setattr__(self, k: Hashable, v: Any):
        if self.has_context():
            self.__setitem__(k, v)

        else:
            super().__setattr__(k, v)

    def __setitem__(self, k: Hashable, v: Any):
        self.current_context().__setitem__(k, v)

    def __delattr__(self, k: Hashable):
        if self.has_context():
            self.__delitem__(k)

        else:
            super().__delattr__(k)

    def __delitem__(self, k: Hashable):
        self.current_context().__delitem__(k)

    def __getattr__(self, k: Hashable) -> Any:
        if self.has_context():
            return self.__getitem__(k)

        else:
            raise KeyError(k)

    def __getitem__(self, k: Hashable) -> Any:
        """Most of the context LIFO magic happens here, this will work through
        the contexts looking for k"""
        for context in self.active_contexts():
            try:
                return context[k]

            except KeyError:
                pass

        return self.__missing__(k)

    def __missing__(self, k: Hashable):
        raise KeyError(k)

    def __contains__(self, k: Hashable) -> bool:
        for context in self.active_contexts():
            if k in context:
                return True

        return False

    def __len__(self) -> int:
        """Unlike a normal dict this is O(n)"""
        return len(list(self.keys()))

    def __ior__(self, other: Mapping) -> Self:
        """self |= other"""
        self.update(other)
        return self

    def __or__(self, other: Mapping) -> Mapping:
        """self | other"""
        d = {i[0]: i[1] for i in self.items()}
        d.update(other)
        return d

    def setdefault(self, k: Hashable, v: Any):
        if k not in self:
            self[k] = v

    def get(self, k: Hashable, default: Any = None) -> Any:
        # we have to check each context like this because if we try and use
        # `self[k]` then we can get unexpected results when a class
        # implements `__missing__`
        for context in self.active_contexts():
            if k in context:
                return context[k]

        return default

    def pop(self, k: Hashable, *default: Any) -> Any:
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

    def popitem(self) -> tuple[Hashable, Any]:
        return self.current_context().popitem()

    def clear(self):
        return self.current_context().clear()

    def update(self, *args: Iterable[tuple[Any, Any]]|Mapping, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        self.current_context().update(*args, **kwargs)

    def copy(self) -> Mapping:
        """return a dict of all active values in the config at the moment"""
        return dict(item for item in self.items())

    def items(self) -> Generator[Hashable, Any]:
        seen_keys = set()
        for context in self.active_contexts():
            for k, v in context.items():
                if k not in seen_keys:
                    yield k, v
                    seen_keys.add(k)

    def __iter__(self) -> Generator[Hashable]:
        yield from self.keys()

    def keys(self) -> Generator[Hashable]:
        for k, _ in self.items():
            yield k

    def values(self) -> Generator[Any]:
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

    This is different than `StackNamespace` because it will remember previous
    contexts so you can restore them

    Internally, this class keeps a stack of created contexts and when the
    context blocks are done, the context is popped off the active stack but
    a pointer is kept to the context in case the `name` is used again,
    if the context name is used again, that context will be moved back onto
    the active stack.

    This class can be thought of as a context  mapping while `StackNamespace`
    can more be thought of as a list, in `StackNamespace` you can have
    multiple contexts with the same name because once their popped they are
    forgotten, but you can only have one context per name with this class.

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
    """
    def __init__(self, name: str = "", cascade: bool = True):
        self._all_contexts = {}
        super().__init__(name, cascade)

    def _push_context(
        self,
        name: str,
        context: Mapping|None = None,
        source: str = "",
    ):
        if name not in self._all_contexts:
            self._all_contexts[name] = {}

        d = self._all_contexts[name]

        if context:
            d.update(context)

        super()._push_context(name, d, source)


class DictTree(NormalizeMappingMixin, Dict):
    """A dict of dicts. Each key is another dict and each dict has a `.value`
    property that contains the value for that node in the dict tree.

    :example:
        d = DictTree()

        d.set_node(["foo", "bar", "che"], 1)
        d["foo"]["bar"]["che"].value # 1

        d.set_node([], 2) # set a value on the root node
        d.value # 2

    This is the terminology (with tree_ prefix) I'm trying to adhere to:
        https://en.wikipedia.org/wiki/Tree_(data_structure)#Terminology

    Each tree node in the tree has these properties:

    * .parent: DictTree, points to the tree node above this tree, this
        will be None if this is the absolute head tree
    * .key: str, the name of the key this tree is in (so 
        `self == self.parent[self.name]`), this will be None if this
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
    def pathkeys(self) -> Sequence[Hashable]:
        """Get the path of keys from the absolute head tree to this tree"""
        keys = [self.key]
        parent = self
        while parent := parent.parent:
            keys.append(parent.key)
        return list(reversed(keys[:-1]))

    def __init__(self):
        """An instance should be built up specifically using `.set_node` so
        this doesn't support passing in any values by default.

        You should only change passing in any values if you know what you're
        doing because `_create_instance`, which is used to create new nodes
        relies on `__init__` not taking any arguments
        """
        self.root = self
        self.parent = None
        self.key = None
        self.value = None

        super().__init__()

    def update(self, *args, **kwargs):
        raise NotImplementedError()

    def __setitem__(self, *args, **kwargs):
        raise NotImplementedError()

    def setdefault(self, *args, **kwargs):
        raise NotImplementedError()

    def set_node(self, keys: Sequence[Hashable], value: Any):
        """Set value into the last key in keys, creating intermediate/path
        nodes along the way. If the path node already exists then it will
        be left untouched

        :param keys: list[hashable]|hashable, a list of keys or the key you
            want to set value in
        :param value: Any
        """
        if len(keys) > 1:
            key = self._normalize_key(keys[0])
            if key not in self:
                #self.add_node(key, self.create_instance(), None)
                self._add_node(
                    key,
                    self._create_instance(),
                    self._normalize_path_value(key, value),
                )

            super().__getitem__(key).set_node(keys[1:], value)

        else:
            if keys:
                key = self._normalize_key(keys[0])
                value = self._normalize_value(key, value)
                if key not in self:
                    self._add_node(key, self._create_instance(), value)

                else:
                    self._update_node(
                        key,
                        super().__getitem__(key),
                        value
                    )

            else:
                # root of the tree
                self._update_node(
                    self.key,
                    self,
                    self._normalize_value(None, value)
                )

    def _create_instance(self) -> Self:
        """Internal method. Called from .add_node and is only responsible
        for creating an instance of this class.

        The reason this exists is because the __init__ might be customized
        in a child class and so this can also be customized so nothing fails
        and .add_node can be left alone since it sets the node properties

        :returns: DictTree instance
        """
        return type(self)()

    def _add_node(self, key: Hashable, node: Self, value: Any):
        """Add `node` into `self` at `key` with `value`

        .. note:: this is never called for the root node since the root node
            is never added into another node

        :param key: Hashable, already ran through .normalize_key
        :param node: freshly created with .create_instance
        :param value: Any, already ran through .normalize_value
        """
        node.parent = self
        node.key = key
        node.root = self.root
        node.value = value
        super().__setitem__(key, node)

    def _update_node(self, key: Hashable, node: Self, value: Any):
        """Update `node` of `self` at `key` with `value`

        .. note:: this only updates the value of node, the key is only here to
            keep the signature the same as .add_node and self and node can be
            the same node when the root node is being updated

        :param key: Hashable, already ran through .normalize_key
        :param node: the node to update
        :param value: Any, already ran through .normalize_value
        """
        node.value = value

#     def _normalize_key(self, key: Hashable) -> Hashable:
#         """Internal method. Hook that is called right before key is used
#         to access
# 
#         Called on both set and get
# 
#         :param key: Hashable
#         :returns: Hashable
#         """
#         return key

    def _normalize_path_value(self, key: Hashable, value: Any) -> Any:
        """Internal method. Called right before a intermediate/path/waypoint
        value is added while adding a destination value

        Basically, this will be called and then `.add_node(key, value)` with
        the value returned from this method will be called right after

        :parma key: the key the returned value will be set at, this is a
            sub key to the final set of keys that `value` will be set at
        :param value: this is the destination value since sometimes this might
            be useful for creating the waypoint value in child classes
        """
        return None

#     def _normalize_value(self, key: Hashable|None, value: Any) -> Any:
#         """Internal method. Hook that is called right before `value` is set
#         into the node at `key`
# 
#         Called *only* on set
# 
#         :param key: if None then `value` is the root value
#         :param value: Any
#         :returns: Any
#         """
#         return value

    def trees(self, depth: int = -1) -> Generator[tuple[Sequence[Hashable], Self]]:
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

    def leaves(self, depth: int = -1) -> Generator[tuple[Sequence[Hashable], Self]]:
        """Iterate through the leaves in this tree

        A leaf is a node that is at the end of a tree

        :param depth: int, see .trees
        :returns: generator[tuple(list, DictTree)], Index 0 is the path of
            keys.  Index 1 is the value of the leaf node
        """
        for ks, tree in self.trees(depth=depth):
            for k, d in tree.items():
                if not len(d):
                    yield ks + [k], d

    def suffixes(self, keys: Sequence[Hashable]) -> Generator[Self]:
        """Iterate through the leaves that match the passed in suffix keys

        If you had a node at foo->bar->che and another node at baz->bar->che
        and you passed in `["bar", "che"]` then this would yield foo->bar-che
        and then baz->bar->che because they both end with bar->che
        """
        start_i = len(keys) - 1

        for nks, n in self.leaves():
            if nks[start_i:] == keys:
                yield n

    def walk(
        self,
        keys: Iterable[Hashable],
        set_missing: bool = False,
    ) -> Generator[tuple[Iterable[Hashable], Self]]:
        """Walk each node of the tree in keys.

        Basically, if you passed in ["foo", "bar", "che"] it would first
        yield the node at ["foo"], then ["foo", "bar"], and finally the
        node at ["foo", "bar", "che"]

        :param keys: list[str]|str, the path key(s) to walk
        :returns: generator[DictTree]
        """
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
                d = d[k]
                yield ks, d

            else:
                if set_missing:
                    d.set_node([k], None)
                    d = d[k]
                    yield ks, d

                else:
                    raise KeyError(k)

    def nodes(self, depth: int = -1) -> Generator[Self]:
        """Iterate all the rows in depth order, so do the first row of keys,
        then the second row of keys, etc. It's similar to how you would
        recursively iterate a folder, first you do all the files in the
        root folder, then you do all the files of all the folders in the
        root folder, etc.

        :param depth: see .trees
        :returns: each row of nodes starting from the root node and iterating
            all keys of each level of nodes until the leaf nodes
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

    def preorder(self) -> Generator[Any]:
        """preorder traversal - perform first on node itself, then children

        :returns: the value of the node, not the node itself
        """
        yield self.value

        for node in self.values():
            yield from node.preorder()

    def postorder(self) -> Generator[Any]:
        """postorder traversal - perform first on node's children, then the
        node itself

        :returns: the value of the node, not the node itself
        """
        for node in self.values():
            yield from node.postorder()

        yield self.value

