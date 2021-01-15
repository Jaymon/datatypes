# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import copy
from io import IOBase

from .compat import *


class Deepcopy(object):
    """deep copy an object trying to anticipate and handle any errors

    The original version of this class comes from endpoints.utils and is used in
    the http.Http.__deepcopy__() method.

    You would traditionally use this in a class by adding these two methods:

        def copy(self):
            # handy wrapper around the deepcopy stuff
            return copy.deepcopy(self)

        def __deepcopy__(self, memodict=None):
            dc = Deepcopy()
            return dc.copy(self, memodict)

    This follows the rules of pickle for creating a new instance, so you can use
    methods like __getnewargs_ex__ to get the arguments for creating a new instance
    and __getstate__() and __setstate__() to handle migrating data from the old instance
    to the new instance

    https://docs.python.org/3/library/copy.html
    """
    def __init__(self, **kwargs):
        """
        :param **kwargs:
            ignore_keys: set, if you don't want to include certain keys in the copy
                then you can pass them in this named argument
            ignore_private: boolean, if you don't want to copy any properties that
                begin with an underscore (eg, _foo) then set this to True
            memodict: the memodict used in deepcopy
        """
        self.ignore_keys = set(kwargs.pop("ignore_keys", []))
        self.memodict = kwargs.pop("memodict", kwargs.pop("memo", {}))
        self.ignore_private = kwargs.pop("ignore_private", False)

    def copy(self, val, memodict=None, **kwargs):
        if memodict:
            memo = dict(self.memodict)
            memo.update(memodict or {})
        else:
            memo = self.memodict

        ignore_keys = kwargs.get("ignore_keys", self.ignore_keys)
        ignore_private = kwargs.get("ignore_keys", self.ignore_private)

        if hasattr(val, "__dict__"):
            instance = self.create_instance(val)
            d = self.get_state(val)

            instance_d = {}
            for k in d.keys():
                if k in ignore_keys:
                    continue

                if ignore_private and k.startswith("_"):
                    continue

                if k in memo:
                    instance_d[k] = memo[k]

                else:
                    instance_d[k] = self._copy(d[k], memo)

            self.set_state(instance, instance_d)

        else:
            instance = self._copy(val, memo)

        return instance

    def _copy(cls, val, memodict):
        ret = val
        # try a deepcopy
        try:
            ret = copy.deepcopy(val, memodict)

        except (AttributeError, TypeError) as e:
            # if the deepcopy failed a shallow copy is better than nothing
            try:
                ret = copy.copy(val)

            except (TypeError, RuntimeError):
                # we can do nothing so just pass it straight through
                # RuntimeError is because py3 can throw a RecursionError, py2
                # will throw a TypeError
                pass

        return ret

    def create_instance(self, val):
        """If the passed in .copy val is a class, this will create a new instance
        of val using the pickle rules:

            py3: https://docs.python.org/3/library/pickle.html#module-pickle
            py2: https://docs.python.org/2/library/pickle.html#module-pickle

        This will try for py3 methods first and then fall back to py2 rules
        """
        instance_class = self.get_instance_type(val)
        args, kwargs = self.get_instance_args(val)
        return instance_class(*args, **kwargs)

    def get_instance_type(self, val):
        """get the class/type of val"""
        return type(val)

    def get_instance_args(self, val):
        """get the arguments that val would need to be instantiated again"""
        args = ()
        kwargs = {}

        if hasattr(val, "__getnewargs_ex__"):
            args, kwargs = val.__getnewargs_ex__()

        elif hasattr(val, "__getnewargs__"):
            args = val.__getnewargs__()

        elif hasattr(val, "__getinitargs__"):
            args = val.__getinitargs__()

        return args, kwargs

    def set_state(self, val, state):
        """Populate val with state (the contents of a previous version of val's
        __dict__ property)"""
        if hasattr(val, "__setstate__"):
            val.__setstate__(state)

        else:
            for k, v in state.items():
                setattr(val, k, v)

    def get_state(self, val):
        """Get the state (the contents of val.__dict__) of val as a dict"""
        if hasattr(val, "__getstate__"):
            d = val.__getstate__()

        else:
            d = val.__dict__

        return d

