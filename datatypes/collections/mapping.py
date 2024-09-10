# -*- coding: utf-8 -*-
"""
Dict and Map like objects

https://docs.python.org/3/library/collections.abc.html#collections.abc.Mapping
"""
from contextlib import contextmanager

from ..compat import *
from .sequence import PriorityQueue, Stack


class Pool(dict):
    """Generic pool of some values bounded by size, this means when size is
    reached then the least used item will be silently dropped from the pool.

    This class gets interesting when you extend it and add __missing__() so you
    can use this as kind of a hotcache of the maxsize most used items in the
    Pool

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
        if none of the keys exist then return default, all keys in the keys list
        will be popped, even the ones after a value is found

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


class NormalizeDict(Dict):
    """A normalizing dictionary, taken from herd.utils.NormalizeDict

    You can override the .normalize_key and .normalize_value methods, which get
    called anytime you set/get a value. You can check out the idict class for
    an implementation that uses those methods to allow case-insensitive keys
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


class idict(NormalizeDict):
    """A case insensitive dictionary, adapted from herd.utils.NormalizeDict,
    naming convention is meant to mimic python's use of i* for case-insensitive
    functions and python's built-in dict class (which is why the classname is
    all lowercase)"""
    def __init__(self, *args, **kwargs):
        self.ikeys = {} # hold mappings from normalized keys to the actual key
        super().__init__(*args, **kwargs)

    def normalize_key(self, k):
        nk = k.lower()
        if nk in self.ikeys:
            k = self.ikeys[nk]
        self.ikeys[nk] = k
        return k


class NamespaceMixin(object):
    def __setattr__(self, k, v):
        if k.startswith("__"):
            return super().__setitem__(k, v)

        else:
            return self.__setitem__(k, v)

    def __getattr__(self, k):
        if k.startswith("__"):
            return super().__getattr__(k)

        else:
            try:
                return self.__getitem__(k)

            except KeyError as e:
                raise AttributeError(e) from e

    def __delattr__(self, k):
        if k.startswith("__"):
            return super().__delitem__(k)

        else:
            return self.__delitem__(k)


class Namespace(NamespaceMixin, NormalizeDict):
    """Allows both dictionary syntax (eg foo["keyname"]) and object syntax
    (eg foo.keyname)
    """
    pass


class ContextNamespace(Namespace):
    """A context aware namespace where you can override values in later
    contexts and then revert back to the original context when the with
    statement is done

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
            "foo" in n.foo # True

        n.foo # 1
    """
    context_class = Namespace
    """Each context will be an instance of this class"""

    def __init__(self, name="", cascade=True):
        """
        :param name: str, If you want to customize the default context name
        then pass it in
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
        """yield all the _context_names taking into account the cascade setting
        """
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
        """Pop works a little differently than other key access methods, pop
        will only return a value if it is actually in the current context, if k
        is not in the current context then this will return default. It does
        this because it would violate the principal of least surprise if popping
        something in the current context actually popped it from a previous
        context
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


class DictTree(Dict):
    """A dict/tree hybrid, what that means is you can pass in a list of keys
    and it will create sub DictTrees at each key so you can nest values. This
    could also be called a NestingDict, hierarchyDict, or something like that

    https://github.com/Jaymon/datatypes/issues/29

    :Example:
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

