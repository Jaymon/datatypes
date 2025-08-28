# -*- coding: utf-8 -*-
import inspect
import sys
import types
import functools
import os
import importlib
import ast
import pkgutil
import re
import decimal
import itertools
from typing import (
    Any, # https://docs.python.org/3/library/typing.html#the-any-type
    get_args, # https://stackoverflow.com/a/64643971
    get_origin,
    Optional,
    Union,
    Literal,
    Annotated,
)
from collections.abc import (
    Mapping,
    Sequence,
    Set,
)

from ..compat import *
from ..decorators import (
    cachedproperty,
)
from ..path import Dirpath
from ..token.base import Scanner


class ReflectObject(object):
    """Internal base class for the common inter-related object/instance
    inspection classes like ReflectClass, ReflectCallable, and ReflectModule
    """
    def __init__(self, target, **kwargs):
        self.target = target

    def get_docblock(self, inherit=False):
        """Get the docblock comment for the callable

        :param inherit: bool, if True then check parents for a docblock also,
            if False then only check the immediate object
        :returns: str
        """
        target = self.target

        if inherit:
            # https://github.com/python/cpython/blob/3.11/Lib/inspect.py#L844
            doc = inspect.getdoc(target)

        else:
            doc = target.__doc__
            if doc:
                doc = inspect.cleandoc(doc)

        if not doc:
            # https://github.com/python/cpython/blob/3.11/Lib/inspect.py#L1119
            doc = inspect.getcomments(target)
            if doc:
                doc = re.sub(r"^\s*#", "", doc, flags=re.MULTILINE).strip()
                doc = inspect.cleandoc(doc)

        return doc or ""

    def reflect_docblock(self, inherit=False):
        if doc := self.get_docblock(inherit=inherit):
            return self.create_reflect_docblock(doc)

    def get_module(self):
        return self.reflect_module().get_module()

    def reflect_module(self):
        """Returns the reflected module"""
        return self.create_reflect_module(self.get_target().__module__)

    def get_class(self):
        raise NotImplementedError()

    def reflect_class(self):
        if klass := self.get_class():
            return self.create_reflect_class(klass)

    def get_target(self):
        return self.target

    def has_definition(self, attr_name):
        """Return True if attr_name is actually defined in this object, this
        doesn't take into account inheritance, it has to be actually defined
        on this object

        https://stackoverflow.com/questions/5253397/

        :param attr_name: str, the attribute's name that has to have a
            definition on .get_target()
        :returns: bool
        """
        return attr_name in vars(self.get_target())

    def create_reflect_class(self, *args, **kwargs):
        return kwargs.get("reflect_class_class", ReflectClass)(
            *args,
            **kwargs
        )

    def create_reflect_module(self, *args, **kwargs):
        return kwargs.get("reflect_module_class", ReflectModule)(
            *args,
            **kwargs
        )

    def create_reflect_callable(self, *args, **kwargs):
        return kwargs.get("reflect_callable_class", ReflectCallable)(
            *args,
            **kwargs
        )

    def create_reflect_type(self, *args, **kwargs):
        return kwargs.get("reflect_type_class", ReflectType)(
            *args,
            **kwargs
        )

    def create_reflect_ast(self, *args, **kwargs):
        return kwargs.get("reflect_ast_class", ReflectAST)(
            *args,
            **kwargs
        )

    def create_reflect_docblock(self, *args, **kwargs):
        return kwargs.get("reflect_docblock_class", ReflectDocblock)(
            *args,
            **kwargs
        )

    def is_class(self):
        """Returns True if target is considered a class"""
        return isinstance(self, ReflectClass)

    def is_module(self):
        """Returns True if target is considered a module"""
        return isinstance(self, ReflectModule)

    def is_callable(self):
        """Returns True if target is considered a callable (usually a function
        or method)"""
        return isinstance(self, ReflectCallable)


class ReflectAST(ReflectObject):
    """Internal class. Provides introspection and helper methods for ast.AST
    nodes"""
    @property
    def name(self):
        n = self.get_target()
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Attribute):
                name = n.func.attr

            else:
                name = n.func.id

        else:
            name = n.attr if isinstance(n, ast.Attribute) else n.id

        return name

    def __init__(self, target, reflect_callable=None, **kwargs):
        super().__init__(target)

        self.reflect_callable = reflect_callable

    def get_class(self):
        return self.reflect_callable.get_class()

    def reflect_module(self):
        return self.reflect_callable.reflect_module()

    def get_imported_value(self, name):
        """Get the actual imported value from either the module
        (imported) or from the global builtins
        """
        ret = None
        if m := self.get_module():
            ret = getattr(m, name, None)

        if not ret:
            if rc := self.reflect_class():
                for rp in rc.reflect_parents():
                    if m := rp.get_module():
                        if ret := getattr(m, name, None):
                            break

        if not ret:
            ret = getattr(builtins, name, None)

        if not ret:
            raise RuntimeError(
                "Could not find imported {} value".format(name)
            )

    def get_parameters(self):
        n = self.get_target()
        if not isinstance(n, ast.Call):
            raise ValueError(f"Getting parameters with {type(n)}")

        args = []
        kwargs = {}

        for an in n.args:
            ran = self.create_reflect_ast(an)
            args.append(ran.get_expr_value())

        for an in n.keywords:
            ran = self.create_reflect_ast(an.value)
            kwargs[an.arg] = ran.get_expr_value()

        return args, kwargs

    def get_expr_value(self, default=None):
        """given an inspect type argument figure out the actual real python
        value and return that

        :param na: ast.expr instance
        :param default: sets the default value for na if it can't be
            resolved
        :returns: type, the found value as a valid python type
        """
        na = self.get_target()
        if not isinstance(na, ast.expr):
            raise TypeError(f"get_expr_value with {type(na)}")

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
                na_items = zip(
                    na.keys,
                    na.values
                )
                for k, v in na_items:
                    rk = self.create_reflect_ast(k)
                    rv = self.create_reflect_ast(v)
                    ret[rk.get_expr_value()] = rv.get_expr_value()

            else:
                ret = {}

        elif isinstance(na, (ast.List, ast.Tuple)):
            if na.elts:
                ret = [
                    self.create_reflect_ast(elt).get_expr_value()
                    for elt in na.elts
                ]

            else:
                ret = []

            if isinstance(na, ast.Tuple):
                ret = tuple(ret)

        else:
            ret = default

        return ret


