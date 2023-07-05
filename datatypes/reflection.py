# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import inspect
import sys
import types
import functools
import os
import importlib
import ast
import collections
import pkgutil

from .compat import *
from .decorators import property as cachedproperty
from .string import String
from .path import Dirpath


class OrderedSubclasses(list):
    """A list that maintains subclass order where subclasses always come before
    their parents in the list

    Basically, it makes sure all subclasses get placed before the parent class,
    so if you want your ChildClass to be before ParentClass, you would just have
    ChildClass extend ParentClass

    You'd think this would be a niche thing and not worth being in a common library
    but I've actually had to do this exact thing multiple times, so I'm finally
    moving this from Pout and Bang into here so I can standardize it
    """
    def __init__(self, cutoff_classes=None, classes=None):
        """
        :param cutoff_classes: [type, ...], you should ignore anything before these
            classes when working out order
        :param classes: list, any classes you want to insert right away
        """
        super().__init__()

        self.info = {}

        # make sure we have a tuple of type objects
        if cutoff_classes:
            if not isinstance(cutoff_classes, (Sequence, tuple)):
                cutoff_classes = (cutoff_classes,)
            else:
                cutoff_classes = tuple(cutoff_classes)
        else:
            cutoff_classes = (object,)

        self.cutoff_classes = cutoff_classes

        if classes:
            self.extend(classes)

    def extend(self, classes):
        for klass in classes:
            self.insert(klass)

    def insert(self, klass):
        """Insert class into the ordered list

        :param klass: the class to add to the ordered list, this klass will come
            before all its parents in the list (this class and its parents will
            be added to the list up to .cutoff_classes)
        """
        index = len(self)
        cutoff_classes = self.cutoff_classes
        klasses = inspect.getmro(klass)

        for offset, subclass in enumerate(reversed(klasses), 1):
            if issubclass(subclass, cutoff_classes):
                rc = ReflectClass(subclass)
                index_name = rc.classpath
                if index_name in self.info:
                    self.info[index_name]["child_count"] += 1
                    index = min(index, self.info[index_name]["index"])

                else:
                    self.info[index_name] = {
                        "index": len(self), # children should be inserted at least before this index
                        "child_count": len(klasses) - offset, # how many children in self
                    }

                    super().insert(index, subclass)

    def insert_module(self, module):
        """Insert any classes of module into the list

        :param module: the module to check for subclasses of cutoff_classes
        """
        for name, klass in inspect.getmembers(module, inspect.isclass):
            if issubclass(klass, self.cutoff_classes):
                self.insert(klass)

    def insert_modules(self):
        """Runs through sys.modules and inserts all classes matching .cutoff_classes"""
        for m in list(sys.modules.values()):
            self.insert_module(m)

    def edges(self):
        """Iterate through the absolute children and only the absolute children,
        no intermediate classes.

        :Example:
            class Foo(object): pass
            class Bar(Foo): pass
            class Che(object): pass

            classes = OrderedSubclasses()
            classes.extend([Foo, Bar, Che])

            for c in classes.edges():
                print(c)

            # this would print out Bar and Che because object and Foo are parents

        :returns: generator, only the absolute children who are not parents
        """
        for klass in self:
            rc = ReflectClass(klass)
            index_name = rc.classpath
            if self.info[index_name]["child_count"] == 0:
                yield klass

#         active_class = None
#         for current_class in self:
#             #pout.v(current_class, active_class)
#             if active_class is None or not issubclass(active_class, current_class):
#                 active_class = current_class
#                 yield current_class


