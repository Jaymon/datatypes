# -*- coding: utf-8 -*-
import inspect
import types
import collections
from collections.abc import (
    Sequence,
    Generator,
    Mapping,
    Iterable,
)

from ..compat import *
from ..string import NamingConvention
from ..collections.mapping import DictTree
from .. import logging


logger = logging.getLogger(__name__)


class BaseClassFinder(DictTree):
    @classmethod
    def find_modules(cls, prefixes=None, paths=None, fileroot=""):
        """Tries to find modules to pass into .__init__ by first checking
        prefixes, then paths using fileroot if applicable

        :param prefixes: see .get_prefix_modules
        :param paths: see .get_path_modules
        :param fileroot: see .get_path_modules
        :returns: see .get_prefix_modules return value
        """
        modules = {}

        if prefixes:
            modules = cls.get_prefix_modules(prefixes)

        elif paths:
            modules = cls.get_path_modules(
                paths,
                fileroot
            )

        return modules

    @classmethod
    def get_prefix_modules(cls, prefixes, **kwargs):
        """Given a set of prefixes, find all the modules

        This is a helper method that finds all the modules for further
        processing or calls some class's .__init_subclass__ method when the
        module is loaded

        :param prefixes: iterator[str], module prefixes are basically module
            paths (eg, "foo.bar")
        :returns: dict[str, dict[str, types.ModuleType]], the top-level keys
            are the prefixes, the value is a dict with module path keys and
            the module found at the end of that module path
        """
        # avoid circular dependency
        from .inspect import ReflectModule

        modules = collections.defaultdict(dict)
        seen = set()
        prefixes = prefixes or []

        for prefix in prefixes:
            logger.debug(f"Checking prefix: {prefix}")
            rm = ReflectModule(prefix)
            for m in rm.get_modules():
                if m.__name__ not in seen:
                    logger.debug(f"Found prefix module: {m.__name__}")
                    modules[prefix][m.__name__] = m
                    seen.add(m.__name__)

        return modules

    @classmethod
    def get_path_modules(cls, paths, fileroot="", **kwargs):
        """Given a set of paths, find all the modules

        This is a helper method that finds all the modules for further
        processing or calls some class's .__init_subclass__ method when the
        module is loaded

        :param paths: iterator[str|Path], if a path is a directory then
            `fileroot` is needed to search the directory for matching modules,
            if the path is a file then it is loaded as a python module
        :param fileroot: see `fileroot` in `ReflectPath.find_modules`
        :returns: see .get_prefix_modules since it's the same value
        """
        # avoid circular dependency
        from .path import ReflectName, ReflectPath

        modules = collections.defaultdict(dict)
        seen = set()
        paths = paths or []

        for path in paths:
            logger.debug(f"Checking path: {path}")
            rp = ReflectPath(path)
            if rp.is_dir():
                if fileroot:
                    for m in rp.find_modules(fileroot):
                        if m.__name__ not in seen:
                            rn = ReflectName(m.__name__)
                            prefix = rn.absolute_module_name(fileroot)

                            logger.debug(
                                f"Found dir module: {m.__name__}"
                                f" with prefix: {prefix}"
                            )

                            modules[prefix][m.__name__] = m
                            seen.add(m.__name__)

            else:
                if m := rp.get_module():
                    if m.__name__ not in seen:
                        logger.debug(f"Found file module: {m.__name__}")
                        modules[""][m.__name__] = m
                        seen.add(m.__name__)

        return modules


