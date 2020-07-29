# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import copy
from io import IOBase

from .compat import *


class Deepcopy(object):
    """deep copy an object trying to anticipate and handle any errors

    I'm honestly not quite sure why this class was created, it comes from endpoints.utils
    and is used in the http.Http.__deepcopy__() method. You would traditionally use this
    in a class by adding these two methods:

        def copy(self):
            # handy wrapper around the deepcopy stuff
            return copy.deepcopy(self)

        def __deepcopy__(self, memodict=None):
            # create a shell instance that can be populated
            instance = type(self)()
            return Deepcopy.copy(self, memodict, instance)
    """
    def __init__(self, **kwargs):
        self.ignore_keys = set(kwargs.pop("ignore_keys", []))
        self.memodict = kwargs.pop("memodict", kwargs.pop("memo", {}))
        self.ignore_private = kwargs.pop("ignore_private", False)

    def copy(self, val, memodict=None, **kwargs):
        memodict = dict(self.memodict)
        memodict.update(memodict or {})
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

                instance_d[k] = self._copy(d[k], memodict)

            self.set_state(instance, instance_d)

        else:
            instance = self._copy(val, memodict)

        return instance

    def _copy(cls, val, memodict):
        ret = val
        # try a deepcopy
        try:
            ret = copy.deepcopy(val, memodict)

        except (AttributeError, TypeError):
            # if the deepcopy failed a shallow copy is better than nothing
            try:
                ret = copy.copy(val)

            except TypeError:
                # we can do nothing so just pass it straight through
                pass

        return ret

    def create_instance(self, val):
        instance_class = self.get_instance_type(val)
        args, kwargs = self.get_instance_args(val)
        return instance_class(*args, **kwargs)

    def get_instance_type(self, val):
        return type(val)

    def get_instance_args(self, val):
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
        if hasattr(val, "__setstate__"):
            val.__setstate__(state)

        else:
            for k, v in state.items():
                setattr(val, k, v)

    def get_state(self, val):
        if hasattr(val, "__getstate__"):
            d = val.__getstate__()

        else:
            d = val.__dict__

        return d


#         type_class = self.get_type(val)
#         type_args = self.get_type_args(val)
# 
# 
#     def get_type(self, val):
#         return type(val)
# 
#     def get_type_args(self, val):
#         pass




    @classmethod
    def __copy(cls, val, memodict=None, instance=None, **kwargs):
        """deepcopy the contents of val into instance (if it exists, it will attempt
        to create instance if it's not passed in)

        https://docs.python.org/3/library/copy.html

        :param memodict: dict, dictionary of objects already copied during the
            current copying pass
        :param instance: mixed, a shell of the object you are copying, this makes it
            possible for class instances that take __init__ arguments and things like
            that, since the instance is already created it won't fail on copying it
        :param **kwargs: 
            ignore_keys: set, any keys that shouldn't be copied over to the returned
                copied instance
        :returns: mixed, a fully deepcopied object
        """
        ret = val
        ignore_keys = set(kwargs.pop("ignore_keys", []))
        if not memodict:
            memodict = {}

        if isinstance(val, Mapping):
            ret = instance if instance else type(val)()
            for k, v in val.items():
                if k not in ignore_keys:
                    ret[k] = cls.copy(v, memodict)

        elif isinstance(val, IOBase):
            # file/stream objects should just be passed through
            pass

        elif hasattr(val, "__dict__"):
            if instance:
                ret = instance
                for k, v in val.__dict__.items():
                    if k in ignore_keys:
                        continue

                    if not k.startswith("_"):
                        if v is None:
                            setattr(ret, k, v)

                        else:
                            if k in memodict and v is memodict[k]:
                                continue

                            else:
                                setattr(ret, k, cls.copy(v, memodict))

            else:
                ret = cls._copy(val, memodict)

        else:
            ret = cls._copy(val, memodict)

        return ret

    @classmethod
    def ___copy(cls, val, memodict):
        ret = val
        try:
            ret = copy.deepcopy(val, memodict)

        except (AttributeError, TypeError):
            try:
                ret = copy.copy(val)

            except TypeError:
                pass

        return ret

