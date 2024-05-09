# -*- coding: utf-8 -*-
import warnings
import inspect

from ..compat import *
from .base import FuncDecorator, Decorator


class cache(FuncDecorator):
    """run the decorated function only once for the given arguments

    in python 3+ it's better to use functools.cache or functools.lru_cache if
    those will work for you

        https://docs.python.org/3/library/functools.html#functools.cache

    However, those don't work great for instance methods where the object
    isn't hashable (like a method on a dict child classe) since it will try
    and use the `self` passed into the method as the value to cache

    :Example:
        @cache
        def func(x):
            print("adding")
            return x + 1
        func(4) # prints "adding"
        func(10) # prints "adding"
        func(4) # returns 5, no print
        func(10) # returns 11, no print

        class Foo(dict):
            @cache
            def func(self):
                # functools.cache would normally fail on this
                return 1

        # The cache can be wrong when the first value is non-hashable and it
        # is important to the returned value, however, I think this would
        # be an uncommon use case for this decorator:
        @cache
        def func(d, v):
            return d.get("foo", v)

        d = {}
        func(d, 1) # 1

        d["foo"] = 2
        func(d, 1) # 1 instead of 2 because value was already cached
    """
    def decorate(self, f, *cache_args, **cache_kwargs):
        def wrapped(*args, **kwargs):
            name = str(hash(f))
            if args:
                for i, a in enumerate(args):
                    try:
                        name += str(hash(a))

                    except TypeError:
                        if i == 0:
                            # if it's the first value passed to the callable
                            # and it failed hashing then let's just use the id
                            # because this is most likely an instance method
                            # and the unhashable value is `self`
                            name += str(id(a))

                        else:
                            raise

            if kwargs:
                for k, v in kwargs.items():
                    name += str(hash(k))
                    name += str(hash(v))

            try:
                ret = getattr(self, name)

            except AttributeError:
                ret = f(*args, **kwargs)
                setattr(self, name, ret)

            return ret
        return wrapped


class deprecated(Decorator):
    """Mark function/class as deprecated

    python has to be ran with -W flag to see warnings

    https://stackoverflow.com/a/30253848/5006
    """
    def find_definition(self, o, callback):
        src_line = 0
        src_file = ""

        st = inspect.stack()
        for ft in st:
            lines = "\n".join(ft[4])
            if callback(lines):
                src_file = ft[1]
                src_line = ft[2]
                break

        if not src_file:
            if self.is_function(o):
                if is_py2:
                    c = o.func_code

                else:
                    c = o.__code__


                src_file = c.co_filename
                src_line = c.co_firstlineno + 1

            else:
                src_file = inspect.getsourcefile(o)
                if not src_file:
                    src_file = inspect.getfile(o)
                if not src_file:
                    src_file = "UNKNOWN"

        return src_file, src_line

    def decorate_func(self, func, *deprecated_args, **deprecated_kwargs):
        callback = lambda lines: "@" in lines or "def " in lines
        src_file, src_line = self.find_definition(func, callback)

        def wrapped(*args, **kwargs):
            # https://wiki.python.org/moin/PythonDecoratorLibrary#Generating_Deprecation_Warnings
            # http://stackoverflow.com/questions/2536307/decorators-in-the-python-standard-lib-deprecated-specifically
            warnings.warn_explicit(
                "Deprecated function {}".format(func.__name__),
                category=DeprecationWarning,
                filename=src_file,
                lineno=src_line
            )
            return func(*args, **kwargs)
        return wrapped

    def decorate_class(self, cls, *deprecated_args, **deprecated_kwargs):
        callback = lambda lines: "@" in lines or "class " in lines
        src_file, src_line = self.find_definition(cls, callback)

        warnings.warn_explicit(
            "Deprecated class {}.{}".format(cls.__module__, cls.__name__),
            category=DeprecationWarning,
            filename=src_file,
            lineno=src_line,
        )
        return cls

