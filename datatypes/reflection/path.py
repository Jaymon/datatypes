# -*- coding: utf-8 -*-
import sys
import types
import importlib
import importlib.util
import importlib.machinery
import pkgutil
import re

from ..compat import *
from ..decorators import (
    classproperty,
)
from ..string import String
from ..path import Dirpath, Path
from ..config import Config
from ..url import Url

from .inspect import ReflectModule


class ReflectPath(Path):
    """Reflect a path

    This is just a set of helper methods to infer python specific information
    from a path
    """
    @classproperty
    def reflect_module_class(self):
        return ReflectModule

    def reflect_modules(self, depth=-1):
        """Yield all the python modules found in this path

        :param depth: int, how deep into the path you would like to go,
            defaults to all depths
        :returns: generator[ReflectModule], yields reflection instances for
            every found python module
        """
        if not depth:
            depth = -1

        if self.is_file():
            modname = self.fileroot
            path = self.basedir
            yield self.reflect_module_class(modname, path=path)

        else:
            path = self
            for modname in self.reflect_module_class.find_module_names(path):
                if depth <= 0 or modname.count(".") < depth:
                    yield self.reflect_module_class(modname, path=path)

    def get_modules(self, depth=-1, ignore_errors=False):
        """Yield all the python modules found in this path

        :param depth: int, how deep into the path you would like to go,
            defaults to all depths
        :param ignore_errors: bool, True if you would like to just ignore
            errors when trying to load the module
        :returns: generator[module], yields every found python module
        """
        for rm in self.reflect_modules(depth=depth):
            try:
                yield rm.get_module()

            except (SyntaxError, ImportError):
                if not ignore_errors:
                    raise

    def get_module(self):
        if self.is_file():
            if self.ext == "py":
                parts = [self.fileroot]
                p = self.parent
                while p.has_file("__init__.py"):
                    parts.append(p.fileroot)
                    p = p.parent

                rm = ReflectModule(
                    ".".join(reversed(parts)),
                    path=p
                )

            else:
                # https://docs.python.org/3/library/exceptions.html#ModuleNotFoundError
                raise ModuleNotFoundError(self.path)

        elif self.is_dir():
            p = self.as_dir()
            if p.has_file("__init__.py"):
                parts = []
                while p.has_file("__init__.py"):
                    parts.append(p.fileroot)
                    p = p.parent

                rm = ReflectModule(
                    ".".join(reversed(parts)),
                    path=p
                )

            else:
                raise ModuleNotFoundError(
                    f"{self.path} is not a python package"
                )

        return rm.get_module()

    def exec_module(self, module_name=""):
        """Implementation of imp.load_source with the change that it doesn't
        cache the module in sys.modules

        The python 2.7 imp.load_source doc says:

            Load and initialize a module implemented as a Python source file
            and return its module object. If the module was already
            initialized, it will be initialized again.

        This is based on:
            * https://github.com/python/cpython/pull/105978/files
            * https://github.com/python/cpython/issues/104212#issuecomment-1560813974
            * https://stackoverflow.com/a/77401571

        Discussion:
            * https://docs.python.org/2.7/library/imp.html#imp.load_source
            * https://github.com/python/cpython/issues/58756
            * https://github.com/python/cpython/issues/104212#issuecomment-1599697511

        :param module_name: str, the name you want for the module, if nothing
            is passed in it will use self.fileroot
        :returns: types.ModuleType
        """
        if self.is_dir():
            fp = self.as_dir().get_file("__init__.py")

        else:
            fp = self

        if not module_name:
            module_name = self.fileroot

        loader = importlib.machinery.SourceFileLoader(module_name, fp)
        spec = importlib.util.spec_from_file_location(
            module_name,
            fp,
            loader=loader
        )
        module = importlib.util.module_from_spec(spec)

        # sys.modules[module.__name__] = module
        loader.exec_module(module)
        return module

    def remote_repository_url(self):
        """Return the remote repository url of this directory

        For example, if this was ran in the datatypes repo directory, it would
        return:

            https://github.com/Jaymon/datatypes
        """
        if self.is_dir():
            config_path = self.child(".git", "config")
            if config_path.is_file():
                c = Config(config_path)
                for section in c.sections():
                    if "url" in c[section]:
                        gurl = c[section]["url"]
                        if "github.com" in gurl:
                            gurl = gurl.replace(":", "/")
                            gurl = re.sub(r"\.git$", "", gurl)
                            url = Url(
                                gurl,
                                username="",
                                password="",
                                scheme="https"
                            )
                            return url

                        else:
                            raise NotImplementedError(
                                f"Not sure how to handle {gurl}"
                            )

    def find_modules(self, fileroot, depth=3, submodules=True):
        """Iterate any `fileroot` modules found in .path

        This method incorporates this functionality:

        * https://github.com/Jaymon/endpoints/issues/87
        * https://github.com/Jaymon/endpoints/issues/123

        It was moved here on 3-3-2024 because I wanted to use this in prom
        also so I needed it in a common library

        How this works is by finding sys.path (PYTHONPATH) paths that are
        located in .path and then checking those to depth looking for fileroot

        :param fileroot: str, the module name, this is using the fileroot
            nomenclature because it can be module path (eg `foo.bar`) and it
            shouldn't have an extension either (eg, `foo.py`)
        :param depth: int, how many folders deep you want to look
        :param submodules: bool, True if you want to iterate modules matching
            fileroot and all their submodules also
        :returns: generator[ModuleType]
        """
        path = self.path

        if self.is_file() and self.fileroot == fileroot:
            yield self.get_module()

        else:
            for p in (Dirpath(p) for p in sys.path):
                if p.is_relative_to(path):
                    dirparts = p.relative_parts(path)

                    piter = p.iterator
                    # we only want to look depth folders deep
                    piter.depth(depth)
                    # ignore any folders that begin with an underscore or
                    # period
                    piter.nin_basename(regex=r"^[_\.]")
                    # we only want dir/file fileroots with this name
                    piter.eq_fileroot(fileroot)

                    for sp in piter:
                        modparts = sp.parent.relative_parts(path)
                        # trim the directory parts of our module path so we
                        # have a real module path we can import
                        modparts = modparts[len(dirparts):]
                        modparts.append(sp.fileroot)
                        prefix = ".".join(modparts)

                        rm = ReflectModule(prefix)
                        try:
                            if submodules:
                                for m in rm.get_modules():
                                    yield m

                            else:
                                yield rm.get_module()

                        except ModuleNotFoundError:
                            # what we found wasn't actually a module
                            pass


