# -*- coding: utf-8 -*-
import inspect
import types
import collections
from collections.abc import (
    Sequence,
)

from ..compat import *
from ..string import NamingConvention
from ..collections.mapping import DictTree
from .. import logging

from .inspect import ReflectClass, ReflectModule
from .path import ReflectName, ReflectPath


logger = logging.getLogger(__name__)


class OrderedSubclasses(list):
    """A list that maintains subclass order where subclasses always come before
    their parents in the list

    Basically, it makes sure all subclasses get placed before the parent class,
    so if you want your ChildClass to be before ParentClass, you would just
    have ChildClass extend ParentClass

    You'd think this would be a niche thing and not worth being in a common
    library but I've actually had to do this exact thing multiple times, so I'm
    finally moving this from Pout and Bang into here so I can standardize it.
    I'll admit me having to do this multiple times might be a quirk of my
    personality and how I solve problems.

    https://docs.python.org/3/tutorial/datastructures.html#more-on-lists
    """

    insert_cutoff_classes = True
    """True if cutoff classes should be included when inserting classes"""

    def __init__(self, cutoff_classes=None, classes=None, **kwargs):
        """
        :param cutoff_classes: tuple[type, ...], you should ignore anything
            before these classes when working out order
        :param classes: list, any classes you want to insert right away
        """
        super().__init__()

        if "insert_cutoff_classes" in kwargs:
            self.insert_cutoff_classes = kwargs["insert_cutoff_classes"]

        self.info = {}
        self.set_cutoff(cutoff_classes)

        if classes:
            self.extend(classes)

    def extend(self, classes):
        for klass in classes:
            self.insert(klass)

    def _insert(self, klass, klass_info):
        """Internal method called from .insert for the klass and all subclasses
        when klass is being inserted

        :param klass: type, the class being inserted
        :param klass_info: dict
            * index: int, klass should be inserted at or before this value in
                order to make sure it comes before all its parents
            * index_name: str, the full classpath of klass
            * child_count: int, how many children this class should start with
                if info is being added
            * in_info: bool, True if klass info is already in .info
            * edge: bool, True if klass is considered an edge class
        """
        if not klass_info["in_info"]:
            self.info[klass_info["index_name"]] = {
                # children should be inserted at least before this index
                "index": klass_info["index"],
                # how many children does klass have
                "child_count": klass_info["child_count"],
            }

            for d_info in klass_info["descendants"]:
                if d_info["in_info"]:
                    self.info[d_info["index_name"]]["child_count"] += 1

            super().insert(klass_info["index"], klass)

    def insert(self, klass, cutoff_classes=None):
        """Insert class into the ordered list

        :param klass: the class to add to the ordered list, this klass will
            come before all its parents in the list (this class and its parents
            will be added to the list up to .cutoff_classes)
        """
        for klass, klass_info in self._subclasses(klass, cutoff_classes):
            self._insert(klass, klass_info)

    def insert_module(self, module, cutoff_classes=None):
        """Insert any classes of module into the list

        :param module: the module to check for subclasses of cutoff_classes
        """
        cutoff_classes = self.get_cutoff(cutoff_classes)

        for name, klass in inspect.getmembers(module, inspect.isclass):
            if self._is_valid_subclass(klass, cutoff_classes):
                self.insert(klass)

    def insert_modules(self, module, cutoff_classes=None):
        """Runs through module and all submodules and inserts all classes
        matching cutoff_classes

        :param module: ModuleType|str, the module or module name (eg "foo.bar")
        :param cutoff_classes: list[type], this will be combined with
            .cutoff_classes
        """
        rm = ReflectModule(module)
        for m in rm.get_modules():
            self.insert_module(m, cutoff_classes)

    def remove(self, klass, cutoff_classes=None):
        """Remove an edge class from the list of classes

        :param klass: type, currently you can only remove an edge class
        """
        rc = ReflectClass(klass)
        index_name = rc.classpath

        if index_name in self.info:
            if self.info[index_name]["child_count"] == 0:
                super().remove(klass)
                info = self.info.pop(index_name)

                subclasses = self._subclasses(klass, cutoff_classes)
                for sc, sc_info in subclasses:
                    if sc_info["index_name"] in self.info:
                        self.info[sc_info["index_name"]]["child_count"] -= 1

                for index_name in self.info.keys():
                    if self.info[index_name]["index"] > info["index"]:
                        self.info[index_name]["index"] -= 1

            else:
                raise TypeError(
                    f"Cannot remove {index_name} because it is not an edge"
                )

        else:
            raise ValueError(f"No {index_name} found")

    def set_cutoff(self, cutoff_classes):
        # make sure we have a tuple of type objects
        if cutoff_classes:
            if not isinstance(cutoff_classes, (Sequence, tuple)):
                cutoff_classes = (cutoff_classes,)

            else:
                cutoff_classes = tuple(cutoff_classes)

        else:
            cutoff_classes = None

        self.cutoff_classes = cutoff_classes

    def get_cutoff(self, cutoff_classes):
        if cutoff_classes:
            if isinstance(cutoff_classes, type):
                cutoff_classes = (cutoff_classes,)

            else:
                cutoff_classes = tuple(cutoff_classes)

        elif self.cutoff_classes:
            cutoff_classes = self.cutoff_classes

        else:
            cutoff_classes = self.default_cutoff()

        return cutoff_classes

    def default_cutoff(self):
        """Turns out, many times when I use this class the cutoff class isn't
        fully defined yet, I've ran into this problem a few times now.

        This attempts to solve that issue by allowing a child class to override
        this method and return the desired cutoff classes

        :returns: tuple[type]
        """
        return (object,)

    def edges(self, **kwargs):
        """Iterate through the absolute children and only the absolute
        children, no intermediate classes.

        :Example:
            class Foo(object): pass
            class Bar(Foo): pass
            class Che(object): pass

            classes = OrderedSubclasses()
            classes.extend([Foo, Bar, Che])

            for c in classes.edges():
                print(c)

            # this would print out Bar and Che because object and Foo are
            # parents

        :param **kwargs:
            - names: bool, True if you want a tuple[str, type] where index 0 is
                the classpath of the edge and index 1 is the actual edge class
        :returns: generator, only the absolute children who are not parents
        """
        names = kwargs.get("names", kwargs.get("name", False))
        for index_name, klass in self.items(edges=True):
            if names:
                yield index_name, klass

            else:
                yield klass

    def items(self, **kwargs):
        """Iterate through all the classes, this is handy because it yields
        tuple[str, type] where index 0 is the ful classpath and index 1 is the
        actual class

        :param **kwargs:
            - edges: bool, True if you only want the edges (absolute children)
                and not all classes
        :returns: generator[tuple[str, type]]
        """
        edges = kwargs.get("edges", kwargs.get("edge", False))
        for klass in self:
            rc = ReflectClass(klass)
            index_name = rc.classpath
            if edges:
                if self.info[index_name]["child_count"] == 0:
                    yield index_name, klass

            else:
                yield index_name, klass

    def _subclasses(self, klass, cutoff_classes=None):
        """Internal method used in both .insert and .remove

        :param klass: type, the class we want to get all the subclasses of
        :returns: generator[type, dict], each item yielded is a tuple of the
            the class object, and information about the class. That means
            the edge (the tuple equivalent to passed in klass) will have a
            child count of 0 and will be the last tuple yielded since we go
            from earliest ancestor to current klass
            """
        ret = []
        klasses = list(self.getmro(klass, cutoff_classes))
        child_count = len(klasses)
        index = len(self)
        descendants = []

        for offset, subclass in enumerate(reversed(klasses), 1):
            rc = ReflectClass(subclass)
            index_name = rc.classpath

            d = {
                "index_name": index_name,
                "child_count": child_count - offset,
                "in_info": index_name in self.info,
                "edge": False,
            }

            if d["in_info"]:
                index = min(index, self.info[index_name]["index"])

            else:
                d["descendants"] = list(descendants)

            d["index"] = index

            if not d["in_info"] and not d["child_count"]:
                d["edge"] = True

            yield subclass, d

            descendants.append(d)

    def _is_valid_subclass(self, klass, cutoff_classes):
        """Return True if klass is a valid subclass that should be iterated
        in ._subclasses

        This is dependent on the value of .insert_cutoff_classes, if it is
        True then True will be returned if klass is a subclass of the cutoff
        classes. If it is False then True will only be returned if klass
        is a subclass and it's not any of the cutoff classes

        :param klass: type, the class to check
        :param cutoff_classes: tuple[type], the cutoff classes returned from
            .get_cutoff
        :returns: bool, True if klass should be yield by ._subclasses
        """
        ret = False
        if issubclass(klass, cutoff_classes):
            ret = True
            if not self.insert_cutoff_classes:
                for cutoff_class in cutoff_classes:
                    if klass is cutoff_class:
                        ret = False
                        break

        return ret

    def getmro(self, klass, cutoff_classes=None):
        """Get the method resolution order of klass taking into account the
        cutoff classes

        :param klass: type, the class to get the method resolution order for
        :param cutoff_classes: tuple[type], the cutoff classes returned from
            .get_cutoff
        :returns: generator[type]
        """
        cutoff_classes = self.get_cutoff(cutoff_classes)
        klasses = inspect.getmro(klass)
        for klass in klasses:
            if self._is_valid_subclass(klass, cutoff_classes):
                yield klass

    def clear(self):
        super().clear()
        self.info = {}

    def append(self, *args, **kwargs):
        raise NotImplementedError()

    def pop(self, *args, **kwargs):
        raise NotImplementedError()

    def sort(self, *args, **kwargs):
        raise NotImplementedError()

    def copy(self, *args, **kwargs):
        raise NotImplementedError()


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

    NOTE -- <MODULE_NAME> is only used if prefixes are passed into the
    instance, if there are no prefixes then the module path is ignored when
    adding classes. This means the path for foo.bar:Che without prefixes would
    just be Che. If prefixes=["foo"] then the path is bar:Che 

    Like OrderedSubclasses, you'd think this would be a niche thing and not
    worth being in a common library but I do this exact thing in both Endpoints
    and Captain and rather than duplicate the code I've moved it here.

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
        self.find_keys = {}
        self.kwargs = kwargs # convenience for default .create_instance
        self.value = self._get_node_default_value(**kwargs)

    def create_instance(self):
        """Internal method that makes sure creating sub-instances of this
        class when creating nodes doesn't error out"""
        return type(self)(
            prefixes=self.prefixes,
            **self.kwargs,
        )

    def add_node(self, key, node, value):
        """override parent to set find keys

        Whenever a new node is created this will be called, it populates
        the .find_keys used in .normalize_key
        """
        super().add_node(key, node, value)

        if key not in self.find_keys:
            self.find_keys[key] = key

            nc = NamingConvention(key)
            for vk in nc.variations():
                self.find_keys[vk] = key

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

    def normalize_key(self, key):
        """override parent to normalize key using .find_keys"""
        return self.find_keys.get(key, key)

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
        return None

    def _get_node_module_info(self, key, **kwargs):
        """Get the module key and value for a node representing a module.

        This is called for each module in the full classpath. So if the
        full classpath was `foo.bar:Che.Baz` then this would be called for
        `foo` and `bar`

        :param key: Hashable
        :param **kwargs:
            * module: types.ModuleType, the module
        :returns: tuple[hashable|None, dict], index 0 is the key in the
            tree, no key will be added if it is `None`, index 1 is the value
            at that key in the tree
        """
        value = self._get_node_default_value(**kwargs) or {}
        value["module"] = kwargs["module"]
        return key, value

    def _get_node_class_info(self, key, **kwargs):
        """Get the key and value for a node representing a class

        This is called for each class in the full classpath. So if the
        full classpath was `foo.bar:Che.Baz` then this would be called for
        `Che` and `Baz`

        :param key: Hashable
        :param **kwargs:
            * class_name: str, this class name, this will always be there
            * class: type, this will only be here on the final class
            * module_keys: list[str], a list of all the keys used for the
                module portion of the path
            * class_keys: list[str], a list of all the keys used for the
                class portion of the path
        :returns: tuple[hashable|None, dict], index 0 is the key in the
            tree, no key will be added if it is `None`, index 1 is the value
            at that key in the tree, the keys it can have:
                * class: this will be set for the final absolute class of the
                    path
                * class_name: this will always be set
        """
        value = self._get_node_default_value(**kwargs) or {}

        value["class_name"] = kwargs["class_name"]

        if "class" in kwargs:
            for k in ["class", "module_keys", "class_keys"]:
                value[k] = kwargs[k]

            if key is not None:
                value["class_keys"] = kwargs["class_keys"] + [key]

        return key, value

    def _get_node_items(self, klass):
        """Internal method. This yields the keys and values that will be
        used to create new nodes in this tree

        This is called for each value in the full classpath. So if the
        full classpath was `foo.bar:Che.Baz` then this would yield `foo`,
        `bar`, `Che`, and `Baz`

        :returns: generator[tuple(list[str], Any)], the keys and value for
            a node in the tree. Index 0 contains the key from root to the
            node. Index 1 contains the value at that node, by default that
            value is a dict which will contain the value returned from either
            `._get_node_module_info`
        """
        rn = ReflectName(self._get_classpath(klass))

        module_keys = []
        class_keys = []

        # these values are added to and passed into the child
        # `._get_node_*_info` methods
        nkwargs = {
            "keys": [],
            "module_keys": [],
            "modules": [],
            "class_keys": [],
        }

        for prefix in self.prefixes:
            if rn.is_module_relative_to(prefix):
                if modname := rn.relative_module_name(prefix):
                    for rm in rn.reflect_modules(modname):
                        m = rm.get_module()
                        k, v = self._get_node_module_info(
                            rm.module_basename,
                            module=m,
                            **nkwargs
                        )
                        if k is not None:
                            nkwargs["keys"].append(k)
                            nkwargs["module_keys"].append(k)
                            nkwargs["modules"].append(m)

                        yield nkwargs["keys"], v

                break

        # we can't use rn.get_classes() here because classpath could be
        # something like: `<run_path>:ClassPrefix.ClassName` and so we can't
        # actually get the module because `<run_path>` doesn't exist anywhere
        # or `ClassPrefix`, we basically only have access to `klass`
        # because it was passed in, and it corresponds to `ClassName`
        class_names = rn.class_names
        class_i = len(class_names) - 1
        for i, class_name in enumerate(class_names):
            nkwargs["class_name"] = class_name

            if class_i == i:
                nkwargs["class"] = klass

            k, v = self._get_node_class_info(
                class_name,
                **nkwargs
            )
            if k is not None:
                nkwargs["keys"].append(k)
                nkwargs["class_keys"].append(k)

            yield nkwargs["keys"], v

    def add_class(self, klass):
        """This is the method that should be used to add new classes to the
        tree

        :param klass: type, the class to add to the tree
        """
        for keys, value in self._get_node_items(klass):
            self.set(keys, value)

    def add_classes(self, classes):
        """Adds all the classes using .add_class"""
        for klass in classes:
            self.add_class(klass)

    def get_class_items(self):
        """go through and return destination nodes keys and values"""
        for keys, node in self.nodes():
            if node.value and "class" in node.value:
                yield keys, node.value


