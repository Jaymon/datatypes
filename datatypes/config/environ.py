# -*- coding: utf-8 -*-
import os
import tempfile

from ..compat import *


class Environ(Mapping):
    """Create an Environ namespace instance

    you would usually create this like this:

        environ = Environ("PREFIX_")

    Then you can access any environment variables with that prefix from the
    `environ` instance.

    :Example:
        # in your environment
        export PREFIX_FOOBAR=1
        export PREFIX_CHE="this is the che value"

        # in your python code
        environ = Environ("PREFIX_")

        print(environ.FOOBAR) # "1"
        print(environ.CHE) # this is the che value

        # by default, all environ values are string, but you can set defaults
        # and set the type
        environ.setdefault("BAZ", 1000, type=int)

        print(environ.BAZ, type(environ.BAZ)) # 1000 <class 'int'>
    """
    @classmethod
    def find_namespace(cls, prefix):
        namespace = ""
        if prefix:
            namespace = prefix.split(".", maxsplit=1)[0].upper()
            if not namespace.endswith("_"):
                namespace += "_"
        return namespace

    def __init__(self, namespace="", environ=None):
        """
        :param namespace: str, usually __name__ from the calling module but can
            also be "PREFIX_" or something like that
        :param environ: str, the environment you want this instance to wrap, it
            defualts to os.environ
        """
        self.__dict__["namespace"] = self.find_namespace(namespace)
        self.__dict__["defaults"] = {}
        self.__dict__["environ"] = environ or os.environ

    def setdefault(self, key, value, type=None):
        self.defaults[self.ekey(key)] = {
            "value": value,
            "type": type,
        }

    def set(self, key, value):
        self.__setattr__(key, value)
        #os.environ[self.key(key)] = value

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        self.environ[self.key(key)] = value

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
        self.__delattr__(key)
        #os.environ.pop(self.key(key), None)

    def __delitem__(self, key):
        #os.environ.pop(self.key(key), None)
        self.environ.pop(self.key(key), None)

    def ndelete(self, key):
        """remove all key_* from the environment"""
        for k in self.nkeys(key):
            #os.environ.pop(k)
            self.environ.pop(k, None)

    def get(self, key, default=None):
        """get a value for key from the environment

        :param key: string, this will be normalized using the key() method
        :returns: mixed, the value in the environment of key, or default if key
            is not in the environment
        """
        try:
            return self[key]

        except KeyError:
            return default
            #return os.environ.get(self.key(key), default)

    def pop(self, key, *defaults):
        try:
            return self.__getitem__(key)

        except KeyError:
            if defaults:
                return defaults[0]

            else:
                raise

    def __getitem__(self, key):
        ek = self.ekey(key)
        k = self.key(key)
        try:
            #return os.environ[k]
            v = self.environ[k]

        except KeyError:
            v = self.defaults[ek]["value"]

        if ek in self.defaults:
            if self.defaults[ek]["type"]:
                v = self.defaults[ek]["type"](v)

        return v

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)

        except KeyError as e:
            raise AttributeError(key) from e

    def nget(self, key):
        """this will look for key, and key_N (where
        N is 1 to infinity) in the environment

        The number checks (eg *_1, *_2) go in order, so you can't do *_1, *_3,
        because it will fail on missing *_2 and move on, so make sure your number
        suffixes are in order (eg, 1, 2, 3, ...)

        :param key: string, the name of the environment variables
        :returns: generator, the found values for key and key_* variants
        """
        for nkey in self.nkeys(key):
            #yield os.environ[nkey]
            yield self.environ[nkey]

    def keys(self):
        """yields all the keys of the given namespace currently in the environment"""
        for k, _ in self.items():
            yield k

    def values(self):
        """yields all the keys of the given namespace currently in the environment"""
        for _, v in self.items():
            yield v

    def items(self):
        #for k, v in os.environ.items():
        seen = set()
        for k, v in self.environ.items():
            if k.startswith(self.namespace):
                ek = self.ekey(k)
                seen.add(ek)
                yield ek, v

        for ek, d in self.defaults.items():
            if ek not in seen:
                yield ek, d["value"]

    def __iter__(self):
        return self.keys()

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
        """internal method. Helper method for nkeys"""
        k = self.key(key)
        for fmt in ["{key}_{n}", "{key}{n}"]:
            nkey = fmt.format(key=k, n=n)
            if nkey in self.environ:
            #if nkey in os.environ:
                return nkey

        raise KeyError("Environ {} has no {} key".format(key, n))

    def nkeys(self, key):
        """This returns the actual environment variable names from * -> *_N

        :param key: str, the name of the environment variables
        :returns: generator[str], the found environment names
        """
        k = self.key(key)
        #if k in os.environ:
        if k in self.environ:
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

    def paths(self, key, sep=None):
        """splits the value at key by the path separator and yields each
        individual path part

        splits each value using the path separator

        :param key: str, the key
        :param sep: str, the value to split on, defaults to the OS's underlying
            path separator
        :returns: generator, each part of the value found at key
        """
        for paths in self.nget(key):
            for p in self.split_value(paths, sep=sep):
                yield p

    def split_value(self, value, sep=None):
        """Split value using sep, sep defaults to the os path separator

        :param value: str, the value to split
        :param sep: str, the value to split on, defaults to the OS's underlying
            path separator
        :returns: list[str]
        """
        sep = sep or os.pathsep
        return value.split(sep)

    def has(self, key):
        """Return True if key is in the environment

        :param k: str
        :returns: bool
        """
        #return self.key(key) in os.environ
        return self.key(key) in self.environ

    def __contains__(self, key):
        return self.has(key)

    def __len__(self):
        return len(list(self.keys()))


###############################################################################
# Actual environment configuration that is used throughout the package
###############################################################################
environ = Environ("DATATYPES_")

environ.setdefault("ENCODING", "UTF-8")
"""For things that need encoding, this will be the default encoding if nothing
else is passed in"""


environ.setdefault("ENCODING_ERRORS", "replace")
"""For things that need encoding, this will handle any errors"""


# 2021-1-15 - we place our cache by default into another directory because I
# have problems running some commands like touch on the base temp directory on
# MacOS on Python3, no idea why but I couldn't get around it
environ.setdefault(
    "CACHE_DIR",
    os.path.join(tempfile.gettempdir(), environ.namespace.lower().rstrip("_"))
)
"""the default caching directory for things that need a cache folder"""


environ.setdefault("USER_AGENT", "")