class ClasspathFinder(BaseClassFinder):
    """Create a tree of the full classpath (<MODULE_NAME>:<QUALNAME>) of
    a class added with .add_class

    .. note:: <MODULE_NAME> is only used if prefixes are passed into the
    instance, if there are no prefixes then the module path is ignored when
    adding classes. This means the path for foo.bar:Che without prefixes would
    just be Che. If prefixes=["foo"] then the path is bar:Che 

    You'd think this would be a niche thing and not worth being in a common
    library but I do this exact thing in both Endpoints and Captain and rather
    than duplicate the code I've moved it here.

    This code is based on similar code in Captain. I moved it here on 
    August 29, 2024. The Captain code was based on similar code from Endpoints
    and was my second stab at solving this problem, so this codebase is my
    third stab at the problem. I've now integrated this version back into
    Endpoints. So the circle of life continues
    """
    def __init__(self, prefixes=None, **kwargs):
        """
        :param prefixes: list[str], passing in prefixes means the <MODULE-NAME>
            will be used when adding the classpaths, if there are no prefixes
            then the <MODULE-NAME> portion of a full class path (eg,
            <MODULE-NAME>:<CLASS-QUALNAME>) will be ignored and only the
            <CLASS-QUALNAME> will be used
        """
        super().__init__()

        self.prefixes = prefixes or set()
        self.kwargs = kwargs # convenience for default .create_instance
        self.value = self._get_node_default_value(**kwargs)

    def create_instance(self):
        """Internal method that makes sure creating sub-instances of this
        class when creating nodes doesn't error out"""
        return type(self)(
            prefixes=self.prefixes,
            **self.kwargs,
        )

    def update_node(self, key, node, value):
        """Update the node only if value has a class (meaning it's a
        destination value and not a waypoint value) or node doesn't already
        have a value

        Because of how ._get_node_items works, the parent nodes can be updated
        multiple times as paths are added, but we don't want final paths
        (paths that end with a class) to be overwritten later by route paths
        (not final paths but just a waypoint towards our final destination).
        """
        if not node.value or "class" in value:
            super().update_node(key, node, value)

    def _get_classpath(self, klass):
        """Internal method. Get the classpath (<MODULE_NAME>:<CLASS_QUALNAME>)
        for klass"""
        if "<" in klass.__qualname__:
            raise ValueError(
                f"{klass.__qualname__} is programmatically inaccessible"
            )

        return f"{klass.__module__}:{klass.__qualname__}"

    def _get_node_default_value(self, **kwargs):
        """Get the default value for the node on creation

        :returns: Any
        """
        return {}

    def _get_node_module_info(self, key, **kwargs):
        """Get the module key and value for a node representing a module.

        This is called for each module in the full classpath. So if the
        full classpath was `foo.bar:Che.Baz` then this would be called for
        `foo` and `bar`

        :param key: Hashable
        :keyword module: types.ModuleType, the module
        :keyword module_name: str, the current module name
        :returns: tuple[hashable|None, dict], index 0 is the key in the
            tree, no key will be added if it is `None`, index 1 is the value
            at that key in the tree
        """
        value = self._get_node_default_value(**kwargs)
        value.update(kwargs)
        value.pop("reflect_name", None)
        return key, value

    def _get_node_class_info(self, key, **kwargs):
        """Get the key and value for a node representing a class

        This is called for each class in the full classpath. So if the
        full classpath was `foo.bar:Che.Baz` then this would be called for
        `Che` and `Baz`

        :param key: Hashable
        :keyword module_name: str, the current module name
        :keyword class_name: str, this class name, this will always be there
        :keyword class: type, this will only be here on the final class
        :keyword module_keys: list[str], a list of all the keys used for the
            module portion of the path
        :keyword class_keys: list[str], a list of all the keys used for the
            class portion of the path
        :returns: tuple[hashable|None, dict], index 0 is the key in the
            tree, no key will be added if it is `None`, index 1 is the value
            at that key in the tree, the keys it can have:
                * class: this will be set for the final absolute class of the
                    path
                * class_name: this will always be set
        """
        value = self._get_node_default_value(**kwargs)
        value.update(kwargs)
        value.pop("reflect_name", None)
        return key, value

    def _get_node_module_items(
        self,
        klass: type,
        **kwargs
    ) -> Generator[list[str], Mapping, Mapping]:
        """Internal method for this class. This will generate all the module
        nodes for `klass` and is called from `._get_node_path_items`

        This will only generate nodes if `.prefixes` is not empty and will
        only generate a node if the node's module path matches a prefix

        :returns: a generator of keys, value, and the latest kwargs
        """
        rn = kwargs["reflect_name"]
        for prefix in self.prefixes:
            if rn.is_module_relative_to(prefix):
                if modname := rn.relative_module_name(prefix):
                    for rm in rn.reflect_modules(modname):
                        m = rm.get_module()

                        kwargs["module_name"] = m.__name__

                        k, v = self._get_node_module_info(
                            rm.module_basename,
                            module=m,
                            **kwargs,
                        )
                        if k is not None:
                            for vk in ["keys", "module_keys"]:
                                kwargs[vk].append(k)
                                v[vk] = kwargs[vk][:]

                        kwargs["modules"].append(m)
                        v["modules"] = kwargs["modules"][:]
                        v["class_keys"] = []

                        yield kwargs["keys"], v, kwargs

                break

    def _get_node_class_items(
        self,
        klass: type,
        **kwargs,
    ) -> Generator[list[str], Mapping, Mapping]:
        """Internal method for this class. This will generate all the class
        nodes for `klass` and is called from `._get_node_path_items`

        :returns: a generator of keys, value, and the latest kwargs
        """
        rn = kwargs["reflect_name"]

        # we can't use rn.get_classes() here because classpath could be
        # something like: `<run_path>:ClassPrefix.ClassName` and so we can't
        # actually get the module because `<run_path>` doesn't exist anywhere
        # or `ClassPrefix`, we basically only have access to `klass`
        # because it was passed in, and it corresponds to `ClassName`
        class_names = rn.qualnames
        class_i = len(class_names) - 1
        for i, class_name in enumerate(class_names):
            kwargs["class_name"] = class_name

            if i == class_i:
                kwargs["class"] = klass

            k, v = self._get_node_class_info(class_name, **kwargs)

            if k is not None:
                for vk in ["keys", "class_keys"]:
                    kwargs[vk].append(k)
                    v[vk] = kwargs[vk][:]

            v["module_keys"] = kwargs["module_keys"][:]
            v["modules"] = kwargs["modules"][:]

            yield kwargs["keys"], v, kwargs

    def _get_node_path_items(
        self,
        klass: type,
        **kwargs,
    ) -> Generator[list[str], Mapping, Mapping]:
        """Internal method for this class. This will generate all the path
        nodes for `klass`

        :returns: a generator of keys, value, and the latest kwargs
        """
        # can't use `yield from` because kwargs can build on each other so we
        # need to capture it
        for k, v, kwargs in self._get_node_module_items(klass, **kwargs):
            yield k, v, kwargs

        for k, v, kwargs in self._get_node_class_items(klass, **kwargs):
            yield k, v, kwargs

    def _get_node_items(self, klass: type) -> Generator[list[str], Mapping]:
        """Internal method for parent. This yields the keys and values that
        will be used to create new nodes in this tree

        If there are `.prefixes` then this is called for each value in the full
        classpath. So if the full classpath was `foo.bar:Che.Baz` then this
        would yield `foo`, `bar`, `Che`, and `Baz`. If there are no `.prefixes`
        then this will be called with just `CHe` and `Baz`

        :returns: a generator of keys and value for a node in the tree. Index 0
            contains the key from root to the node. Index 1 contains the value
            at that node, by default that value is a dict which will contain
            the value returned from either `._get_node_module_info`
        """
        # avoid circular dependency
        from .path import ReflectName

        rn = ReflectName(self._get_classpath(klass))

        # these values are added to and passed into the child
        # `._get_node_*_info` methods. These are updated each iteration and
        # shallow copied into the node value by default (see
        # `._get_node_default_value`). That means, for the most part, you
        # shouldn't touch these keys but children classes can add keys to
        # the value
        kwargs = {
            "keys": [],
            "module_keys": [],
            "modules": [],
            "class_keys": [],
            "reflect_name": rn,
        }
        for keys, value, kwargs in self._get_node_path_items(klass, **kwargs):
            yield keys, value

    def add_class(self, klass: type):
        """This is the method that should be used to add new classes to the
        tree

        :param klass: type, the class to add to the tree
        """
        for keys, value in self._get_node_items(klass):
            self.set(keys, value)

    def add_classes(self, classes: Iterable[type]):
        """Adds all the classes using .add_class"""
        for klass in classes:
            self.add_class(klass)

    def get_class_items(self) -> tuple[list[str], Mapping]:
        """go through and return destination nodes keys and values"""
        for keys, node in self.nodes():
            if node.value and "class" in node.value:
                yield keys, node.value

    def find_class_node(self, klass: type) -> Mapping:
        """return klass's node in the tree

        .. note:: Unlike `ClassFinder`, a class isn't guarranteed to be
            unique in this tree, and this method returns the first matching
            class, not all matching classes

        :param klass: type
        :returns: ClasspathFinder
        """
        for keys, node in self.nodes():
            if node.value and "class" in node.value:
                if node.value["class"] is klass:
                    return node

        raise KeyError(f"{klass} not found in tree")


