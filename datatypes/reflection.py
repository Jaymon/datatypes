# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import inspect
import sys
import types

from .compat import *


class OrderedSubclasses(list):
    """A list that maintains subclass order where subclasses always come before
    their parents in the list

    Basically, it makes sure all subclasses get placed before the parent class,
    so if you want your ChildClass to be before ParentClass, you would just have
    ChildClass extend ParentClass

    You'd think this would be a niche thing and not worth being in a common lib
    of things, but I've actually had to do this exact thing multiple times, so
    I'm finally moving this from Pout and Bang into here so I can standardize it
    """
    def __init__(self, cutoff_classes=None):
        """
        :param cutoff_classes: [type, ...], you should ignore anything before these
            classes when working out order
        """
        super().__init__()

        self.indexes = {}

        # make sure we have a tuple of type objects
        if cutoff_classes:
            if not isinstance(cutoff_classes, (Sequence, tuple)):
                cutoff_classes = (cutoff_classes,)
            else:
                cutoff_classes = tuple(cutoff_classes)
        else:
            cutoff_classes = (object,)

        self.cutoff_classes = cutoff_classes

    def insert(self, klass):
        """Insert class into the ordered list

        :param klass: the class to add to the ordered list, this klass will come
            before all its parents in the list (this class and its parents will
            be added to the list up to .cutoff_classes)
        """
        index = len(self)
        cutoff_classes = self.cutoff_classes

        for subclass in reversed(inspect.getmro(klass)):
            if issubclass(subclass, cutoff_classes):
                index_name = f"{subclass.__module__}.{subclass.__name__}"
                if index_name in self.indexes:
                    index = min(index, self.indexes[index_name])

                else:
                    self.indexes[index_name] = len(self)
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