class ReflectName(String):
    r"""A reflection object similar to python's built-in resolve_name

    take something like some.full.module:Classpath and return the actual Path
    class object

    https://docs.python.org/3/library/pkgutil.html#pkgutil.resolve_name

    foo.bar.che:FooBar.baz
    \_________/ \____/ \_/
         |         |    |
    module_name    |    |
                   |    |
            class_name  |
                |       |
                |  method_name
                |      |
    foo/bar.py:FooBar.baz
    \________/
        |
      filepath

    TODO -- add support for cwd, so this would be valid:

        /some/base/directory:module.path:ClassName.method_name

    and /some/base/directory would become .cwd

    NOTE -- this will fail when the object isn't accessible from the module,
    that means you can't define your class object in a function and expect
    this function to work, the reason why this doesn't work is because the
    class is on the local stack of the function, so it only exists when that
    function is running, so there's no way to get the class object outside
    of the function, and you can't really separate it from the class (like
    using the code object to create the class object) because it might use
    local variables and things like that

    :Example:
        # -- THIS IS BAD --
        def foo():
            class FooCannotBeFound(object): pass
            # this will fail
            get_class("path.to.module.FooCannotBeFound")

    moved to ReflectClass.get_class from morp.reflection.get_class on 2-5-2023
    and then moved to here on 7-31-2023

    This is loosely based on pyt.path:PathGuesser.set_possible
    """
    @classproperty
    def reflect_module_class(self):
        return ReflectModule

    @property
    def module(self):
        return self.get_module()

    @property
    def cls(self):
        return self.get_class()

    @property
    def method(self):
        return self.get_method()

    @property
    def module_parts(self):
        return self.module_name.split(".")

    def __new__(cls, name):
        name, properties = cls.normalize(name)

        instance = super().__new__(cls, name)

        for k, v in properties.items():
            setattr(instance, k, v)

        return instance

    @classmethod
    def normalize(cls, name):
        ret = ""
        filepath = modpath = classname = methodname = ""
        classnames = []
        unresolvable = []

        parts = name.split(":")
        if len(parts) > 1:
            if parts[0].endswith(".py") or "/" in parts[0]:
                # foo/bar/che.py:Classname.methodname
                filepath = parts[0]

            else:
                modpath = parts[0]

            parts = parts[1].split(".")
            for index, part in enumerate(parts):
                if re.search(r'^[A-Z]', part):
                    classnames.append(part)
                    classname = part

                elif part.startswith("<"):
                    unresolvable = parts[index:]
                    break

                else:
                    methodname = part

        else:
            # this is old syntax of module_name.class_name(s).method_name and
            # so it will assume module_name is everything to the left of a part
            # that starts with a capital letter, then every part that starts
            # with a capital letter are the class_name(s) and a lowercase
            # part after is the method_name
            if name.endswith(".py") or "/" in name:
                # foo/bar/che.py
                filepath = name

            else:
                # this can be just module_name, module_name.class_name(s), and
                # module_name.class_name(s).method_name
                #
                # TODO -- if everything is lowercase it now assumes everything
                # is a module_name, but it should probably actually resolve it
                # and find out if there is a class or method in there
                parts = name.split(".")

                modparts = []
                while parts:
                    if re.search(r'^[A-Z]', parts[0]):
                        break

                    else:
                        modparts.append(parts[0])
                        parts.pop(0)

                modpath = ".".join(modparts)

                classnames = []
                while parts:
                    if re.search(r'^[A-Z]', parts[0]):
                        classname = parts.pop(0)
                        classnames.append(classname)

                    else:
                        break

                if parts:
                    methodname = parts[0]

        if filepath:
            ret = filepath

        elif modpath:
            ret = modpath

        if classnames:
            if ret:
                ret += ":"

            ret += ".".join(classnames)

        if methodname:
            ret += f".{methodname}"

        if unresolvable:
            ret += ".".join(unresolvable)

        return ret, {
            "filepath": filepath,
            "module_name": modpath,
            "class_names": classnames,
            "class_name": classname,
            "method_name": methodname,
            "unresolvable": unresolvable,
        }

    def reflect_module(self):
        if not self.module_name:
            return None

        return self.reflect_module_class(self.module_name)

    def reflect_class(self):
        if self.class_names:
            rm = self.reflect_module()
            if rm:
                o = rm.get_module()
                for classname in self.class_names:
                    o = getattr(o, classname)

                return rm.create_reflect_class(o)

    def reflect_method(self):
        if not self.method_name:
            return None

        rc = self.reflect_class()
        return rc.reflect_method(self.method_name)

    def get_module(self):
        rm = self.reflect_module()
        if rm:
            return rm.get_module()

    def get_module_names(self, module_name=""):
        """Get all the module names of the module name

        :Example:
            rn = ReflectName("foo.bar.che:FooBar")
            list(rn.get_module_names()) # ["foo", "foo.bar", "foo.bar.che"]

            list(rn.get_module_names("bar")) # ["foo.bar"]
            list(rn.get_module_names("bar.che")) # ["foo.bar", "foo.bar.che"]

            list(rn.get_module_names("moo")) # []

        :param module_name: str, if this is passed in then only module names
            that belong to this module_name in some way will be yielded
        :returns: generator[str], each module path starting from the first
            parent module and moving through the paths to the most child 
            module
        """
        modname = ""

        mparts = []
        if module_name:
            mparts = module_name.strip(".").split(".")

        for p in self.module_parts:
            if modname:
                modname += "." + p

            else:
                modname = p

            if mparts:
                if p == mparts[0]:
                    for mp in mparts[1:]:
                        yield modname
                        modname += "." + mp

                    yield modname
                    break

            else:
                yield modname

    def get_modules(self, module_name=""):
        """Similar to .reflect_modules but returns the actual module"""
        for rm in self.reflect_modules(module_name):
            yield rm.get_module()

    def reflect_modules(self, module_name=""):
        """Similar to .get_module_names but returns ReflectModule instances

        :Example:
            rn = ReflectName("foo.bar.che.bar")
            mnames = [rm.module_name for rm in rn.reflect_modules("bar.che")]
            print(mnames) # ["foo.bar", "foo.bar.che"]

        :param module_name: see .get_module_names
        :returns: generator[ReflectModule]
        """
        for modname in self.get_module_names(module_name):
            if modname.startswith("<"):
                # <run_path> module paths can't be reflected
                break

            else:
                yield self.reflect_module_class(modname)

    def get_class(self):
        """Get the absolute child class for this name

        :Example:
            rn = ReflectName("<MODPATH>:Foo.Bar.Che.<METHOD>")
            rn.get_class().__name__ # Che

        :returns: type
        """
        rc = self.reflect_class()
        if rc:
            return rc.get_class()

    def get_classes(self):
        """Get all the classes for this name

        :Example:
            rn = ReflectName("<MODPATH>:Foo.Bar.Che")
            classes = list(rn.get_classes())
            classes[0].__name__ # Foo
            classes[1].__name__ # Bar
            classes[2].__name__ # Che

        :returns: generator[type]
        """
        o = self.get_module()
        for class_name in self.class_names:
            o = getattr(o, class_name)
            yield o

    def get_method(self):
        rm = self.reflect_method()
        if rm:
            return rm.get_method()

    def has_class(self):
        return bool(self.class_name)

    def resolve(self):
        return pkgutil.resolve_name(self)

    def is_module_relative_to(self, other):
        """Return whether or not self.module_name is relative to other"""
        try:
            self.relative_module_name(other)
            return True

        except ValueError:
            return False

    def relative_module_name(self, other):
        """Return the relative module path relative to other. This is similar
        to Path.relative_to except it allows a partial other

        :Example:
            rn = ReflectName("foo.bar.che.boo")
            print(rn.relative_module_name("bar")) # che.boo
            print(rn.relative_module_name("foo.bar")) # che.boo

        :param other: str, the module path. This can either be the full module
            prefix or a partial module prefix
        :returns: str, the submodule path that comes after other
        """
        other = re.escape(other.strip("."))
        parts = re.split(
            rf"(?:^|\.){other}(?:\.|$)",
            self.module_name,
            maxsplit=1
        )

        if len(parts) > 1:
            return parts[1]

        raise ValueError(
            f"{other} is not a parent module of {self.module_name}"
        )

    def relative_module_parts(self, other):
        """Same as .relative_module but returns the remainder submodule as a
        list of parts. Similar to Path.relative_parts

        :param other: str, see .relative_module_name
        :returns: list[str]
        """
        smpath = self.relative_module_name(other)
        return smpath.split(".") if smpath else []

    def absolute_module_parts(self, other):
        """Same as .absolute_module but returns the remainder submodule as a
        list of parts.

        :param other: str, see .absolute_module_name
        :returns: list[str]
        """
        smparts = self.relative_module_parts(other)
        parts = self.module_parts
        return parts[0:-len(smparts)] if smparts else parts

    def absolute_module_name(self, other):
        """The opposite of .relative_module, this returns the parent module
        ending with other

        :Example:
            rn = ReflectName("foo.bar.che.boo")
            print(rn.absolute_module_name("bar")) # foo.bar
            print(rn.absolute_module_name("foo.bar")) # foo.bar

        :param other: str, the module path. This will usually be a partial
            module prefix
        :returns: str, the parent module that ends with other
        """
        return ".".join(self.absolute_module_parts(other))

