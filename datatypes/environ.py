# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os

from .compat import *


class Environ(object):
    """Create an Environ for the given modname module

    you would usually create this like this:

        environ = Environ(__name__)

    This would take __name__ and normalize it, so something like `foo.bar` would
    become `FOO_`, if you want to set the namespace explicitely, you could do:

        environ = Environ("FOO_")
    """
    def __init__(self, modname=""):
        self.namespace = ""
        if modname:
            namespace = modname.split(".")[0].upper()
            if not namespace.endswith("_"):
                namespace += "_"
            self.namespace = namespace

    def set(self, key, value):
        k = self.key(key)
        os.environ[k] = value

    def get(self, key, default=None):
        """get a value for key from the environment

        :param key: string, this will be normalized using the key() method
        :returns: mixed, the value in the environment of key, or default if key
            is not in the environment
        """
        if self.namespace and not key.startswith(self.namespace):
            key = self.namespace + key

        r = os.environ.get(key, default)
        return r

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

    def all(self, key):
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

    def paths(self, key):
        """Similar to .all() but splits each value using the path separator"""
        sep = os.pathsep
        for paths in self.all(key):
            for p in paths.split(sep):
                yield p


environ = Environ(modname=__name__)

ENCODING = environ.get("ENCODING", "UTF-8")
"""For things that need encoding, this will be the default encoding if nothing else
is passed in"""

ENCODING_ERRORS = environ.get("ENCODING_ERRORS", "replace")
"""For things that need encoding, this will handle any errors"""

CACHE_DIR = environ.get("CACHE_DIR", "")
"""the default caching directory for things that need a cache folder"""

