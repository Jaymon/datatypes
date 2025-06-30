# -*- coding: utf-8 -*-
import inspect
import re

from ..compat import *


class ReflectObject(object):
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

