# -*- coding: utf-8 -*-
from collections import ChainMap

from ..collections.mapping import Namespace
from .environ import Environ
from .parser import Config


class Settings(Namespace):
    """A settings object that can source values locally, from the environment,
    or from a config file.

    The order of precedence for values is:

        1. Locally
        2. Environment
        3. Configuration file

    :Example:
        environ = Environ("<PREFIX>")
        config = Config("<CONFIG-FILE-PATH>")
        local = {
            "foo": 1,
            "bar: 2,
        }
        s = Settings(local, environ, config)
        s.foo # 1
        s["foo"] # 1

    This extends Namespace so both attribute (.foo) and item (["foo"]) access
    are supported
    """
    def __init__(self, data=None, environ=None, config=None, **kwargs):
        super().__init__(self.get_init_data(data, **kwargs))

        self.config = self.get_init_config(config, **kwargs)
        self.environ = self.get_init_environ(environ, **kwargs)

    def get_init_environ(self, environ, **kwargs):
        """Returns the instance that will be used for environ lookups

        :param environ: Environ
        :returns: Environ
        """
        return environ or Environ(kwargs.get("prefix", self.__module__))

    def get_init_config(self, config, **kwargs):
        """Returns the instance that will be used for config lookups

        :param config: Config|str, if a str it's assumed to be a path to a
            configuration file
        :returns: Config
        """
        if isinstance(config, str):
            config = Config(config)

        return config or {}

    def get_init_data(self, data, **kwargs):
        """Returns the data that will be passed to the parent as the local
        data

        :param data: Mapping
        :returns: Mapping
        """
        return data or {}

    def get_environ_value(self, k):
        """Given a key k, attempt to get the value from the environment

        :param k: str, the key we're looking for
        :returns: Any
        """
        k = self.normalize_environ_key(k)
        return self.normalize_environ_value(self.environ[k])

    def normalize_environ_key(self, k):
        """If you want to customize the value of environment keys, you can use
        this method"""
        return self.normalize_key(k)

    def normalize_environ_value(self, v):
        """If you want to customize environment values, you can use this
        method"""
        return self.normalize_value(v)

    def get_config_value(self, k):
        """Given a key k, attempt to get the value from the config

        :param k: str, the key we're looking for
        :returns: Any
        """
        k = self.normalize_config_key(k)
        return self.normalize_config_value(self.config[k])

    def normalize_config_key(self, k):
        """If you want to customize the value of config keys, you can use this
        method"""
        return self.normalize_key(k)

    def normalize_config_value(self, v):
        """If you want to customize config values, you can use this method"""
        return self.normalize_value(v)

    def __getitem__(self, k):
        # I'd love to use a collections.ChainMap here but because there are
        # customization methods for each type of settings they need to know
        # where the value came from
        try:
            return super().__getitem__(k)

        except KeyError:
            try:
                return self.get_environ_value(k)

            except KeyError:
                return self.get_config_value(k)


class MultiSettings(Settings):
    """Similar to Settings but makes it easier to query multiple configuration
    files or environ prefixes
    """
    def __init__(self, data, **kwargs):
        """
        :param data: dict, the local data
        :param **kwargs:
            * prefixes: list[str], the environment prefixes
            * configs: list[str], the configuration files
        """
        super().__init__(data, **kwargs)

    def get_init_environ(self, _, **kwargs):
        prefixes = []

        if environ := kwargs.get("environ", None):
            prefixes.append(environ)

        if environs := kwargs.get("environs", []):
            prefixes.extend(environs)

        if prefix := kwargs.get("prefix", ""):
            prefixes.append(prefix)

        if prefixes := kwargs.get("prefixes", []):
            prefixes.extend(prefixes)

        maps = []
        for prefix in prefixes:
            if isinstance(prefix, Environ):
                maps.append(super().get_init_environ(prefix))

            else:
                maps.append(super().get_init_environ(None, prefix=prefix))

        return ChainMap(*maps)

    def get_init_config(self, _, **kwargs):
        configs = []

        if c := kwargs.get("config", ""):
            configs.append(c)

        if cs := kwargs.get("configs", []):
            configs.extend(cs)

        maps = []
        for c in configs:
            maps.append(super().get_init_config(c))

        return ChainMap(*maps)




