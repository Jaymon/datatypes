# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import tempfile
import sys

from .compat import *


class Environ(object):
    """Create an Environ for the given modname module

    you would usually create this like this:

        environ = Environ(__name__)

    This would take __name__ and normalize it, so something like `foo.bar` would
    become `FOO_`, if you want to set the namespace explicitely, you could do:

        environ = Environ("FOO_")

    And if you want a separate environment prefix than your module:

        # environ.py
        environ = Environ("FOO_", __name__)
        # merge FOO_* environment variables into __name__ module and strip FOO_
        # from those variables (ie FOO_BAR would become BAR)
        environ.update() 
    """
    @classmethod
    def find_namespace(cls, modname):
        namespace = modname.split(".")[0].upper()
        if not namespace.endswith("_"):
            namespace += "_"
        return namespace

    def __init__(self, modname="", envmodname=""):
        """
        :param modname: str, usually __name__ from the calling module but can also
            be "PREFIX_" or something like that
        :param envmodname: str, if modname is "PREFIX_" then this would be __name__
            or the module path
        """
        self.namespace = self.find_namespace(modname) if modname else ""
        self.envmodname = envmodname if envmodname else modname

    def update(self, environ=None, envmodname="", clobber=False):
        """merge the variables of environ into the module found using envmodname

        This is designed to be called from a library's environ.py file

        :Example:
            # <LIBRARY>/environ.py
            from datatypes.environ import Environ
            environ = Environ(__name__)
            environ.merge()

        :param environ: dict, if None os.environ will be used instead
        :param envmodname: str, this is the modpath used to pull the module from
            sys.modules
        :param clobber: bool, True if you want to clobber previously set values,
            False if you skip values that have already been set
        :returns: module, the module found via envmodname
        """
        if not environ:
            environ = os.environ

        if not envmodname:
            envmodname = self.envmodname

        envmod = sys.modules[envmodname]

        for k in self.keys():
            ek = self.ekey(k)
            if clobber or not hasattr(envmod, ek):
                setattr(envmod, ek, self.get(k))

        return envmod

    def set(self, key, value):
        os.environ[self.key(key)] = value

    def nset(self, key, values):
        """Given a list of values, this will set key_* where * is 1 -> len(values)

        :param key: string, the key that will be added to the environment as key_*
        :param values: list, a list of values
        """
        self.ndelete(key)

        for i, v in enumerate(values, 1):
            k = "{}_{}".format(key, i)
            self.set(k, v)

    def delete(self, key):
        """remove key from the environment"""
        os.environ.pop(self.key(key), None)

    def ndelete(self, key):
        """remove all key_* from the environment"""
        for k in self.nkeys(key):
            os.environ.pop(k)

    def get(self, key, default=None):
        """get a value for key from the environment

        :param key: string, this will be normalized using the key() method
        :returns: mixed, the value in the environment of key, or default if key
            is not in the environment
        """
        return os.environ.get(self.key(key), default)

    def __getitem__(self, key):
        return os.environ[self.key(key)]

    def __getattr__(self, key):
        return self.__getitem__(key)

    def nget(self, key):
        """this will look for key, and kkey_N (where
        N is 1 to infinity) in the environment

        The num checks (eg *_1, *_2) go in order, so you can't do *_1, *_3, because it
        will fail on missing *_2 and move on, so make sure your nums are in order 
        (eg, 1, 2, 3, ...)

        :param key: string, the name of the environment variables
        :returns: generator, the found values for key and key_* variants
        """
        for nkey in self.nkeys(key):
            yield os.environ[nkey]

    def keys(self):
        """yields all the keys of the given namespace currently in the environment"""
        for k in os.environ.keys():
            if k.startswith(self.namespace):
                yield k

    def key(self, key):
        """normalizes key to have the namespace

        :Example:
            environ = Environ("FOO_")
            k = environ.key("BAR")
            print(k) # FOO_BAR
        """
        if self.namespace and not key.startswith(self.namespace):
            key = self.namespace + key
        return key

    def ekey(self, key):
        """Given a full namespaced key return the key name without the namespace

        :Example:
            environ = Environ("FOO_")
            k = environ.ekey("FOO_BAR")
            print(k) # BAR
        """
        return key.replace(self.namespace, "")

    def nkey(self, key, n):
        """helper method for nkeys"""
        k = self.key(key)
        for fmt in ["{key}_{n}", "{key}{n}"]:
            nkey = fmt.format(key=k, n=n)
            if nkey in os.environ:
                return nkey

        raise KeyError("Environ {} has no {} key".format(key, n))

    def nkeys(self, key):
        """This returns the actual environment variable names from * -> *_N

        :param key: string, the name of the environment variables
        :returns: generator, the found environment names
        """
        k = self.key(key)
        if k in os.environ:
            yield k

        # now try importing _1 -> _N prefixes
        n = 0
        while True:
            try:
                yield self.nkey(key, n)

            except KeyError:
                # 0 is a special case, so if it fails we keep going
                if n:
                    # we are done because we missed an n value
                    break

            finally:
                n += 1

    def paths(self, key):
        """Similar to .all() but splits each value using the path separator"""
        sep = os.pathsep
        for paths in self.nget(key):
            for p in paths.split(sep):
                yield p

    def has(self, key):
        """Return True if key is in the environment

        :param k: str
        :returns: bool
        """
        return self.key(key) in os.environ

    def __contains__(self, key):
        return self.has(key)


environ = Environ("DATATYPES_", __name__)

ENCODING = environ.get("ENCODING", "UTF-8")
"""For things that need encoding, this will be the default encoding if nothing else
is passed in"""

ENCODING_ERRORS = environ.get("ENCODING_ERRORS", "replace")
"""For things that need encoding, this will handle any errors"""

# 2021-1-15 - we place our cache by default into another directory because I have problems
# running some commands like touch on the base temp directory on MacOS on
# Python3, no idea why but I couldn't get around it
CACHE_DIR = environ.get("CACHE_DIR", os.path.join(tempfile.gettempdir(), environ.namespace.lower().rstrip("_")))
"""the default caching directory for things that need a cache folder"""


USER_AGENT = environ.get("USER_AGENT", "")


# Load all other DATATYPES_* environment variables into this module
environ.update()