class ReflectType(ReflectObject):
    """Reflect a python type

    This is used to get more information from typing annotations

    Let's say we have the type: `dict[str, int]`, the origin type would be
    `dict`, and the value types would be `[int]`, the key types would be
    `[str]`. The arg types would be `[str, int]`

    .. note:: You have to be careful with encompassing types, since they can
        identify as any of their sub types

        :example:
            rt = ReflectType(str|int)
            rt.is_int() # True
            rt.is_str() # True
            rt.is_union() # True

            rt = ReflectType(Annotated[str|int, None])
            rt.is_union() # True
            rt.is_str() # True
            rt.is_annotated() # True

    .. note:: Annotations seem to be internally cached by python and so you
        can get different results with things like

        :example:
            rt1 = ReflectType(Annotated[str|int, None])

            # this one can switch `int|str` to `str|int` since it pulls the
            # type from cache since it matches its heuristic
            rt2 = ReflectType(Annotated[int|str, None])

    https://docs.python.org/3/library/typing.html
    https://docs.python.org/3/library/collections.abc.html
    """
    def reflect_types(self, depth=1):
        """This breaks apart the argument types and iterates through them

        the type could be a union (eg, `int|str`) or an alias (eg,
        `dict[str, int]`, `tuple[int, ...]`) or any other type

        :returns: generator[ReflectType]
        """
        if self.is_annotated():
            yield self
            yield from self.reflect_arg_types(depth=depth)

        elif self.is_union():
            yield from self.reflect_arg_types(depth=depth)

        elif self.is_any():
            # we ignore Any since it is equivalent to no check and we're only
            # really interested in "actionable" types
            pass

        elif self.is_ellipsis():
            # we ignore the ellipses type because it is just saying more of
            # the previous type
            pass

        else:
            yield self
            yield from self.reflect_arg_types(depth=depth-1)

    def get_types(self, depth=1):
        """Wrapper around `.reflect_types()` that returns the raw original
        type"""
        for rt in self.reflect_types(depth=depth):
            yield rt.get_origin_type()

    def reflect_arg_types(self, depth=-1):
        targets = []
        prt = self

        while depth < 0 or depth > 0:
            depth = depth - 1

            for at in prt.get_args():
                rt = self.create_reflect_type(at)
                targets.append((depth, rt))
                if rt.is_union():
                    if depth == 0:
                        # we only yield unions if we are at the end, if we
                        # aren't then they will get yielded when they are
                        # split apart
                        yield rt

                else:
                    yield rt

                if prt.is_annotated():
                    # only the first arg is a type in an Annotated
                    break

            if targets:
                depth, prt = targets.pop(0)

            else:
                break

    def get_arg_types(self, depth=-1):
        """Get the raw types of .target's args (eg, the types wrapped in the
        [] of the type (eg, dict[str, int] would yield str and int))

        :example:
            rt = ReflectType(dict[str, int|bool])
            list(rt.get_arg_types) # [str, int, bool]

        :returns: generator[type]
        """
        for rt in self.reflect_arg_types(depth=depth):
            yield rt.get_origin_type()

    def reflect_cast_types(self, depth=1):
        """Yields all the arg types that are considered castable

        :example:
            rt = ReflectType(Any)
            list(rt.reflect_cast_types()) # []

            rt = ReflectType(str|list[int])
            list(rt.reflect_cast_types()) # [str, list[int]]
            list(rt.reflect_cast_types(depth=-1)) # [str, list[int], int]

        :returns: Generator[ReflectType]
        """
        if self.is_annotated():
            for rt in self.reflect_arg_types(depth=depth):
                if rt.is_castable():
                    yield rt

        else:
            for rt in self.reflect_types(depth=depth):
                if rt.is_castable():
                    yield rt

    def reflect_key_types(self):
        """Reflect the types for the key types in a mapping

        :example:
            rt = ReflectType(dict[str, int|bool])
            list(rt.get_key_types) # [str]

        :returns: generator[ReflectType]
        :raises: ValueError, if `.get_target()` isn't a mapping
        """
        if self.is_dictish():
            for rt in self.reflect_arg_types(depth=1):
                yield from rt.reflect_types()
                break

        else:
            raise ValueError(
                f"Type {self.get_origin_type} is not a Mapping type"
            )

    def get_key_types(self):
        """Get the raw types for the keys in a mapping

        :example:
            rt = ReflectType(dict[str, int|bool])
            list(rt.get_key_types) # [str]

        :returns: generator[type]
        :raises: ValueError, if .target isn't a mapping
        """
        for rt in self.reflect_key_types():
            yield rt.get_origin_type()

    def reflect_value_types(self):
        """Get the value types of a container object

        Unlock many other `*_types()` methods with a depth argument this
        isn't recursive and only looks at the first set of arg types

        A value is the opposite of a key type (see `.get_key_types()`)

        :returns: generator[ReflectType]
        """
        for i, rt in enumerate(self.reflect_arg_types(depth=1)):
            if i == 0:
                if self.is_dictish():
                    continue

            if rt.is_union():
                for srt in rt.reflect_arg_types(depth=1):
                    yield srt

            else:
                yield rt

    def get_value_types(self):
        """Wrapper around `.reflect_value_types()` that returns the raw types

        :example:
            rt = ReflectType(dict[str, int|bool])
            list(rt.get_value_types) # [int, bool]

            rt = ReflectType(list[int|bool])
            list(rt.get_value_types) # [int, bool]

        :returns: generator[type]
        """
        for rt in self.reflect_value_types():
            yield rt.get_origin_type()

    def reflect_origin_types(self, depth=1):
        """Reflect all the origin types of the target type

        :returns: Generator[ReflectType]
        """
        yield from self.reflect_types(depth=depth)

    def get_origin_types(self, depth=1):
        """Wrapper around `.reflect_origin_types()`. Return all the raw origin
        types of the target type

        :example:
            rt = ReflectType(dict[str, int]|list[int])
            list(rt.get_origin_types()) # [dict, list]

        :returns: Generator[type]
        """
        for rt in self.reflect_origin_types(depth=depth):
            yield rt.get_origin_type()

    def get_origin_type(self):
        """Get the raw type of .target, this will normalize the value a bit
        so it is not just a wrapper like `.get_origin`

        :returns: type
        """
        return self.get_origin() or self.get_target()

    def get_origin(self):
        """Wrapper around `typing.get_origin`"""
        return get_origin(self.get_target())

    def get_args(self):
        """wrapper around `typing.get_args`

        :example:
            rt = ReflectType(str|int)
            list(rt.get_args()) # [str, int]

            rt = ReflectType(str)
            list(rt.get_args()) # []

            rt = ReflectType(dict[str, int])
            list(rt.get_args()) # [str, int]

            rt = ReflectType(Literal[1, 2, 3])
            list(rt.get_args()) # [1, 2, 3]

        This is different than `.get_arg_types` since it doesn't unwrap like
        that method does, this truly is just a wrapper around the
        typing function.

        :example:
            rt = ReflectType(dict[str, int|float])
            list(rt.get_args()) # [str, int|float]
            list(rt.get_arg_types()) # [str, int, float]

        :returns: Generator[type]
        """
        yield from get_args(self.get_target())

    def reflect_args(self):
        """Wrapper around `.get_arg_types` that returns ReflectType instances

        :returns: Generator[ReflectType]
        """
        for t in self.get_args():
            yield self.create_reflect_type(t)

    def get_metadata(self):
        """Returns the annotated metadata.

        An annotated type looks like `Annotated[<TYPE>, <METADATA...>] and
        so this will skip that first argument <TYPE> and return all the
        other arguments after <TYPE>.

        This has no idea what the metadata looks like

        :returns: Generator[Any]
        """
        if self.is_annotated():
            for i, arg in enumerate(self.get_args()):
                if i > 0:
                    yield arg

    def get_metadata_info(self) -> dict:
        """Normalize the metadata to positionals and keywords for easier
        processing"""
        info = {
            "positionals": [],
            "keywords": {},
        }
        for arg in self.get_metadata():
            if isinstance(arg, Mapping):
                info["keywords"].update(arg)

            else:
                info["positionals"].append(arg)

        return info

    def is_type(self, haystack) -> bool:
        """Returns True if .target's origin type is in haystack

        https://docs.python.org/3/library/functions.html#issubclass

        :param haystack: type|UnionType|tuple[type, ...]
        :returns: bool
        """
        needle = self.get_origin_type()

        #pout.v(needle, haystack)

        def is_subtype(haystack):
            for rt in self.reflect_arg_types(depth=1):
                if rt.is_type(haystack):
                    return True

            return False

        if needle is None or needle is Optional:
            return haystack is None

        elif needle is Any:
            return haystack is Any

        elif needle is Union or self._is_subclass(needle, types.UnionType):
            if haystack is Union or haystack is types.UnionType:
                return True

            elif haystack is Annotated:
                return False

            else:
                return is_subtype(haystack)

        elif needle is Annotated:
            if haystack is Annotated:
                return True

            else:
                return is_subtype(haystack)

        else:
            if haystack is None:
                if needle is None:
                    return True

                else:
                    if isinstance(needle, type):
                        return isinstance(None, needle)

            elif haystack is Any:
                return needle is Any

            else:
                return self._is_subclass(needle, haystack)

    def _is_subclass(self, needle, haystack) -> bool:
        """Internal method. Checks if needle is a subclass of haystack

        :param needle: type
        :param haystack: type|tuple[type, ...]
        """
        if not isinstance(needle, type):
            needle = type(needle)

        if not isinstance(haystack, type):
            if isinstance(haystack, tuple):
                for i in range(len(haystack)):
                    if not isinstance(haystack[i], type):
                        haystack[i] = type(haystack[i])

            else:
                haystack = type(haystack)

        return issubclass(needle, haystack)

    def is_subclass(self, haystack) -> bool:
        """Checks if `.get_target()` is a subclass of haystack

        :param haystack: type|tuple[type, ...]
        """
        return self._is_subclass(self.get_target(), haystack)

    def is_child(self, parent_type) -> bool:
        """Only returns True if .target's origin is an actual child of
        parent_type. Unlike issubclass it can't actually be parent_type

        :param parent_type: type, the parent, .target has to be a child
        :returns: bool, True if .target is a child
        """
        if self.is_type(parent_type):
            needle = self.get_origin_type()
            return needle is not parent_type

        return False

    def is_bool(self) -> bool:
        """Returns True if .target is a boolean"""
        return self.is_type(bool)

    def is_int(self):
        """Returns True if .target is an integer"""
        if self.is_union():
            for rt in self.reflect_arg_types(depth=1):
                if rt.is_int():
                    return True

            return False

        else:
            return not self.is_bool() and self.is_type(int)

    def is_any(self) -> bool:
        """Returns True if .target is the special type Any"""
        return self.is_type(Any)

    def is_union(self) -> bool:
        """Returns true if this is a union type (eg, `str|int`)"""
        return self.is_type(types.UnionType)

    def is_none(self) -> bool:
        """Returns True if .target is the special type None"""
        return self.is_type(None)

    def is_numberish(self) -> bool:
        """Returns True if .target is numeric and not a boolean"""
        return self.is_int() or self.is_floatish()

    def is_numeric(self) -> bool:
        """alias for `.is_numberish`"""
        return self.is_numberish()

    def is_floatish(self) -> bool:
        """Return True if .target is a number with a decimal"""
        return self.is_type((float, decimal.Decimal))

    def is_float(self) -> bool:
        return self.is_type(float)

    def is_str(self) -> bool:
        return self.is_type(str)

    def is_bytes(self) -> bool:
        return self.is_type((bytes, bytearray, memoryview))

    def is_ellipsis(self) -> bool:
        return self.is_type(...)

    def is_alias(self) -> bool:
        """generic aliases are things like `dict[str, int]`, because it has
        values set for the key and value types it is an alias"""
        return isinstance(t, types.GenericAlias)

    def is_dictish(self) -> bool:
        """Returns True if .target is a mapping

        This uses dictish instead of mapping because of sequence and list and
        str. Both list and str are sequences but many times when I am looking
        for a sequence I'm not looking for a string. So listish was more
        explicit for differentating lists and strings and so this follows
        that naming convention

        :returns: bool
        """
        return self.is_type(Mapping)

    def is_mapping(self) -> bool:
        """Alias of `.is_dictish()`"""
        return self.is_dictish()

    def is_stringish(self) -> bool:
        """Returns True if .target is string-like

        :returns: bool
        """
        return self.is_str() or self.is_bytes()

    def is_tuple(self) -> bool:
        """Returns True if .target is a tuple

        NOTE -- .is_listish will also return True for tuples
        """
        return self.is_type(tuple)

    def is_listish(self) -> bool:
        """Returns True if .target looks like a list and isn't a string

        :returns: bool
        """
        return (
            not self.is_str()
            and not self.is_bytes()
            and self.is_type(Sequence)
        )

    def is_list(self) -> bool:
        return self.is_type(list)

    def is_setish(self) -> bool:
        """Returns True if .target looks like a set

        :returns: bool
        """
        return self.is_type(Set) 

    def is_primitive(self) -> bool:
        """Return True if .target is a primitive type (str, int, float, bool,
        or None)"""
        return (
            self.is_stringish()
            or self.is_numberish()
            or self.is_none()
            or self.is_bool()
        )

    def is_literal(self) -> bool:
        """Returns true if this is a literal type containing literal values

        https://typing.python.org/en/latest/spec/literal.html
        https://docs.python.org/3.8/library/typing.html#typing.Literal
        https://peps.python.org/pep-0586/
        """
        return self.is_type(Literal)

    def is_annotated(self) -> bool:
        """Returns true if this type was annotated

        https://docs.python.org/3/library/typing.html#typing.Annotated
        """
        return self.is_type(Annotated)

    def is_castable(self) -> bool:
        """Returns True if this type is a castable type, meaning `self.cast`
        could work
        """
        return (
            not self.is_any()
            and not self.is_none()
            and not self.is_ellipsis()
            and not self.is_annotated()
        )

    def __instancecheck__(self, instance):
        """Returns True if instance is an instance of .target

        https://docs.python.org/3/reference/datamodel.html#class.__instancecheck__

        :param instance: object
        :returns: bool
        """
        if self.is_any():
            return True

        elif self.is_none():
            return instance is None

        else:
            return isinstance(instance, self.get_origin_type())

    def __subclasscheck__(self, subclass):
        """Returns True if subclass is a subclass of .target

        https://docs.python.org/3/reference/datamodel.html#class.__subclasscheck__

        :param subclass: type
        :returns: bool
        """
        if self.is_any():
            return True

        elif self.is_none():
            return subclass is None

        else:
            return issubclass(subclass, self.get_origin_type())

    def __str__(self):
        return str(self.get_target())

    def cast(self, value):
        """Cast `value` to a type in self

        This will move through the types from left to right and the first
        type that succeeds wins

        :param value: Any, this value will be cast to a type in self
        :returns: Any, an instance of one of the types in self
        """
        if self.is_any():
            return value

        if value is None and self.is_none():
            return value

        if self.is_literal():
            for choice in self.get_args():
                try:
                    t = type(choice)
                    r = t(value)

                    if r == choice:
                        return r

                except (ValueError, TypeError):
                    pass

        else:
            # we reflect all the actionable types to break apart special types
            # like Union or Annotated
            for rt in self.reflect_cast_types(depth=1):
                # broken special types can then have their types used
                # for casting
                for t in rt.get_types(depth=1):
                    try:
                        r = t(value)

                        if rt.is_listish():
                            # if we have a value type then we want to cast
                            # all the items in the list to that value type
                            for rit in rt.reflect_value_types():
                                try:
                                    for index in range(len(r)):
                                        r[index] = rit.cast(r[index])

                                except ValueError:
                                    pass

                        return r

                    except (ValueError, TypeError):
                        pass

        raise ValueError(f"Could not cast value to {self}")