class MethodpathFinder(ClasspathFinder):
    """Create a tree of the full callpath 
    (<MODULE_NAME>:<QUALNAME>.<METHOD_NAME>) of a class added with .add_class
    """
    def _get_node_path_items(
        self,
        klass: type,
        **kwargs,
    ) -> Generator[list[str], Mapping, Mapping]:
        """Internal method of parent. Overloaded to also yield methods"""
        path_node_items = super()._get_node_path_items(klass, **kwargs)
        for keys, value, kwargs in path_node_items:
            kwargs["method_keys"] = []
            yield keys, value, kwargs

        yield from self._get_node_method_items(klass, **kwargs)

    def _get_node_method_items(
        self,
        klass: type,
        **kwargs,
    ) -> Generator[list[str], Mapping, Mapping]:
        """Internal method of this class. This yields all the method nodes
        that should be added to the tree

        This method is similar to `._get_node_module_items` and
        `._get_node_class_items` from parent
        """
        methods = inspect.getmembers(klass, callable)
        for method_name, method in methods:
            k, v = self._get_node_method_info(
                method_name,
                method_name=method_name,
                method=method,
                **kwargs,
            )
            if v is not None:
                if k is not None:
                    v["keys"] = [*kwargs["keys"], k]
                    v["method_keys"] = [k]

                for vk in ["module_keys", "modules", "class_keys"]:
                    v[vk] = kwargs[vk][:]

                yield v["keys"], v, kwargs

    def _get_node_method_info(
        self,
        key: str,
        **kwargs,
    ) -> tuple[str|None, Mapping|None]:
        """Internal method to the class. This is similar to
        `._get_node_module_info` and `._get_node_class_info`.

        If the key is None then it won't move to a new node in the tree and
        will overwrite the previous key, if value is None then this info
        won't even be yielded
        """
        if key.startswith("_"):
            return None, None

        value = self._get_node_default_value(**kwargs)
        value.update(kwargs)
        value.pop("reflect_name", None)
        return key, value


