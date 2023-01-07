# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import inspect
import sys

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