class Extend(object):
    """you can use this decorator to extend instances in the bangfile with custom
    functionality

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
        """internal method that patches an instance o with a callback at name"""
        if isinstance(callback, property):
            setattr(o.__class__, name, callback)
        else:
            setattr(o, name, types.MethodType(callback, o))


class ReflectDecorator(object):
    """Internal class used by ReflectClass

    The information of each individual decorator on a given method will
    be wrapped in this class

    Moved from endpoints.reflection.ReflectDecorator on Jan 31, 2023
    """
    @cachedproperty(cached="_parents")
    def parents(self):
        """If this decorator is a class then this will return all the parents"""
        ret = []
        decor = self.decorator
        if inspect.isclass(decor):
            parents = inspect.getmro(decor)
            ret = parents[1:]
        return ret

    def __init__(self, name, args, kwargs, decorator):
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.decorator = decorator

    def contains(self, obj):
        """Return True if this decorator (that's a class) extends obj"""
        ret = obj == self.decorator
        if not ret:
            for parent in self.parents:
                if parent == obj:
                    ret = True
                    break

        return ret

    def __contains__(self, obj):
        return self.contains(obj)


class ReflectMethod(object):
    """Internal class used by ReflectClass

    Reflects a method on a class. This is kind of a strange situation where this
    class is entirely dependant on ReflectClass for its information. This is because
    this figures out all the decorators that were defined on this method and that
    information is only available in the full actual python code of the class, as
    retrieved using the ast module, so this really wraps ReflectClass.get_info()

    Moved from endpoints.reflection.ReflectMethod on Jan 31, 2023
    """
    @cachedproperty(cached="_required_args")
    def required_args(self):
        """return the *args that are needed to call the method"""
        ret = []
        info = self.get_info()
        for param_d in info.get("params", []):
            if param_d.get("required", False):
                ret.append(param_d["name"])

        if ret:
            # we need to go through the param decorators and check path args,
            # because it's entirely possible we can make something required in
            # the method definition but make it optional in the decorator
            for name, param_d in self.params.items():
                if not isinstance(name, int):
                    names = []
                    dest = param_d.get("dest", "")
                    if dest:
                        names.append(dest)
                    names.append(name)
                    names.extend(param_d.get("other_names", []))

                    # first name that is found wins
                    for n in names:
                        try:
                            ret.remove(n)
                            break
                        except ValueError:
                            pass

        ret.extend([None] * (max(0, len(self.params) - len(ret))))

        # now we will remove any non required path args that are left
        for name, param_d in self.params.items():
            if isinstance(name, int):
                #pout.v(name, param_d, ret)
                # since name is an integer it's a path variable
                if param_d.get("required", False):
                    if ret[name] is None:
                        ret[name] = name
                else:
                    if name < len(ret):
                        ret[name] = None

        return list(filter(lambda x: x is not None, ret))

    @cachedproperty(cached="_name")
    def name(self):
        """return the method name"""
        return self.method_name

    @cachedproperty(cached="_desc")
    def desc(self):
        """return the description of this method"""
        doc = None
        def visit_FunctionDef(node):
            """ https://docs.python.org/2/library/ast.html#ast.NodeVisitor.visit """
            if node.name != self.method_name:
                return

            doc = ast.get_docstring(node)
            raise StopIteration(doc if doc else "")

        target = self.reflect_class.cls
        try:
            node_iter = ast.NodeVisitor()
            node_iter.visit_FunctionDef = visit_FunctionDef
            node_iter.visit(ast.parse(inspect.getsource(target)))

        except StopIteration as e:
            doc = String(e)

        return doc or ""

    def __init__(self, method_name, method, reflect_class):
        self.method_name = method_name
        self.method = method
        self.reflect_class = reflect_class

    def get_info(self):
        """Gets info about this method using ReflectClass.get_info()

        :returns: dict, the information the class was able to gather about this method
        """
        info = self.reflect_class.get_info()
        return info[self.name][self.method_name]

    def has_positionals(self):
        """return True if this method accepts *args"""
        return self.get_info().get("positionals", False)

    def has_keywords(self):
        """return True if this method accepts **kwargs"""
        return self.get_info().get("keywords", False)

    def reflect_decorators(self):
        """Return all the decorators that decorate this method

        :returns: list, a list of ReflectDecorator instances
        """
        class_info = self.reflect_class.get_info()
        return class_info[self.method_name].get("decorators", [])


class ReflectClass(object):
    """
    Moved from endpoints.reflection.ReflectClass on Jan 31, 2023
    """
    reflect_method_class = ReflectMethod

    reflect_decorator_class = ReflectDecorator

    @property
    def class_name(self):
        """The class name"""
        return self.cls.__name__

    @property
    def modpath(self):
        """the module name that this class is defined in"""
        return self.cls.__module__

    @property
    def classpath(self):
        """The full classpath

        should this use the currently suggested syntax of modpath:Classname? instead
        of the backwards compatible modpath.Classname?

        https://docs.python.org/3/library/pkgutil.html#pkgutil.resolve_name

        :returns: str, "modpath.Classname"
        """
        return "{}:{}".format(self.modpath, self.class_name)

    @property
    def reflect_module(self):
        """Returns the reflected module"""
        return self._reflect_module or ReflectModule(self.cls.__module__)

    @cachedproperty(cached="_desc")
    def desc(self):
        """return the description of this class"""
        doc = inspect.getdoc(self.cls) or ""
        return doc

    @classmethod
    def get_class(cls, full_python_class_path):
        """
        take something like some.full.module.Path and return the actual Path class object

        https://docs.python.org/3/library/pkgutil.html#pkgutil.resolve_name

        Note -- this will fail when the object isn't accessible from the module, that means
        you can't define your class object in a function and expect this function to work, the
        reason why this doesn't work is because the class is on the local stack of
        the function, so it only exists when that function is running, so there's
        no way to get the class obect outside of the function, and you can't really
        separate it from the class (like using the code object to create the class
        object) because it might use local variables and things like that

        :Example:
            # -- THIS IS BAD --
            def foo():
                class FooCannotBeFound(object): pass
                # this will fail
                get_class("path.to.module.FooCannotBeFound")

        moved here from morp.reflection.get_class on 2-5-2023
        """
        parts = full_python_class_path.rsplit(':', 1)
        if len(parts) == 1:
            module_name, class_name = full_python_class_path.rsplit('.', 1)

        else:
            module_name, class_name = parts

        m = ReflectModule.import_module(module_name)
        return getattr(m, class_name)

    @classmethod
    def get_classpath(cls, obj):
        """return the full classpath of obj

        :param obj: type|instance
        :returns: str, the full classpath (eg, foo.bar.che:Classname)
        """
        parts = [obj.__module__]
        if isinstance(obj, type):
            parts.append(obj.__name__)
        else:
            parts.append(obj.__class__.__name__)

        return ":".join(parts)

    def __init__(self, cls, reflect_module=None):
        self.cls = cls
        self._reflect_module = reflect_module

    def is_private(self):
        """return True if this class is considered private"""
        return self.class_name.startswith('_')

    def module(self):
        """returns the actual module this class is defined in"""
        return self.reflect_module.module()

    def method_names(self):
        for method_name in self.get_info().keys():
            yield method_name

    def methods(self):
        for method_name, method_info in self.get_info().items():
            yield method_name, method_info["method"]

    def instance_methods(self, *args, **kwargs):
        instance = self.cls(*args, **kwargs)
        for method_name, method in inspect.getmembers(instance, inspect.ismethod):
            yield method_name, method

    def reflect_methods(self):
        """Yield all the methods defined in this class

        :returns: generator, yields ReflectMethod instances
        """
        for method_name, method_info in self.get_info().items():
            yield self.reflect_method_class(
                method_name,
                method_info["method"],
                reflect_class=self,
            )

    def reflect_method(self, method_name, *default_val):
        """Returns information about the method_name on this class

        :param method_name: str, the name of the method
        :param *default_val: mixed, if passed in return this instead of raising error
        :returns: ReflectMethod, the reflection information about the method
        """
        try:
            info = self.get_info()
            return self.reflect_method_class(
                method_name,
                info[method_name]["method"],
                reflect_class=self
            )

        except KeyError as e:
            if default_val:
                return default_val[0]

            else:
                raise AttributeError(f"No {self.classpath}.{method_name} method") from e

    def get(self, name, *default_val):
        """Get a value on the class

        :param name: str, the attribute name you want
        :param *default_val: mixed, return this if name doesn't exist
        :returns: mixed, the raw python attribute value
        """
        return getattr(self.cls, name, *default_val)

    @functools.cache
    def get_info(self):
        """Get information about all the methods in this class

        What helped me to get all the decorators in the class
        http://stackoverflow.com/questions/5910703/ specifically, I used this
        answer http://stackoverflow.com/a/9580006
        """
        ret = collections.defaultdict(dict)
        res = collections.defaultdict(list)
        mmap = {}

        def get_val(na, default=None):
            """given an inspect type argument figure out the actual real python
            value and return that
            :param na: ast.expr instanct
            :param default: sets the default value for na if it can't be resolved
            :returns: type, the found value as a valid python type
            """
            ret = None
            if isinstance(na, ast.Num):
                repr_n = repr(na.n)
                val = na.n
                vtype = float if '.' in repr_n else int
                ret = vtype(val)

            elif isinstance(na, ast.Str):
                ret = str(na.s)

            elif isinstance(na, ast.Name):
                # http://stackoverflow.com/questions/12700893/
                ret = getattr(builtins, na.id, None)
                if not ret:
                    ret = na.id
                    if ret == 'True':
                        ret = True
                    elif ret == 'False':
                        ret = False

            elif isinstance(na, ast.Dict):
                if na.keys:
                    ret = {get_val(na_[0]): get_val(na_[1]) for na_ in zip(na.keys, na.values)}
                else:
                    ret = {}

            elif isinstance(na, (ast.List, ast.Tuple)):
                if na.elts:
                    ret = [get_val(na_) for na_ in na.elts]
                else:
                    ret = []

                if isinstance(na, ast.Tuple):
                    ret = tuple(ret)

            else:
                ret = default

            return ret

        def is_super(childnode, parentnode):
            """returns true if child node has a super() call to parent node"""
            ret = False
            for n in childnode.body:
                if not isinstance(n, ast.Expr): continue

                try:
                    func = n.value.func
                    func_name = func.attr
                    if func_name == parentnode.name:
                        ret = isinstance(func.value, ast.Call)
                        break

                except AttributeError as e:
                    ret = False

            return ret

        def visit_FunctionDef(node):
            """as the code is parsed any found methods will call this function
            https://docs.python.org/2/library/ast.html#ast.NodeVisitor.visit
            """
            # if there is a super call in the method body we want to add the
            # decorators from that super call also
            add_decs = True
            if node.name in res:
                add_decs = is_super(mmap[node.name], node)

            if node.name not in mmap:
                mmap[node.name] = node

            if add_decs:
                for n in node.decorator_list:
                    d = {}
                    name = ''
                    args = []
                    kwargs = {}

                    # is this a call like @decorator or like @decorator(...)
                    if isinstance(n, ast.Call):
                        name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                        for an in n.args:
                            args.append(get_val(an))

                        for an in n.keywords:
                            kwargs[an.arg] = get_val(an.value)

                    else:
                        name = n.attr if isinstance(n, ast.Attribute) else n.id

                    d = {
                        "name": name,
                        "args": args,
                        "kwargs": kwargs
                    }

                    # get the actual decorator from either the module (imported)
                    # or from the global builtins
                    decor = None
                    if self.reflect_module:
                        m = self.reflect_module.module()
                        decor = getattr(m, name, None)

                    if not decor:
                        decor = getattr(builtins, name, None)

                    if not decor:
                        raise RuntimeError("Could not find {} decorator class".format(name))

                    d["decorator"] = decor

                    #res[node.name].append((name, args, kwargs))
                    res[node.name].append(self.reflect_decorator_class(**d))

        node_iter = ast.NodeVisitor()
        node_iter.visit_FunctionDef = visit_FunctionDef
        for target_cls in inspect.getmro(self.cls):
            if target_cls == object: break
            node_iter.visit(ast.parse(inspect.getsource(target_cls).strip()))

        for method_name, method in inspect.getmembers(self.cls):
            if method_name not in mmap: continue

            m = mmap[method_name]
            d = {
                "decorators": res.get(method_name, []),
                "method": getattr(self.cls, method_name),
            }

            # does the method have *args?
            d["positionals"] = True if m.args.vararg else False
            # does the method have **kwargs?
            d["keywords"] = True if m.args.kwarg else False

            args = []
            kwargs = {}

            # we build a mapping of the defaults to where they would sit in
            # the actual argument string (the defaults list starts at 0 but
            # would correspond to the arguments after the required
            # arguments, so we need to compensate for that
            defaults = [None] * (len(m.args.args) - len(m.args.defaults))
            defaults.extend(m.args.defaults)

            # if we ever just switch to py3 we can use inpsect.Parameter
            # here https://docs.python.org/3/library/inspect.html#inspect.Parameter
            d["params"] = []
            for i in range(1, len(m.args.args)):
                an = m.args.args[i]
                dp = {
                    "name": an.id if is_py2 else an.arg,
                    "required": True,
                }

                dan = defaults[i]
                if dan:
                    dp["required"] = False
                    dp["default"] = get_val(dan)

                d["params"].append(dp)

            ret[method_name] = d

        return ret

    def members(self, *args, **kwargs):
        """Get all the actual members of this class, passthrough for inspect.getmembers"""
        ret = {}
        for method_name, method in inspect.getmembers(self.cls, *args, **kwargs):
            ret[method_name] = method
        return ret

    def parents(self, cutoff_class=object):
        for parent_class in self.classes(cutoff_class=cutoff_class):
            if parent_class is not self.cls:
                yield parent_class

    def reflect_parents(self, cutoff_class=object):
        for parent_class in self.parents(cutoff_class=cutoff_class):
            yield type(self)(parent_class)

    def classes(self, cutoff_class=object):
        for klass in inspect.getmro(self.cls):
            if cutoff_class and klass is cutoff_class:
                break

            else:
                yield klass

    def reflect_classes(self, cutoff_class=object):
        for klass in self.classes(cutoff_class=cutoff_class):
            yield type(self)(klass)


class ReflectModule(object):
    """Introspect on a given module_name/modulepath (eg foo.bar.che)

    Moved from endpoints.reflection.ReflectModule on Jan 31, 2023
    """
    reflect_class_class = ReflectClass

    @property
    def path(self):
        """Return the importable path for this module, this is not the filepath
        of the module but the directory the module could be imported from"""
        return self.find_module_import_path()

    @property
    def modpath(self):
        """Return the full qualified python path of the module (eg, foo.bar.che)"""
        return self.module().__name__

    @property
    def modroot(self):
        """Return the aboslute root module"""
        if self.module_package:
            module_name = self.module_package.split(".", maxsplit=1)[0]

        else:
            module_name = self.module_name.split(".", maxsplit=1)[0]

        return module_name

    @classmethod
    def find_module_names(cls, path, prefix="", ignore_private=True):
        """recursive method that will find all the modules of the given path

        :param path: str, the path to scan for modules/submodules
        :param prefix: str, if you want found modules to be prefixed with a certain
            module path
        :param ignore_private: bool, if True then ignore modules considered private
        :returns: set, a set of submodule names under path prefixed with prefix
        """
        module_names = set()

        # https://docs.python.org/2/library/pkgutil.html#pkgutil.iter_modules
        for module_info in pkgutil.iter_modules([path]):
            # we want to ignore any "private" modules
            if module_info[1].startswith('_') and ignore_private: continue

            if prefix:
                module_prefix = ".".join([prefix, module_info[1]])
            else:
                module_prefix = module_info[1]

            if module_info[2]:
                # module is a package
                module_names.add(module_prefix)
                submodule_names = cls.find_module_names(os.path.join(path, module_info[1]), module_prefix)
                module_names.update(submodule_names)
            else:
                module_names.add(module_prefix)

        return module_names

    @classmethod
    def find_module_package(cls, module_name):
        """This will attempt to find the package if module_name is relative

        :param module_name: str, if relative (starts with dot) then try and find
            the calling package which you can pass into importlib.import_module()
        :returns: str, the calling package modpath
        """
        module_package = None
        if module_name.startswith("."):
            frames = inspect.stack()
            for frame in frames:
                frame_cls = frame[0].f_locals.get("cls", None)
                frame_self = frame[0].f_locals.get("self", None)
                is_first_outside_call = (frame_cls and frame_cls is not cls) \
                    or (frame_self and type(frame_self) is not cls)
                if is_first_outside_call:
                    module_package = frame[0].f_globals["__name__"]
                    break

        return module_package

    @classmethod
    def import_module(cls, module_name, module_package=None):
        """passthrough for importlib importing functionality"""
        return importlib.import_module(module_name, module_package)

    def __init__(self, module_name, module_package=None):
        """
        :param module_name: str|ModuleType, the module path of the module to introspect
            or the actual module
        :param module_package: the prefix that will be used to load module_name if
            module_name is relative
        """
        if isinstance(module_name, types.ModuleType):
            self._module = module_name
            self.module_name = module_name.__name__
            self.module_package = module_package

        else:
            self._module = None
            self.module_name = module_name
            self.module_package = module_package or self.find_module_package(module_name)

    def __iter__(self):
        """This will iterate through this module and all its submodules
        :returns: a generator that yields ReflectModule instances
        """
        for module_name in self.module_names():
            yield type(self)(module_name)

    def is_private(self):
        """return True if this module is considered private"""
        parts = []
        if self.module_package:
            parts.extend(self.module_package.split("."))
        parts.extend(self.module_name.split("."))
        for part in parts:
            if part.startswith("_"):
                return True

    def reflect_module(self, *parts):
        """Returns a reflect module instance for a submodule"""
        return type(self)(self.module(*parts))

    def basemodule(self):
        """Returns the root-most module of this module's path (eg, if this module was
        foo.bar.che then this would return foo module)"""
        return self.import_module(self.modroot)

    def rootmodule(self):
        return self.basemodule()

    def reflect_rootmodule(self):
        return self.reflect_basemodule()

    def reflect_basemodule(self):
        return type(self)(self.modroot)

    def module(self, *parts):
        """return the actual python module

        :param *parts: modpath parts relative to this module
        :returns: ModuleType, the module or the submodule
        """
        if self._module and not parts:
            ret = self._module

        else:
            module_name = self.module_name
            if parts:
                module_name += "." + ".".join(parts)

            ret = self.import_module(module_name, self.module_package)

        return ret

    def module_names(self):
        """return all the module names that this module encompasses
        :returns: set, a set of string module names
        """
        module = self.module()
        module_name = module.__name__
        module_names = set([module_name])

        if hasattr(module, "__path__"):
            # path attr exists so this is a package
            module_names.update(self.find_module_names(module.__path__[0], module_name))

        return module_names

    @functools.cache
    def get_info(self):
        """Get information about the module"""
        ret = {}
        module = self.module()
        classes = inspect.getmembers(module, inspect.isclass)
        for class_name, class_type in classes:
            ret[class_name] = self.reflect_class_class(class_type, self)
        return ret

    def reflect_classes(self, ignore_private=True):
        """yields ReflectClass instances that are found in only this module (not submodules)

        :param ignore_private: bool, if True then ignore classes considered private
        :returns: a generator of ReflectClass instances
        """
        for class_name, rc in self.get_info(): 
            if isinstance(rc, self.reflect_class_class):
                if ignore_private and rc.is_private():
                    continue
                yield rc

    def classes(self, ignore_private=True):
        """yields classes (type instances) that are found in only this module (not submodules)

        :param ignore_private: bool, if True then ignore classes considered private
        :returns: a generator of type instances
        """
        for rc in self.reflect_classes(ignore_private=ignore_private):
            yield rc.cls

    def reflect_class(self, name, *default_val):
        """Get a ReflectClass instance of name"""
        try:
            return self.get_info()[name]

        except KeyError as e:
            if default_val:
                return default_val[0]

            else:
                raise AttributeError(f"{self.module().__name__}.{name} does not exist") from e

    def get(self, name, *default_val):
        """Get a value of the module

        :param name: str, the attribute name you want
        :param *default_val: mixed, return this if name doesn't exist
        :returns: mixed, the raw python attribute value
        """
        return getattr(self.module(), name, *default_val)

    def find_module_import_path(self):
        """find and return the importable path for the module"""
        module_name = self.module().__name__
        master_modname = module_name.split(".", 1)[0]
        master_module = sys.modules[master_modname]
        path = os.path.dirname(os.path.dirname(inspect.getsourcefile(master_module)))
        return path

    def get_data(self, resource):
        """This is just a wrapper around pkgutil.get_data, so you will need to use
        the full path from this module

        :Example:
            foo/
              __init__.py
              data/
                one.txt
              bar/
                __init__.py
                che.py
                data/
                  two.txt

            rm = ReflectModule("foo")
            rm.get_data("data/one.txt")
            rm.get_data("bar/data/two.txt")

        * https://docs.python.org/3/library/pkgutil.html#pkgutil.get_data
        * https://stackoverflow.com/questions/6028000/how-to-read-a-static-file-from-inside-a-python-package/58941536#58941536
        * https://setuptools.pypa.io/en/latest/userguide/datafiles.html
        * https://stackoverflow.com/questions/779495/access-data-in-package-subdirectory

        :param resource: the full relative path from self.modpath of the file you want
        :returns: bytes, the file contents
        """
        return pkgutil.get_data(self.modpath, resource)

    def find_data(self, resource):
        """Similar to .get_data() but you don't need to specify the full path because
        this will traverse the whole module directory so it will only work with
        traditional packages

        :param resource: the relative path of the file hopefully somewhere in the package
        :returns: bytes, the file contents
        """
        basedir = Dirpath(self.path, self.modpath.split("."))
        for fp in basedir.files():
            if fp.endswith(resource):
                return fp.read_bytes()

        raise FileNotFoundError(f"No such file or directory found: {resource}")

    def data_dirs(self, basename="data"):
        """Find the data directories in this module

        A directory is considered a data directory if it matches basename or if
        it doesn't contain an __init__.py file

        :param basename: the data directory basename
        :returns: generator, yields all the found module data directories
        """
        basedir = Dirpath(self.path)
        # once we find a matching directory we stop traversing it, so data
        # directories can have folders and stuff in them
        it = basedir.dirs()
        for dp in it:
            if not dp.has_file("__init__.py") or dp.endswith(basename):
                it.finish(dp)
                yield dp