class ReflectArgument(ReflectObject):
    """Internal class. Reflect a passed in argument to a method

    This will almost always be used through calling
    `ReflectCallable.reflect_arguments()`

    This is used to represent both bound and unbound arguments.

    `inspect.Parameter.empty` is used to represent a missing value.

    If it represents a missing argument, it will be unbound with an empty
    value.

    If it represents unmatched positionals, its value will be the remaining
    passed in positional arguments that weren't consumed and `.get_target()`
    will return None.

    If it represents unmatched keywords, its value will be a dict of the
    passed in keyword arguments that weren't consumed and `.get_target()` will
    return None.
    """
    @property
    def param(self):
        return self.get_target()

    @property
    def name(self):
        """This will be an empty string if it represents an unbound remainder
        otherwise it will be the name of the parameter"""
        name = ""
        if target := self.get_target():
            name = target.name

        return name

    def __init__(self, target, value, reflect_callable, **kwargs):
        """
        :param target: inspect.Parameter|None, if a Parameter instance then
            `value` was successfully bound (unless it's empty). If None then
            `value` is unbounded
        :param value: Any, the value to bind. `inspect.Parameter.empty` means
            the value doesn't exist. So if target is not None it means that
            parameter wasn't found when binding the arguments
        :param reflect_callable: ReflectCallable, the callable that is binding
            the arguments
        :keyword positional: bool, True if `target` was bound as a positional
            argument
        :keyword keyword: bool, True if `target` was bound as a keyword
            argument
        :keyword keyword_value: Any, if `target` is being bound as a
            positional but there was also a keyword value this will be passed
            in, if this key is not passed in then there are not multiple
            values for the target param
        """
        super().__init__(target)

        self._reflect_callable = reflect_callable
        self.value = value
        self.kwargs = kwargs

    def get_class(self):
        return self.reflect_callable().get_class()

    def reflect_callable(self):
        return self._reflect_callable

    def get_docblock(self):
        if rdb := self.reflect_callable().reflect_docblock():
            descs = rdb.get_param_descriptions()
            return descs.get(self.name, None)

    def is_bound_positional(self) -> bool:
        """True if a bound positional argument is represented"""
        return self.is_bound() and self.kwargs.get("positional", False)

    def is_bound_keyword(self) -> bool:
        """True if a bound keyword argument is represented"""
        return self.is_bound() and self.kwargs.get("keyword", False)

    def is_bound(self) -> bool:
        """True if this instance is a bound argument"""
        return (
            self.get_target() is not None
            and self.has_bound_value()
        )

    def is_unbound_positionals(self) -> bool:
        """True if this instance are the leftover positionals that weren't
        bound and there is no catch-all argument like `*args` in the
        signature"""
        return (
            self.get_target() is None
            and self.kwargs.get("positional", False)
        )

    def is_unbound_keywords(self) -> bool:
        """True if this instance are the leftover keywords that weren't
        bound and there is no catch-all argument like `**kwargs` in the
        signature"""
        return (
            self.get_target() is None
            and self.kwargs.get("keyword", False)
        )

    def is_unbound(self) -> bool:
        """True if this instance is unbound"""
        return (
            not self.is_bound()
            or self.is_unbound_positionals()
            or self.is_unbound_keywords()
        )

    def is_catchall(self) -> bool:
        """True if this is a bound or unbound catch-all"""
        kinds = (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        )

        return (
            self.is_unbound()
            or self.get_target().kind in kinds
        )

    def is_positional(self) -> bool:
        """True if the parameter can be passed in as a positional

        Both this and `.is_keyword()` can be True
        """
        ret = False

        if param := self.get_target():
            kinds = (
                param.POSITIONAL_ONLY,
                param.VAR_POSITIONAL,
                param.POSITIONAL_OR_KEYWORD,
            )
            ret = param.kind in kinds

        else:
            ret = self.is_unbound_positionals()

        return ret

    def is_keyword(self) -> bool:
        """True if the parameter can be passed in as a keyword

        Both this and `.is_positional()` can be True
        """
        ret = False

        if param := self.get_target():
            kinds = (
                param.KEYWORD_ONLY,
                param.VAR_KEYWORD,
                param.POSITIONAL_OR_KEYWORD,
            )
            ret = param.kind in kinds

        else:
            ret = self.is_unbound_keywords()

        return ret

    def has_bound_value(self) -> bool:
        """True if this argument has a bound value

        This does not take into account default values
        """
        return self.value is not inspect.Parameter.empty

    def has_value(self) -> bool:
        """True if this argument has a value, taking into account default
        values also"""
        ret = self.has_bound_value()
        if not ret:
            if param := self.get_target():
                if param.default is not param.empty:
                    ret = True

        return ret

    def has_positional_value(self) -> bool:
        """True if the value is from a positional argument"""
        return self.has_value() and self.is_bound_positional()

    def has_keyword_value(self) -> bool:
        """True if the value is from a keyword argument

        This can be True even if `.has_positional_value()` is also True and
        would represent a "too many arguments" TypeError
        """
        return (
            self.has_value()
            and (
                self.is_bound_keyword()
                or "keyword_value" in self.kwargs
            )
        )

    def has_multiple_values(self) -> bool:
        """True if multiple values for this argument were passed in"""
        return (
            self.has_value()
            and "keyword_value" in self.kwargs
        )

    def get_keyword_value(self):
        """Return the keyword value or `inspect.Parameter.empty` if it doesn't
        exist"""
        if self.is_bound_keyword():
            return self.value

        else:
            return self.kwargs.get("keyword_value", inspect.Parameter.empty)

    def get_positional_value(self):
        """Return the positional value or `inspect.Parameter.empty` if it
        doesn't exist"""
        if self.is_bound_positional():
            return self.value

        return inspect.Parameter.empty

    def get_value(self):
        """Return the value of this argument, this will return the default
        value if it exists"""
        empty = inspect.Parameter.empty
        v = self.value
        if v is empty:
            v = self.get_keyword_value()

        if v is empty:
            if param := self.get_target():
                if param.default is not empty:
                    v = param.default

        return v

    def has_default_value(self) -> bool:
        """True if a default parameter exists"""
        ret = False

        if param := self.get_target():
            ret = param.default is not param.empty

        return ret

    def has_annotation(self) -> bool:
        """True if the parameter has a type annotation"""
        ret = False

        if param := self.get_target():
            ret = param.annotation is not param.empty

        return ret