class ClassFinder(BaseClassFinder):
    """Keep a a class hierarchy tree so subclasses can be easily looked up
    from a common parent

    See also:
        * inspect.getclasstree()
    """
    cutoff_class = None

    def set_cutoff_class(self, cutoff_class: type):
        self.cutoff_class = cutoff_class

    def _get_node_items(self, klass: type):
        keys = []
        for c in self.getmro(klass, reverse=True):
            keys.append(c)
            yield keys, c

    def _is_valid_subclass(self, klass: type, cutoff_class=None):
        """Internal method. check if klass should be considered a valid
        subclass for addition into the tree

        This is a hook to allow child classes to customize functionality

        :param klass: type, the class wanting to be added to the tree
        :param cutoff_class: type, anything before this class will be ignored
        :returns: bool, True if klass is valid
        """
        if cutoff_class is None:
            cutoff_class = self.cutoff_class

        if cutoff_class is None:
            return True

        else:
            return (
                issubclass(klass, cutoff_class)
                and klass is not cutoff_class
            )

    def add_class(self, klass: type):
        """This is the method that should be used to add new classes to the
        tree

        :param klass: type, the class to add to the tree
        """
        for keys, value in self._get_node_items(klass):
            self.set(keys, value)

    def add_classes(self, classes: Sequence[type]):
        """Adds all the classes using .add_class"""
        for klass in classes:
            self.add_class(klass)

    def delete_class(self, klass: type):
        """Remove edge class `klass`"""
        n = self.find_class_node(klass)
        if n:
            raise TypeError(
                f"Cannot remove {klass} because it is not a leaf/edge"
            )

        else:
            del n.parent[klass]

    def delete_mro(self, klass: type):
        """This prunes or trims the tree from `klass` down, any tree that only
        is an ancestor to `klass` and nothing else will be pruned. So if a tree
        has more "branches" that is where the pruning will stop
        """
        n = self.find_class_node(klass)
        while True:
            np = n.parent
            if np is None:
                break

            if len(np) > 1:
                break

            else:
                n = np

        if n.key is None:
            # root node
            n.clear()

        else:
            del n.parent[n.key]

    def getmro(self, klass: type, reverse: bool = False) -> Generator[type]:
        """Get the method resolution order of klass taking into account the
        cutoff classes

        :param klass: type, the class to get the method resolution order for
        :param reverse: reverse the order
        :returns: all the classes
        """
        klasses = inspect.getmro(klass)

        if reverse:
            klasses = reversed(klasses)

        for klass in klasses:
            if self._is_valid_subclass(klass):
                yield klass

    def find_class_node(self, klass: type) -> Mapping:
        """return klass's node in the tree

        This is different than `.get_node` because it's not a straight
        lookup like `.get_node` but will actually find the class in the
        tree

        :param klass: type
        :returns: ClassFinder
        """
        if self.key is klass:
            return self

        else:
            for _, n in self.nodes():
                if klass in n:
                    return n.get_node(klass)

        raise KeyError(f"{klass} not found in tree")

    def get_abs_class(self, klass: type, *default) -> type:
        """Get the absolute edge subclass of klass

        :Example:
            # these were added to ClassFinder instance cf
            class GP(object): pass
            class P(GP): pass
            class C(P): pass

            cf.get_abs_class(P) # <type 'C'>

        :param klass: type, the class to find the absolute child that extends
            klass
        :param *default: Any, return this instead of raising an exception
            if the absolute class can't be inferred
        :returns: type, the found subclass
        :raises: ValueError, if an absolute child can't be inferred
        """
        try:
            n = self.find_class_node(klass)
            child_count = len(n)
            if child_count == 0:
                return n.key

            elif child_count == 1:
                for k in n.keys():
                    return n.get_abs_class(k)

            else:
                raise ValueError(
                    f"Cannot find absolute class because {klass} has"
                    " multiple children"
                )

        except (ValueError, KeyError):
            if default:
                return default[0]

            else:
                raise

    def get_abs_classes(self, klass: type|None = None) -> Generator[type]:
        """Get the absolute edge subclasses of klass

        :Example:
            # these were added to ClassFinder instance cf
            class GP(object): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class C3(C1): pass

            list(cf.get_abs_classes(GP)) # [<type 'C2'>, <type 'C3'>]

        :param klass: the parent class whose absolute children that
            extend it we want. If klass isn't passed in then it will yield
            all absolute subclasses
        :returns: the found absolute subclasses of klass
        """
        if klass is None:
            yield from (t[1].key for t in self.leaves())

        else:
            try:
                n = self.find_class_node(klass)
                if len(n) == 0:
                    yield klass

                else:
                    for k in n.keys():
                        yield from n.get_abs_classes(k)

            except KeyError:
                pass

    def get_mro_classes(self, klass: type|None = None) -> Generator[type]:
        """Get all the classes in method resolution order (mro)

        Children will always come before parents. This does not guarrantee
        the classes will be in mro order for any specific class, only that
        the order will always have children before any of their parents

        Perform a postorder traversal of the tree, this makes sure
        all classes are returned in an order guarranteeing no parents
        appear before their children, this is handy to get the ordered
        subclasses

        This functionality is equivalent to the OrderedSubclasses class
        that was removed on 2025-10-22. This yields subclasses in an order
        where subclasses always come before their parents

        You'd think this would be a niche thing and not worth being in a
        common library but I've actually had to do this exact thing
        multiple times

        :param klass: the parent class, the tree will be postordered traversed
            with nothing before this class yielded
        :returns: the found classes with children appearing before parents
        """
        if klass is None:
            if len(self) > 0:
                for v in self.values():
                    yield from v.get_mro_classes()

                if self.key:
                    yield self.key

            else:
                if self.key:
                    yield self.key

        else:
            try:
                n = self.find_class_node(klass)
                yield from n.get_mro_classes()

            except KeyError:
                pass

    def get_subclasses(self, klass: type) -> Generator[type]:
        """walk all the subclasses of `klass`, the yielded values will
        not include `klass`"""
        try:
            if node := self.find_class_node(klass):
                for k, sn in node.nodes():
                    if k:
                        yield sn.key

        except KeyError:
            pass

    def find_best_subclass(self, call_class: type, klass: type) -> type:
        """Find the best matching subclass of `klass` for `call_class`

        This finds the best subclass to use for `klass` based on proximity
        to the calling `call_class`

        The algo is pretty simple here, it will basically look for a subclass
        defined in the same module as `call_class`, if nothing is found
        it will check all the parents of `call_class` and see if there is a
        subclass of `klass` defined in those modules. If all else fails,
        then consider `klass` as the best matching subclass

        :param call_class: the class that is asking for the best subclass
        :param klass: the class being asked for, the best subclass, defined
            as the closest to proximity to `call_class` will be returned
        """
        subclasses = []
        for sc in self.get_subclasses(klass):
            if sc.__module__ == call_class.__module__:
                return sc

            subclasses.append(sc)

        for parent_class in self.getmro(call_class):
            for sc in subclasses:
                if sc.__module__ == parent_class.__module__:
                    return sc

        return klass