class ClassFinder(BaseClassFinder):
    """Keep a a class hierarchy tree so subclasses can be easily looked up
    from a common parent

    This is very similar to OrderedSubclasses but is a conceptually better
    data structure for this type of class organization

    See also:
        * inspect.getclasstree()
    """
    cutoff_class = None

    def set_cutoff_class(self, cutoff_class: type):
        self.cutoff_class = cutoff_class

    def _get_node_items(self, klass: type):
        keys = []
        for c in reversed(inspect.getmro(klass)):
            if self._is_valid_subclass(c):
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

    def find_class_node(self, klass: type):
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

    def get_abs_class(self, klass: type, *default):
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

    def get_abs_classes(self, klass: type):
        """Get the absolute edge subclasses of klass

        :Example:
            # these were added to ClassFinder instance cf
            class GP(object): pass
            class P(GP): pass
            class C1(P): pass
            class C2(P): pass
            class C3(C1): pass

            list(cf.get_abs_classes(GP)) # [<type 'C2'>, <type 'C3'>]

        :param klass: type, the parent class whose absolute children that
            extend it we want
        :returns: generator[type], the found absolute subclasses of klass
        """
        try:
            n = self.find_class_node(klass)
            if len(n) == 0:
                yield klass

            else:
                for k in n.keys():
                    yield from n.get_abs_classes(k)

        except KeyError:
            pass


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
    def get_class_key(self, klass):
        """Uses `klass` to produce a string class key that can be passed to
        `.find_class` to get klass back

        :param klass: type
        :returns: str, the class key, by default "<CLASSNAME>_class" all
            lower case
        """
        return f"{NamingConvention(klass.__name__).varname()}_class"

    def add_node(self, klass, node, value):
        super().add_node(klass, node, value)

        # this is the first time the root node is adding a node, so do some
        # initialization
        if not self.parent and len(self) == 1:
            self.class_keys = {}

        class_key = self.get_class_key(klass)
        self.root.class_keys[class_key] = klass

    def find_class(self, class_key):
        """Returns the class (type instance) found at `class_key`

        :param class_key: str
        :returns: type
        """
        return self.root.class_keys[class_key]