class ReflectCallable(ReflectObject):
    """Reflect a callable

    Types of callables this supports:
        * class instance with __call__ method
        * A method defined in a class, including @classmethod and
            @staticmethod wrapped methods
        * A function that isn't defined in a class

    This is a refactoring of ReflectMethod that was moved here from
    endpoints.reflection.ReflectMethod on Jan 31, 2023
    """
    @cachedproperty()
    def name(self):
        name = getattr(self.target, "__name__", "")
        if not name:
            name = self.target.__class__.__name__

        # let's verify the name
        parent = self.get_parent()
        o = getattr(parent, name, None)
        if o is not self.target:
            # this is for a badly behaved decorator (eg, not using
            # functools.wraps) so let's check all the mambers and see
            # if we can find a matching object
            for n, v in inspect.getmembers(parent):
                if v is self.target:
                    name = n
                    break

        return name

    @property
    def modpath(self):
        return self.target.__module__

    @property
    def classpath(self):
        """return the full classpath of the callable if callable is a method

        :returns: str, the full classpath (eg, foo.bar.che:Classname) or
            empty string if callable is not a method
        """
        ret = ""
        if klass := self.get_class():
            ret = ":".join([
                self.modpath,
                klass.__qualname__
            ])

        return ret

    @property
    def callpath(self):
        """Returns the full call path for this callable

        :returns: str, the full callpath (eg foo.bar:<CALLABLE_QUALNAME>)
        """
        return ":".join([
            self.modpath,
            self.get_target().__qualname__
        ])

    @property
    def signature(self):
        """Passthrough for `inspect.signature(self.get_target())`"""
        return inspect.signature(self.get_target())

    def __init__(self, target, target_class=None, *, name=""):
        """
        :param function: callable, the callable
        :param target_class: type, if target is a method and you've got access
            to the class target was defined in then it would be best to pass it
            in here so .find_class doesn't have to actually try and find the
            class. If target is a class instance and you have the class you
            can also pass it here
        :param name: str, if you have access to target's name then it would
            be best to pass it in here so it won't have to try and find it,
            finding the name can fail if target is wrapped with a misbehaving
            decorator that doesn't set __wrapped__ or things like that
        :raises: ValueError, if function isn't callable
        """
        if not callable(target):
            raise ValueError(f"Passed in callable {target} is not callable")

        super().__init__(target)

        self.target_class = target_class
        if name:
            self.name = name

    def __call__(self, *args, **kwargs):
        return self.target(*args, **kwargs)

    def get_docblock(self, inherit=False):
        doc = super().get_docblock()
        if not doc:
            # functions/methods can be wrapped by bad decorators that don't
            # correctly wrap, so let's try and parse the docblock before
            # giving up
            doc = ast.get_docstring(self.get_ast()) or ""

        return doc or ""

    def infer_qualname(self):
        """Reflection doesn't assume .target.__qualname__ is correct, this
        can sometimes be good (bad decorators that don't wrap correctly and
        set __wrapped__) and sometimes it can be bad (function is defined
        in <locals>)

        Basically, there is no guarrantee .target.__qualname__ is equal to
        .infer_qualname

        :returns: str, the computed qualname, it is not always the
            valid actual qualname for .target because it can't see <locals>
        """
        qualname = []
        if self.is_class():
            qualname.append(target.__qualname__)

        elif self.is_instance():
            qualname.append(target.__class__.__qualname__)

        else:
            try:
                if target_class := self.get_class():
                    qualname.append(target_class.__qualname__)

            except ValueError:
                pass

        qualname.append(self.name)
        return ".".join(qualname)

    def get_parent(self):
        """Get where this callable is defined, if it's a method that will
        hopefully be a class, otherwise a module

        :returns: type|types.ModuleType
        """
        return self.reflect_parent().get_target()

    def reflect_parent(self):
        """Get where this callable is defined, if it's a method that will
        hopefully be a class, otherwise a module

        :returns: type|types.ModuleType
        """
        if self.is_class() or self.is_instance():
            return self.reflect_module()

        else:
            try:
                return self.reflect_class()

            except ValueError:
                return self.reflect_module()

    def get_class(self):
        """Get the class for the callable

        :returns: type|None
            - Returns the class a method is defined in if it's
                possible to find it.
            - Returns the class if callable is an instance or class
            - Returns None if callable is a function
        :raises: ValueError if the class can't be found and it wasn't passed in
        """
        if not self.target_class:
            if self.is_class():
                self.target_class = self.target

            elif self.is_instance():
                self.target_class = self.target.__class__

            else:
                self.target_class = self.find_class(self.target)

        return self.target_class

    def find_class(self, cb):
        """Try everything it can to find the class where `cb` is defined.

        This is largely based on these two answers:
            * https://stackoverflow.com/a/25959545
            * https://stackoverflow.com/a/54597033
        """
        if isinstance(cb, functools.partial):
            return self.find_class(cb.func)

        if (
            inspect.ismethod(cb)
            or (
                inspect.isbuiltin(cb)
                and getattr(cb, '__self__', None) is not None
                and getattr(cb.__self__, '__class__', None)
            )
        ):
            cls = cb.__self__
            if isinstance(cls, type):
                return cls

            else:
                return cls.__class__

        if inspect.isfunction(cb):
            class_parts = cb.__qualname__.split(".")
            if len(class_parts) == 1:
                return None

            try:
                cls = getattr(inspect.getmodule(cb), class_parts[0])

            except AttributeError:
                cls = cb.__globals__.get(class_parts[0])

            if cls:
                for class_name in class_parts[1:-1]:
                    # https://peps.python.org/pep-3155/
                    # With nested functions (and classes defined inside
                    # functions), the dotted path will not be walkable
                    # programmatically as a function’s namespace is not
                    # available from the outside.
                    if "<" in class_name:
                        raise ValueError(
                            "Classes inside functions cannot be retrieved"
                            f": {cb.__qualname__}"
                        )

                    cls = getattr(cls, class_name)

            if isinstance(cls, type):
                return cls

        # handle special descriptor objects
        return getattr(cb, '__objclass__', None)

    def get_descriptor(self):
        """Get the descriptor of the callable, this only returns something
        if the callable is defined in a class (ie, it's a method/property)

        :returns: callable, the descriptor
        :raises: ValueError, if a class can't be found
        """
        cb_class = self.get_class()
        if cb_class:
            cb_descriptor = inspect.getattr_static(
                cb_class,
                self.name,
                None
            )

        else:
            cb_descriptor = self.target

        return cb_descriptor

    def get_unwrapped(self, **kwargs):
        """Find the original wrapped function. This takes advantage of
        functools.update_wrapper's automatic setting of the __wrapped__
        variable and assumes the original func is the one that doesn't have
        the variable

        :returns: callable, the original wrapped callable if it exists
        """
        return inspect.unwrap(self.target, **kwargs)
        #func = self.target
        #while wrapped := getattr(func, "__wrapped__", None):
        #    func = wrapped
        #return func

    def is_class(self):
        """Returns True if this is a class, in which case the callable is
        the __init__ method if the class is mutable and the __new__ method
        if it is immutable
        """
        return isinstance(self.target, type)

    def is_instance(self):
        """Returns True if the callable is an instance of a class with a
        `__call__` method defined

        :returns: bool
        """
        # special handling for functools partial instances since they
        # shouldn't be considered the actual callable
        cb = self.target
        if isinstance(cb, functools.partial):
            cb = cb.func

        # class instances don't have a qualifying name
        ret = False
        qname = getattr(cb, "__qualname__", "")
        if not qname:
            ret = not self.is_class()

        return ret

    def is_function(self):
        """Returns True if this is just a plain old function defined outside
        of a class

        :returns: bool
        """
        return (
            isinstance(self.target, types.FunctionType)
            and not self.is_method()
        )

    def is_instance_method(self):
        """Returns True if this is classic instance method defined in a class

        An instance method is usually a method whose first argument is self

        :returns: bool
        """
        return (
            self.is_method()
            and not self.is_classmethod()
            and not self.is_staticmethod()
        )

    def is_method(self):
        """Returns True if the callable is a method, this is all encompassing
        so static and class methods are also methods because they are also
        defined on a class

        Use .is_instance_method if you just want to know if this is a
        traditional method of a class

        :returns: bool
        """
        ret = isinstance(self.target, types.MethodType)
        if not ret:
            name = getattr(self.target, "__qualname__", "")
            # if the fully qualified name has a period it's a method
            # unless it's something like <locals>.<NAME> then it is a
            # function
            if "." in name and not re.search(r">\.[^\.]+$", name):
                ret = True

        return ret

    def is_staticmethod(self):
        """Return True if the callable is a static method

        https://stackoverflow.com/questions/31916048/

        The actual c code for the staticmethod decorator is here:
            https://github.com/python/cpython/blob/main/Objects/funcobject.c#L1392

        A static method is a usually a method defined on a class with the
        @staticmethod decorator

        In order to tell if a method is static you have to have access to
        the class that the method is defined in because a static method uses
        the descriptor protocol so you have to retrieve the actual descriptor
        instance from the class. I was not able to figure out any other way
        to do it and I looked, believe me I looked

        :returns: bool, True if this callable is a static method
        """
        ret = isinstance(self.target, staticmethod)
        if not ret:
            cb_descriptor = self.get_descriptor()
            ret = isinstance(cb_descriptor, staticmethod)

        return ret

    def is_classmethod(self):
        """Returns True if the callable is a class method

        A class method is a method defined on a class using the @classmethod
        decorator and usually has `cls` as the first argument

        Class methods have __self__ and __func__ attributes

        :returns: bool
        """
        v = getattr(self.target, "__self__", None)
        return isinstance(v, type)

    def is_bound_method(self):
        """Returns True if callable is a bound method

        This is a little inside baseball, but basically a bound method is
        the method object returned from an instance

        :example:
            class Foo(object):
                def bar(self): pass

                @classmethod
                def che(cls): pass

            ReflectCallable(Foo.bar).is_bound_method() # False
            ReflectCallable(Foo().bar).is_bound_method() # True

            ReflectCallable(Foo.che).is_bound_method() # True
            ReflectCallable(Foo().che).is_bound_method() # True

        :returns: bool
        """
        ret = False
        if getattr(self.target, "__self__", None):
            ret = True

        return ret

    def is_unbound_method(self):
        """Returns True if this is an unbound instance method

        This will only ever be True for an instance method that isn't bound.
        This isn't synonomous with `not self.is_bound_method` because there
        needed to be a way to tell the different between an unbound method
        and a function, which will both return True for
        `not .is_bound_method()`

        :example:
            def func(): pass

            rf = ReflectCallable(func)
            rf.is_bound_method() # False
            rf.is_unbound_method() # False

            class Foo(object):
                def method(self): pass

            rf = ReflectCallable(Foo.method, Foo)
            rf.is_bound_method() # False
            rf.is_unbound_method() # True

            rf = ReflectCallable(Foo().method, Foo)
            rf.is_bound_method() # True
            rf.is_unbound_method() # False

        :returns: bool
        """
        return self.is_instance_method() and not self.is_bound_method()

    def create_reflect_argument(self, *args, **kwargs):
        """Internal method to create ReflectArgument instances"""
        ra_class = kwargs.pop("reflect_argument_class", ReflectArgument)
        return ra_class(
            *args,
            reflect_callable=self,
            **kwargs,
        )

    def get_params(self):
        """This gets the params that can be bounded

        This method ignores `self` or `cls` as the first argument when it
        looks to be present so all callables will have the same signature
        that lines up with passed in `*args` and `**kwargs`. The bound class
        or instance argument is ignored because it is automatically bound
        by python when the method is called

        :returns: Generator[inspect.Parameter]
        """
        # we skip the first argument if it's a method that usually has self
        # or cls as the first argument. This only applies if we passed in the
        # non-bound version of the method though, so we also check 
        skip = self.is_unbound_method()
        signature = self.signature
        for param in signature.parameters.values():
            if skip:
                skip = False
                continue

            yield param

    def get_bind_info(self, *args, **kwargs):
        """Get information on how callable could bind *args and **kwargs

        https://docs.python.org/3/library/inspect.html#inspect.Signature.bind
        https://docs.python.org/3/library/inspect.html#inspect.BoundArguments

        :param *args: all the positional arguments for callable
        :param **kwargs: all the keyword arguments for callable
        :returns: dict[str, dict[str, Any]|list[Any]|set[str]]
            - reflect_arguments: list[ReflectArgument], the RefelctArgument
                instances used to gather the info
            - unbound_args: list[Any], all positional values that failed to be
                bound
            - unbound_kwargs: dict[str, Any], all keywords that failed to
                be bound
            - missing_names: set[str], the required parameter names that
                weren't found in the passed in arguments
            - multiple_names: set[str], any param names that received multiple
                values
            - bound_names: set[str], all the param names that were
                successfully bound
            - bound_args: list[Any], the successfully bound argument values
                from the passed in `args`
            - bound_kwargs: dict[str, Any], the successfully bound keyword
                values from the passed in `kwargs`
        """
        ret = {
            "reflect_arguments": [],
            "unbound_args": [],
            "unbound_kwargs": {},
            "missing_names": set([]),
            "multiple_names": set([]),
            "bound_names": set([]),
            "bound_args": [],
            "bound_kwargs": {},
        }

        for ra in self.reflect_arguments(*args, **kwargs):
            ret["reflect_arguments"].append(ra)

            if ra.is_bound():
                if ra.is_bound_positional():
                    if ra.is_catchall():
                        ret["bound_args"].extend(ra.value)

                    else:
                        ret["bound_names"].add(ra.name)
                        ret["bound_args"].append(ra.value)

                elif ra.is_bound_keyword():
                    if ra.is_catchall():
                        ret["bound_kwargs"].update(ra.value)

                    else:
                        ret["bound_names"].add(ra.name)
                        ret["bound_kwargs"][ra.name] = ra.value

                if ra.has_multiple_values():
                    ret["multiple_names"].add(ra.name)

            else:
                if ra.is_unbound_positionals():
                    ret["unbound_args"] = ra.value

                elif ra.is_unbound_keywords():
                    ret["unbound_kwargs"] = ra.value

                else:
                    ret["missing_names"].add(ra.name)

        return ret

    def reflect_arguments(self, *args, **kwargs):
        """Reflect the bindings for `*args` and `**kwargs`

        The functionality of this method is based on the source of
        `inspect.Signature._bind`

        :arguments *args: these are bound to the method's params
        :keyword **kwargs: these are bound to the method's params
        :returns: Generator[ReflectArgument], each param in the signature
            will be yielded as will any remaining positionals and keywords.
            This allows custom interfaces to move through argument binding
            without worrying about TypeErrors being raised so the custom
            interface can decide what to do with invalid input like multiple
            arguments or missing arguments
        """
        arg_vals = iter(args)
        params = iter(self.get_params())

        while True:
            # Let's iterate through the positional arguments and corresponding
            # parameters
            param = None

            try:
                arg_val = next(arg_vals)

            except StopIteration:
                # No more positional arguments
                break

            else:
                # We have a positional argument to process
                try:
                    param = next(params)

                except StopIteration:
                    # we have a positional value but no more signature params
                    # so all the remaining values are unbound
                    yield self.create_reflect_argument(
                        None,
                        [arg_val] + list(arg_vals),
                        positional=True,
                    )

                    #param = None
                    break

                else:
                    if param.kind == param.VAR_POSITIONAL:
                        # we've found the *args param
                        yield self.create_reflect_argument(
                            param,
                            [arg_val] + list(arg_vals),
                            positional=True,
                        )

                    elif param.kind in (param.VAR_KEYWORD, param.KEYWORD_ONLY):
                        # we've hit the keywords so all remaining positionals
                        # are unbound
                        yield self.create_reflect_argument(
                            None,
                            [arg_val] + list(arg_vals),
                            positional=True,
                        )
                        break

                    else:
                        ra_kwargs = {
                            "positional": True,
                        }

                        # value was passed as both an arg and kwarg
                        if param.name in kwargs:
                            ra_kwargs["keyword_value"] = kwargs.pop(param.name)

                        yield self.create_reflect_argument(
                            param,
                            arg_val,
                            **ra_kwargs,
                        )

        keywords_param = None

        if param:
            params = itertools.chain([param], params)

        for param in params:
            if param.kind == param.VAR_KEYWORD:
                # found the **kwargs param
                keywords_param = param
                continue

            elif param.kind == param.VAR_POSITIONAL:
                # we ignore the *arg param since we consumed all the args
                continue

            elif param.kind == param.POSITIONAL_ONLY:
                ra_kwargs = {
                    "positional": True,
                }

                # value was passed as a keyword but it needed to be a
                # positional and we've run out of positionals
                if param.name in kwargs:
                    ra_kwargs["keyword_value"] = kwargs.pop(param.name)
                    ra_kwargs["positional"] = False
                    ra_kwargs["keyword"] = True

                yield self.create_reflect_argument(
                    param,
                    param.empty,
                    **ra_kwargs,
                )

            else:
                try:
                    arg_val = kwargs.pop(param.name)

                except KeyError:
                    yield self.create_reflect_argument(
                        param,
                        param.empty,
                        keyword=True,
                    )

                else:
                    yield self.create_reflect_argument(
                        param,
                        arg_val,
                        keyword=True,
                    )

        if kwargs:
            yield self.create_reflect_argument(
                keywords_param,
                kwargs,
                keyword=True,
            )

    def get_signature_info(self):
        """Get call signature information of the reflected function

        Moved from captain.reflection and refactored on 7-17-2024

        :returns: dict[str, str|set|list|dict]
            - signature: the inspect signature
            - names: list[str], all the param names in the order they are
                defined in the signature
            - indexes: dict[int, str], the reverse of the `names` key, it
                maps argument index to argument name
            - positional_only_names: set[str], the set of names that can
                only be passed in as positionals
            - keyword_only_names: set[str], the set of names taht can
                only be passed in as keywords
            - required: dict[str, Any], the default values for any of the
                names
            - positionals_name: str, the name of the *args-like param that
                captures all undefined positionals passed into the callable
            - keywords_name: str, the name of the **kwargs-like param that
                captures all undefined keywords passed into the callable
            - annotations: dict[str, type], the found types for any of the
                names
        """
        ret = {
            "names": [],
            "indexes": {},

            # https://peps.python.org/pep-0570/
            "positional_only_names": set(),
            "keyword_only_names": set(),

            "required": set(),
            "defaults": {},
            "annotations": {},
            "positionals_name": "",
            "keywords_name": "",
        }

        index = 0

        for param in self.get_params():
            name = param.name
            check_required = True

            if param.kind is param.POSITIONAL_ONLY:
                ret["positional_only_names"].add(name)

            elif param.kind is param.KEYWORD_ONLY:
                ret["keyword_only_names"].add(name)

            elif param.kind is param.VAR_POSITIONAL:
                ret["positionals_name"] = name
                check_required = False

            elif param.kind is param.VAR_KEYWORD:
                ret["keywords_name"] = name
                check_required = False

            if check_required:
                if param.default is param.empty:
                    ret["required"].add(name)

                else:
                    ret["defaults"][name] = param.default

            if param.annotation is not param.empty:
                ret["annotations"][name] = param.annotation

            ret["names"].append(name)
            ret["indexes"][name] = index
            index += 1

        return ret

    def has_positionals_catchall(self) -> bool:
        """returns True if the callable signature contains a positional
        arguments catch-all variable (eg, `*args`)"""
        for param in self.signature.parameters.values():
            if param.kind is param.VAR_POSITIONAL:
                return True

        return False

    def has_keywords_catchall(self) -> bool:
        """returns True if the callable signature contains a keyword only
        arguments catch-all variable (eg, `**kwargs`)"""
        for param in self.signature.parameters.values():
            if param.kind is param.VAR_KEYWORD:
                return True

        return False

    def getsource(self):
        """get the source of the callable if available

        :returns: str|None
        """
        return inspect.getsource(self.get_target())

    def get_ast(self):
        """Get the abstract syntax tree for this callable

        :returns: ast.AST
        """
        class _Finder(inspect._ClassFinder):
            node = None
            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                qualname = ".".join(self.stack)
                if qualname == self.qualname[0]:
                    self.node = node
                    raise StopIteration()

                else:
                    # These checks aren't 100% sure so we set it but don't stop
                    # checking looking for a more definitive check
                    if qualname in self.qualname:
                        self.node = node

                    else:
                        for qn in self.qualname:
                            if qn.endswith("." + qualname):
                                self.node = node
                    self.stack.pop()
                    super().visit_FunctionDef(node)
            visit_AsyncFunctionDef = visit_FunctionDef

        qualnames = [
            self.infer_qualname(),
            self.get_target().__qualname__
        ]

        finder = _Finder(qualnames)

        rp = self.reflect_parent()
        try:
            if rp.is_module():
                finder.visit(rp.get_ast())

            else:
                # this method might belong to parent but that doesn't mean it's
                # defined in parent, so we need to check all the parents of
                # parent also until we find the actual definition
                for rc in self.reflect_parent().reflect_mro():
                    finder.visit(rc.get_ast())

        except StopIteration:
            pass

        return finder.node

    def reflect_supers(self):
        """Reflect all the parent methods that are called via super in
        the body of this method

        :returns: generator[ReflectCallable]
        """
        rc = self.reflect_class()
        method_name = self.name
        node = self.get_ast()

        for n in ast.walk(node):
            # looking for a super call in the body of the method
            if isinstance(n, ast.Call):
                try:
                    if n.func.value.func.id == "super":
                        if n.func.attr == method_name:
                            for prc in rc.reflect_parents():
                                if prc.has_definition(method_name):
                                    prm = prc.reflect_method(method_name)
                                    yield prm
                                    yield from prm.reflect_supers()
                                    break

                except AttributeError:
                    pass

    def reflect_ast_decorators(self):
        """Reflect all the decorators wrapping this callable

        :returns: generator[ReflectAST]
        """
        for node in self.get_ast().decorator_list:
            yield self.create_reflect_ast(
                node,
                reflect_callable=self
            )

    def reflect_ast_raises(self):
        """Reflect all the raised exception nodes in the callable body

        :returns: generator[ReflectAST]
        """
        class _Finder(ast.NodeVisitor):
            nodes = []
            parent = None
            def find_exc_handlers(self, node):
                n = node.parent
                while n and not isinstance(n, ast.ExceptHandler):
                    n = n.parent

                if n:
                    if isinstance(n.type, ast.Tuple):
                        # except (Exc1, Exc2, ...)
                        for tn in n.type.elts:
                            yield tn

                    else:
                        yield n.type

            def visit_Raise(self, node):
                if node.exc:
                    if isinstance(node.exc, ast.Call):
                        # A standard raise <EXC-NAME>(...)
                        self.nodes.append(node.exc)

                    else:
                        # something like `raise e` so find the handler(s)
                        for n in self.find_exc_handlers(node):
                            self.nodes.append(n)

                else:
                    # raise with no arguments so find the handler(s)
                    for n in self.find_exc_handlers(node):
                        self.nodes.append(n)

            def visit(self, node):
                """Overridden to set parent so we can traverse the tree"""
                node.parent = self.parent
                prev_parent = self.parent
                self.parent = node
                ret = super().visit(node)
                self.parent = prev_parent
                return ret

        finder = _Finder()
        finder.visit(self.get_ast())
        for node in finder.nodes:
            yield self.create_reflect_ast(
                node,
                reflect_callable=self
            )

    def reflect_ast_returns(self):
        """Reflect all the return nodes in the abstract syntax tree

        :returns: generator[ReflectAST]
        """
        class _Finder(ast.NodeVisitor):
            nodes = []
            def visit_Return(self, node):
                if node.value:
                    self.nodes.append(node.value)

        finder = _Finder()
        node = self.get_ast()
        finder.visit(node)
        for node in finder.nodes:
            yield self.create_reflect_ast(
                node,
                reflect_callable=self
            )

    def reflect_return_type(self):
        """Reflect the defined return annotation, this only returns something
        if a return type annotation has been added to the callable definition

        :Example:
            def foo() -> int:
                # this has a type annotation and so will return something
                return 1

            def bar():
                # this has no annotation so is None

        :returns: ReflectType|None, None will be returned if there is no
            annotation, otherwise a reflection instance is returned
        """
        ret = None
        annotations = self.get_target().__annotations__
        if "return" in annotations:
            ret = self.create_reflect_type(annotations["return"])

        return ret