class ClassKeyFinder(ClassFinder):
    """ClassFinder that can find via "<CLASSNAME>_class" keys

    :example:
        class Foo(object): pass
        class FooBar(Foo): pass

        cf = ClassKeyFinder()
        cf.add_classes([Foo, FooBar])
        cf.find_class("foo_bar_class") # FooBar
        cf.find_class("foo_class") # Foo
    """
    def get_class_keys(self, klass):
        """Uses `klass` to produce string class keys that can be passed to
        `.find_class` to get klass back

        :param klass: type
        :returns: list[str], the class keys, by default a list with 
            "<CLASSNAME>_class" all lower case
        """
        return [f"{NamingConvention(klass.__name__).varname()}_class"]

    def add_node(self, klass, node, value):
        super().add_node(klass, node, value)

        # this is the first time the root node is adding a node, so do some
        # initialization
        if not self.parent and len(self) == 1:
            self.class_keys = {}

        #class_key = self.get_class_key(klass)
        for class_key in self.get_class_keys(klass):
            self.root.class_keys[class_key] = klass

    def find_class(self, class_key: str) -> type:
        """Returns the class (type instance) found at `class_key`"""
        try:
            return self.root.class_keys[class_key]

        except AttributeError as e:
            raise KeyError(class_key) from e

    def get_class(self, class_key: str) -> type:
        """Alias for `.find_class` since all the other methods that return
        classes start with `.get_` except `.find_class`. I know why I called
        it that because it uses the `.root` property, but it still felt
        strange using `.find_class` for a single class and then using
        `.get_*` for everything else"""
        return self.find_class(class_key)

    def __contains__(self, class_key_or_klass):
        if isinstance(class_key_or_klass, str):
            try:
                return class_key_or_klass in self.root.class_keys

            except AttributeError:
                return False

        else:
            return super().__contains__(class_key_or_klass)

    def getmro(self, class_key_or_klass, reverse: bool = False):
        """Get the method resolution order of klass taking into account the
        cutoff classes

        :param klass: type, the class to get the method resolution order for
        :param cutoff_classes: tuple[type], the cutoff classes returned from
            .get_cutoff
        :returns: generator[type]
        """
        if isinstance(class_key_or_klass, str):
            klass = self.find_class(class_key_or_klass)

        else:
            klass = class_key_or_klass

        yield from super().getmro(klass, reverse)