class Extend(object):
    """you can use this decorator to extend instances with custom functionality

    Moved from bang.event.Extend on 1-18-2023

    :Example:
        extend = Extend()

        class Foo(object): pass

        @extend(Foo, "bar")
        def bar(self, n1, n2):
            return n1 + n2

        f = Foo()
        f.bar(1, 2) # 3

        @extend(f, "che")
        @property
        def che(self):
            return 42

        f.che # 42
    """
    def property(self, o, name):
        """decorator to extend o with a property at name

        Using this property method is equivalent to:
            @extend(o, "NAME")
            @property
            def name(self):
                return 42

        :param o: instance|class, the object being extended
        :param name: string, the name of the property
        :returns: callable wrapper
        """
        def wrap(callback):
            if inspect.isclass(o):
                self.patch_class(o, name, property(callback))

            else:
                #self.patch_class(o.__class__, name, property(callback))
                self.patch_instance(o, name, property(callback))

            return callback
        return wrap

    def method(self, o, name):
        """decorator to extend o with method name

        :param o: instance|class, the object being extended
        :param name: string, the name of the method
        :returns: callable wrapper
        """
        return self(o, name)

    def __call__(self, o, name):
        """shortcut to using .property() or .method() decorators"""
        def wrap(callback):
            if inspect.isclass(o):
                self.patch_class(o, name, callback)

            else:
                self.patch_instance(o, name, callback)

            return callback
        return wrap

    def patch_class(self, o, name, callback):
        """internal method that patches a class o with a callback at name"""
        setattr(o, name, callback)

    def patch_instance(self, o, name, callback):
        """internal method that patches an instance o with a callback at name
        """
        if isinstance(callback, property):
            setattr(o.__class__, name, callback)
        else:
            setattr(o, name, types.MethodType(callback, o))