class ReflectClass(ReflectObject):
    """
    Moved from endpoints.reflection.ReflectClass on Jan 31, 2023
    """
    @property
    def modpath(self):
        """the module name that this class is defined in"""
        return self.target.__module__

    @property
    def classpath(self):
        """The full classpath of self.target

        should this use the currently suggested syntax of modpath:Classname?
        instead of the backwards compatible modpath.Classname?

        https://docs.python.org/3/library/pkgutil.html#pkgutil.resolve_name

        :returns: str, "modpath:QualifiedClassname", the full classpath (eg,
            foo.bar.che:Classname)
        """
        return ":".join([
            self.target.__module__,
            self.target.__qualname__
        ])

    def __init__(self, target, target_module=None, *, name=""):
        """
        :param target: type|object, the class to reflect
        :param target_module: types.ModuleType, the module the class was
            defined in
        :param name: str, usually not needed but more information is always
            better just in case the class has been badly decorated or
            something
        """
        if inspect.isclass(target):
            target = target
        else:
            target = target.__class__

        super().__init__(target)

        self.target_module = target_module
        self.name = name or self.target.__name__

    def is_private(self):
        """return True if this class is considered private"""
        return self.name.startswith('_')

    def get_module(self):
        """returns the actual module this class is defined in"""
        return self.target_module or self.reflect_module().get_module()

    def reflect_module(self):
        """Returns the reflected module"""
        return self.create_reflect_module(
            self.target_module or self.target.__module__
        )

    def get_class(self):
        return self.target

    def get_method_names(self):
        methods = inspect.getmembers(self.target, inspect.ismethod)
        for method_name, method in methods:
            yield method_name

    def get_methods(self):
        for rc in self.reflect_methods():
            yield rc.target

    def reflect_methods(self):
        """Yield all the methods defined in this class

        :returns: generator, yields ReflectMethod instances
        """
        methods = inspect.getmembers(self.target, inspect.ismethod)
        for method_name, method in methods:
            yield self.create_reflect_callable(
                method,
                target_class=self.target,
                name=method_name
            )

    def reflect_method(self, method_name):
        """Returns information about the method_name on this class

        :param method_name: str, the name of the method
        :param *default_val: mixed, if passed in return this instead of raising
            error
        :returns: ReflectMethod, the reflection information about the method
        """
        return self.create_reflect_callable(
            getattr(self.target, method_name),
            target_class=self.target,
            name=method_name
        )

    def get(self, name, *default_val):
        """Get a value on the class

        :param name: str, the attribute name you want
        :param *default_val: mixed, return this if name doesn't exist
        :returns: mixed, the raw python attribute value
        """
        return getattr(self.target, name, *default_val)

    def getmembers(self, predicate=None, **kwargs):
        """Get all the actual members of this class, passthrough for
        inspect.getmembers

        :param predicate: callable[type], this callback will passed through
            to `inpsect.getmembers`
        :param **kwargs:
            * regex: str, a regex that will be used to filter the members by
                name
            * name_redicate: callable[str], a callback that will be used to
                filter the members by name, returns True to yield the member
        :returns: generator[Any]
        """
        regex = kwargs.pop("regex", "")
        name_predicate = kwargs.pop("name_predicate", None)

        for name, member in inspect.getmembers(self.target, predicate):
            if regex and re.search(regex, name, re.I):
                yield name, member

            elif name_predicate and name_predicate(name):
                yield name, member

            else:
                yield name, member

    def get_parents(self, *args, **kwargs):
        """Get all the parent classes up to cutoff_class

        see .getmro

        :returns: generator[type]
        """
        # we have to compensate for this not yielding itself
        if "depth" in kwargs:
            kwargs["depth"] += 1

        for parent_class in self.getmro(*args, **kwargs):
            if parent_class is not self.target:
                yield parent_class

    def reflect_parents(self, *args, **kwargs):
        """Same as .get_parents but returns ReflectClass instances"""
        for parent_class in self.get_parents(*args, **kwargs):
            yield self.create_reflect_class(parent_class)

    def getmro(self, *, depth=0, cutoff_class=object):
        """Get the classes for method resolution order, this is basically
        class and all its parents up to cutoff_class (if passed in)

        passthrough for inspect.getmro with extra options

        :param depth: int, similar to cutoff_class, only get the parents to
            this depth, if you pass in 1 then it will get the immediate parent
        :param cutoff_class: type, iterate the classes ending at this class
        :returns: generator[type]
        """
        for i, klass in enumerate(inspect.getmro(self.target)):
            if cutoff_class and klass is cutoff_class:
                break

            if depth and i == depth:
                break

            else:
                yield klass

    def reflect_mro(self, *args, **kwargs):
        """Same as .getmro but returns ReflectClass instances"""
        for klass in self.getmro(*args, **kwargs):
            yield self.create_reflect_class(klass)

    def getsource(self):
        return inspect.getsource(self.target)

    def get_ast(self):
        target = self.get_class()
        tree = self.reflect_module().get_ast()

        class _ClassFinder(inspect._ClassFinder):
            node = None
            def visit_ClassDef(self, node):
                self.node = node
                super().visit_ClassDef(node)

        class_finder = _ClassFinder(target.__qualname__)
        try:
            class_finder.visit(tree)

        except inspect.ClassFoundException:
            return class_finder.node


class ReflectModule(ReflectObject):
    """Introspect on a given module name/path (eg foo.bar.che)

    Moved from endpoints.reflection.ReflectModule on Jan 31, 2023
    """
    @property
    def module_basename(self):
        """Return the modules basename (eg, if the module's name was
        "foo.bar.che" then the module basename would be "che")
        """
        return self.name.split(".")[-1]

    @cachedproperty()
    def path(self):
        """Return the importable path for this module, this is not the filepath
        of the module but the directory the module could be imported from"""
        return self.find_module_import_path()

    @cachedproperty()
    def parts(self):
        """Return the importable path for this module, this is not the filepath
        of the module but the directory the module could be imported from"""
        return self.modpath.split(".")

    @property
    def modpath(self):
        """Return the full qualified python path of the module (eg,
        foo.bar.che)
        """
        return self.get_module().__name__

    @property
    def modroot(self):
        """Return the aboslute root module"""
        if self.module_package:
            modroot = self.module_package.split(".", maxsplit=1)[0]

        else:
            modroot = self.name.split(".", maxsplit=1)[0]

        return modroot

    @classmethod
    def find_module_names(cls, path, prefix="", ignore_private=True):
        """recursive method that will find all the modules of the given path

        :param path: str, the path to scan for modules/submodules
        :param prefix: str, if you want found modules to be prefixed with a
            certain module path
        :param ignore_private: bool, if True then ignore modules considered
            private
        :returns: set, a set of submodule names under path prefixed with prefix
        """
        module_names = set()

        # https://docs.python.org/2/library/pkgutil.html#pkgutil.iter_modules
        for module_info in pkgutil.iter_modules([path]):
            # we want to ignore any "private" modules
            if module_info[1].startswith('_') and ignore_private:
                if not module_info[1] == "__main__":
                    continue

            if prefix:
                module_prefix = ".".join([prefix, module_info[1]])

            else:
                module_prefix = module_info[1]

            if module_info[2]:
                # module is a package
                module_names.add(module_prefix)
                submodule_names = cls.find_module_names(
                    os.path.join(path, module_info[1]),
                    module_prefix
                )
                module_names.update(submodule_names)

            else:
                module_names.add(module_prefix)

        return module_names

    @classmethod
    def find_module_package(cls, module_name):
        """This will attempt to find the package if module_name is relative

        :param module_name: str, if relative (starts with dot) then try and
            find the calling package which you can pass into
            importlib.import_module()
        :returns: str, the calling package modpath
        """
        module_package = None
        if module_name.startswith("."):
            frames = inspect.stack()
            for frame in frames:
                frame_cls = frame[0].f_locals.get("cls", None)
                frame_self = frame[0].f_locals.get("self", None)
                is_first_outside_call = (
                    (frame_cls and frame_cls is not cls)
                    or (frame_self and type(frame_self) is not cls)
                )
                if is_first_outside_call:
                    module_package = frame[0].f_globals["__name__"]
                    break

        return module_package

    @classmethod
    def import_module(cls, module_name, module_package=None, path=None):
        """passthrough for importlib importing functionality

        :param module_name: str, the module name/path (eg foo.bar)
        :param module_package: str, if module_name is relative (eg ..foo) then
            this will be used to resolve the relative path
        :param path: str, if passed in then this will be added to the
            importable paths and removed after the module is imported
        """
        if path:
            sys.path.append(path)

        try:
            m = importlib.import_module(module_name, module_package)

        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                f"Could not import {module_name} at package {module_package}"
            ) from e

        if path:
            sys.path.pop(-1)

        return m

    def __init__(self, target, module_package=None, *, path=None):
        """
        :param target: str|ModuleType, the module path of the module to
            introspect or the actual module
        :param module_package: the prefix that will be used to load .target
            if the target's name is relative (eg `target="..foo.bar"`)
        :param path: str, the importable path for target
        """
        if isinstance(target, types.ModuleType):
            self.target = target
            self.name = target.__name__
            self.module_package = module_package

        else:
            self.target = None
            self.name = target
            self.module_package = module_package or self.find_module_package(
                target
            )

        if path:
            self.path = path

    def __iter__(self):
        """This will iterate through this module and all its submodules
        :returns: a generator that yields ReflectModule instances
        """
        for module_name in self.get_module_names():
            yield self.create_reflect_module(module_name)

    def is_private(self):
        """return True if this module is considered private"""
        parts = []
        if self.module_package:
            parts.extend(self.module_package.split("."))
        parts.extend(self.name.split("."))
        for part in parts:
            if part.startswith("_"):
                if not part.startswith("__") and not part.endswith("__"):
                    return True

    def is_package(self):
        if self.target:
            # if path attr exists then this is a package
            return hasattr(self.target, "__path__")

        else:
            p = pkgutil.get_loader(self.name)
            return p.path.endswith("__init__.py")

    def reflect_module(self, *parts):
        """Returns a reflect module instance for a submodule"""
        return self.create_reflect_module(self.get_submodule(*parts))

    def get_basemodule(self):
        """Returns the root-most module of this module's path (eg, if this
        module was foo.bar.che then this would return foo module)"""
        return self.import_module(self.modroot)

    def get_rootmodule(self):
        return self.get_basemodule()

    def reflect_rootmodule(self):
        return self.reflect_basemodule()

    def reflect_basemodule(self):
        return self.create_reflect_module(self.modroot)

    def reflect_parent(self, back=1):
        """Return the reflection instance for the parent module"""
        return self.create_reflect_module(
            self.get_parentpath(back=back)
        )

    def get_parentpath(self, back=1):
        """get a parent module path, depending on the value of back this will
        return the path, by default it is the immediate parent

        :param back: int, how many parts to move back (eg foo.bar.che with back
            as 1 will return foo.bar and foo with back equal to 2)
        :returns: str, the parent module path
        """
        parts = self.parts
        return ".".join(parts[:-abs(back)])

    def get_submodule(self, *parts):
        """return the actual python module

        :param *parts: modpath parts relative to this module
        :returns: ModuleType, the module or the submodule
        """
        if not parts:
            raise ValueError("No submodule parts")

        return self.get_module(*parts)

    def reflect_submodules(self, depth=-1):
        module = self.get_module()
        if not depth:
            depth = -1

        if self.is_package():
            submodule_names = self.find_module_names(
                module.__path__[0],
                self.name
            )

            for subname in submodule_names:
                if depth <= 0 or count(subname) < depth:
                    yield self.create_reflect_module(subname)

    def get_submodules(self, depth=-1):
        for rm in self.reflect_submodules(depth=depth):
            yield rm.get_module()

    def get_target(self):
        return self.get_module()

    def get_module(self, *parts):
        if self.target and not parts:
            ret = self.target

        else:
            module_name = self.name
            if parts:
                module_name += "." + ".".join(parts)

            # self.path uses find_module_import_path which calls this method
            # so we should only use path if we already have it cached
            path = vars(self).get("path", None)
            #path = getattr(self, "_path", None)

            if self.module_package:
                mname = module_name
                if not mname.startswith("."):
                    # We compensate for the package existing but the name not
                    # being relative, if we don't do this then the module will
                    # just fail to load
                    mname = "." + mname

                ret = self.import_module(
                    mname,
                    self.module_package,
                    path=path
                )

            else:
                ret = self.import_module(
                    module_name,
                    path=path
                )

        if not parts and not self.target:
            self.target = ret

        return ret

    def get_modules(self, depth=-1):
        """Similar to .get_submodules() but yields this module first before
        yielding all the submodules

        :returns generator[ModuleType], starting with self's module and then
            yielding all the submodules found in self
        """
        yield self.get_module()

        for sm in self.get_submodules():
            yield sm

    def get_module_names(self):
        """return all the module names that this module encompasses
        :returns: set, a set of string module names
        """
        module = self.get_module()
        module_name = module.__name__
        module_names = set([module_name])

        if self.is_package():
            module_names.update(self.find_module_names(
                module.__path__[0],
                module_name
            ))

        return module_names

    @functools.cache
    def get_info(self):
        """Get information about the module"""
        ret = {}
        module = self.get_module()
        classes = inspect.getmembers(module, inspect.isclass)
        for class_name, class_type in classes:
            ret[class_name] = self.create_reflect_class(class_type)
        return ret

    def reflect_classes(self, ignore_private=True):
        """yields ReflectClass instances that are found in only this module
        (not submodules)

        :param ignore_private: bool, if True then ignore classes considered
            private
        :returns: a generator of ReflectClass instances
        """
        for class_name, rc in self.get_info().items(): 
            if isinstance(rc, ReflectClass):
                if ignore_private and rc.is_private():
                    continue
                yield rc

    def get_classes(self, ignore_private=True, ignore_imported=False):
        """yields classes (type instances) that are found in only this module
        (not submodules)

        :param ignore_private: bool, if True then ignore classes considered
            private
        :param ignore_imported: bool, True if you only want classes that were
            defined in this module (eg, the class's `class <NAME>` is actually
            in this module)
        :returns: a generator of type instances
        """
        module = self.get_module()
        for rc in self.reflect_classes(ignore_private=ignore_private):
            if ignore_imported:
                if module.__name__ == rc.target.__module__:
                    yield rc.target

            else:
                yield rc.target

    def reflect_class(self, name, *default_val):
        """Get a ReflectClass instance of name"""
        try:
            return self.get_info()[name]

        except KeyError as e:
            if default_val:
                return default_val[0]

            else:
                raise AttributeError(
                    f"{self.get_module().__name__}.{name} does not exist"
                ) from e

    def get_members(self, *args, **kwargs):
        module = self.get_module()
        for name, value in inspect.getmembers(module, *args, **kwargs):
            yield name, value

    def get(self, name, *default_val):
        """Get a value of the module

        :param name: str, the attribute name you want
        :param *default_val: mixed, return this if name doesn't exist
        :returns: mixed, the raw python attribute value
        """
        try:
            return getattr(self.get_module(), name, *default_val)

        except (ImportError, SyntaxError) as e:
            if default_val:
                return default_val[0]

            else:
                raise AttributeError(name) from e

    def find_module_import_path(self):
        """find and return the importable path for the module"""
        module_name = self.get_module().__name__
        master_modname = module_name.split(".", 1)[0]
        master_module = sys.modules[master_modname]
        path = os.path.dirname(
            os.path.dirname(inspect.getsourcefile(master_module))
        )
        return path

    def get_data(self, resource):
        """This is just a wrapper around pkgutil.get_data, so you will need to
        use the full path from this module

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

        :param resource: the full relative path from self.modpath of the file
            you want
        :returns: bytes, the file contents
        """
        return pkgutil.get_data(self.modpath, resource)

    def find_data(self, resource):
        """Similar to .get_data() but you don't need to specify the full path
        because this will traverse the whole module directory so it will only
        work with traditional packages

        :param resource: the relative path of the file hopefully somewhere in
            the package
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
        if self.is_package():
            basedir = Dirpath(self.path, self.modpath.split("."))
            # once we find a matching directory we stop traversing it, so data
            # directories can have folders and stuff in them
            it = basedir.dirs()
            for dp in it:
                if not dp.has_file("__init__.py") or dp.endswith(basename):
                    it.finish(dp)
                    dpb = dp.basename
                    if not dpb.startswith("__") and not dpb.endswith("__"):
                        yield dp

    def get_docblock(self):
        if not self.target:
            # make sure self.target is set
            self.get_module()

        docblock = super().get_docblock()

        if docblock.startswith("!"):
            # we need to remove the shebang
            # example: #!/usr/bin/env ruby
            # https://en.wikipedia.org/wiki/Shebang_(Unix)
            docblock = re.sub(
                r"^!\S+.*?$",
                "",
                docblock,
                flags=re.MULTILINE
            ).lstrip()

        if docblock.startswith("-*-"):
            # we need to remove the emacs notation variables
            # example: # -*- mode: ruby -*-
            # http://www.python.org/dev/peps/pep-0263/
            # https://stackoverflow.com/questions/14083111/
            # https://stackoverflow.com/questions/4872007/
            docblock = re.sub(
                r"^\-\*\-.*?\-\*\-$",
                "",
                docblock,
                flags=re.MULTILINE
            ).lstrip()

        # remove generic editor configuration
        # example: # vi: set ft=ruby :
        docblock = re.sub(
            r"^[^:]+:.*?:$",
            "",
            docblock,
            flags=re.MULTILINE
        ).lstrip()

        return docblock

    def getsource(self):
        return inspect.getsource(self.get_module())

    def get_ast(self):
        return ast.parse(self.getsource())


class ReflectDocblock(object):
    """Information about a ReST docblock

    https://www.sphinx-doc.org/en/master/usage/domains/python.html
    """
    def __init__(self, target, **kwargs):
        self.target = target
        self.info = self.parse()

    def parse(self):
        """Internal method. Called from the constructor to give structure to
        the docblock

        :returns: dict[str, list[str]|dict[str, str|list[str]]]
        """
        info = {}
        delims = [":", ".."]

        s = Scanner(self.target)
        while s:
            desc = s.read_to(delims=delims)
            if desc:
                info.setdefault("description", [])
                info["description"].append(desc)

            if not desc or desc[-1].isspace():
                chars = s.read_thru(delims=delims)
                if chars == ":":
                    tagname, tagval, tagbody = self.parse_tag(s)
                    info.setdefault(tagname, [])
                    info[tagname].append({
                        "value": tagval,
                        "body": tagbody,
                    })

                elif chars == "..":
                    dirname, dirbody = self.parse_directive(s)
                    info.setdefault(dirname, [])
                    info[dirname].append({
                        "body": dirbody,
                    })

        return info

    def parse_tag(self, s):
        """Internal method. Called from `.parse()`. This handles parsing
        `:tag:` syntax.

        https://www.sphinx-doc.org/en/master/usage/domains/python.html#info-field-lists

        :param s: Scanner
        :returns: tuple[str, str, list[str]], tagname, value (the value is
            is anything after the tagname but before the closing colon), and
            the body lines
        """
        name = s.read_to(char=":", hspace=True)
        s.read_thru(hspace=True)
        value = s.read_to(char=":")
        s.read_thru(char=":")
        body = self.parse_body(s)
        return name, value, body

    def parse_directive(self, s):
        """Internal method. Called from `.parse()`. This handles parsing
        `.. directive::` syntax

        :param s: Scanner
        :returns: tuple[str, str, list[str]], directive name, and the
            body lines
        """
        s.read_thru(hspace=True)
        name = s.read_to(delim="::")
        s.read_thru(delim="::")
        body = self.parse_body(s)
        return name, body

    def parse_body(self, s):
        """Internal method. Called from the sub parsing methods.

        :param s: Scanner
        :returns: list[str], each line in the body after the tag or directive
        """
        body = []

        while True:
            body.append(s.read_to(char="\n", include_delim=True))
            indent, blanklines = self.parse_blanklines(s)
            body.extend(blanklines)
            if not indent:
                break

        return body

    def parse_blanklines(self, s):
        """Internal method. Called from `.parse_body()`. Get all the blank
        lines between 2 populated lines in a body

        :param s: Scanner
        :returns: tuple[str, list[str]], the indent of the current line in `s`
            and the blank lines that were found in a list
        """
        indent = ""
        blanklines = []

        while True:
            indent = s.read_thru(hspace=True)
            newline = s.read_thru(delims=["\n", "\r"])
            if newline:
                blanklines.append(indent + newline)

            else:
                break

        return indent, blanklines

    def get_bodies(self, name):
        """Get the bodies of `name`

        :param name: str, the directive or tag name
        :returns: Generator[str], the bodies of name
        """
        if name in self.info:
            if isinstance(self.info[name][0], dict):
                for row in self.info[name]:
                    if "body" in row:
                        yield self._get_str_body(row["body"])

            else:
                yield self._get_str_body(self.info[name])

    def get_signature_info(self):
        """Get call signature information according to the docblock

        :returns: dict[str, str|set|dict[str, str]]
            - positional_only_names: set[str], the set of names that can
                only be passed in as positionals
            - keyword_only_names: set[str], the set of names taht can
                only be passed in as keywords
            - descriptions: dict[str, str], the descriptions for each param
        """
        siginfo = {
            "positional_only_names": set(),
            "keyword_only_names": set(),
            "descriptions": {},
        }

        for name, ptype, pdesc in self._get_params():
            if pdesc:
                siginfo["descriptions"][name] = pdesc

            if ptype == "positional":
                siginfo["positional_only_names"].add(name)

            elif ptype == "keyword":
                siginfo["keyword_only_names"].add(name)

        return siginfo

    def get_docblock(self):
        return self.get_target()

    def get_description(self):
        """Get the docblock description"""
        return self._get_str_body(self.info.get("description", []))

    def get_param_descriptions(self):
        """Get all the callable's parameter descriptions

        :returns: dict[str, str], the key is the parameter name and the
            value is the parameter description
        """
        ret = {}
        for name, ptype, desc in self._get_params():
            ret[name] = desc

        return ret

    def _get_params(self):
        """Internal method to get the parameters

        This normalize all the different keywords a parameter can be defined
        with to just:

            * param - can either be positional or keyword
            * positional - can only be passed in by value
            * keyword - can only be passed in as key=value

        :returns: tuple[str, str, str], index 0 is the param name, index 1
            is the param type (param, positional, keyword), and index 2 is
            the param description
        """
        tagnames = [
            "param",
            "parameter",
            "arg",
            "argument",
            "key",
            "keyword",
        ]

        for tagname in tagnames:
            if tagname in self.info:
                for row in self.info[tagname]:
                    name = row["value"]
                    param_type = "param"

                    if tagname in set(["arg", "argument"]):
                        param_type = "positional"

                    elif tagname in set(["key", "keyword"]):
                        param_type = "keyword"

                    desc = self._get_str_body(row["body"])
                    yield name, param_type, desc

    def _get_str_body(self, lines):
        return "".join(lines).strip()

