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
        4. Environ.namespace
        5. Config.path.fileroot

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
    are supported.

    Retrieve an Environ instance by requesting its prefix namespace:

        s = Settings(prefix="FOOBAR_")
        s.foobar # Environ instance

    Or request a Config instance by its fileroot:

        s = Settings(config="/some/path/foobar.ini")
        s.foobar # Config instance
    """
    environ_class = Environ

    config_class = Config

    def __init__(self, data=None, environ=None, config=None, **kwargs):
        """
        :param data: Mapping, the local data
        :param environ: Environ, environment data
        :param config: Config, configuration file data
        :param **kwargs:
            * prefix: str, this will create an Environ instance with this
                prefix (eg, prefix="FOO_" would create an Environ("FOO_"))
        """
        super().__init__(self.get_init_data(data, **kwargs))

        self.__dict__["config"] = self.get_init_config(config, **kwargs)
        self.__dict__["environ"] = self.get_init_environ(environ, **kwargs)

    def get_init_environ(self, environ, **kwargs):
        """Returns the instance that will be used for environ lookups

        :param environ: Environ
        :returns: Environ
        """
        if environ is None:
            if self.__module__ != __name__:
                environ = self.environ_class(
                    kwargs.get("prefix", self.__module__)
                )

            else:
                environ = self.environ_class(
                    kwargs.get("prefix", "")
                )

        return environ

    def get_init_config(self, config, **kwargs):
        """Returns the instance that will be used for config lookups

        :param config: Config|str, if a str it's assumed to be a path to a
            configuration file
        :returns: Config
        """
        if isinstance(config, str):
            config = self.config_class(config)

        return config or {}

    def get_init_data(self, data, **kwargs):
        """Returns the data that will be passed to the parent as the local
        data

        :param data: Mapping
        :returns: Mapping
        """
        return data or {}

    def _get_value(self, backend, k):
        """Internal method. Used to check the chainmap for an item value
        and also an attribute

        :param backend: Environ|Config
        :param k: str
        :returns: Any
        :raises: KeyError
        """
        return backend[k]

    def get_environ_value(self, k):
        """Given a key k, attempt to get the value from the environment

        :param k: str, the key we're looking for
        :returns: Any
        """
        return self._get_value(self.environ, k)


    def get_config_value(self, k):
        """Given a key k, attempt to get the value from the config

        :param k: str, the key we're looking for
        :returns: Any
        """
        return self._get_value(self.config, k)

    def get_environ(self, k):
        """Internal method called from .__getitem__ that checks to see if the
        key k is actually the Environ instance's namespace

        :param k: str, the key that wasn't found anywhere else
        :returns: Environ
        """
        if self.environ is not None:
            namespace = getattr(self.environ, "namespace", "")
            if namespace and namespace.lower().startswith(k.lower()):
                return self.environ

    def get_config(self, k):
        """Internal method called from .__getitem__ that checks to see if the
        key k is actually the config file's fileroot

        :param k: str, the key that wasn't found anywhere else
        :returns: Config
        """
        if self.config is not None:
            path = getattr(self.config, "path", "")
            if path and path.fileroot == k:
                return self.config

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
                try:
                    return self.get_config_value(k)

                except KeyError:
                    environ = self.get_environ(k)
                    if environ is not None:
                        return environ

                    else:
                        config = self.get_config(k)
                        if config is not None:
                            return config

            raise


class MultiSettings(Settings):
    """Similar to Settings but makes it easier to query multiple configuration
    files or environ prefixes

    Sometimes there might be multiple of the same value with different
    prefixes (eg FOO_BOO=1, BAR_BOO=2), and self.BOO is first match wins, so
    it depends on order. If you need the sub value you have to give more
    information (eg, s.BAR_BOO will return 2)

    I have a tendency for different packages to have their own environment
    or settings singleton, then dependent projects will also have a settings
    singleton, so this allows these dependent projects to give their settings
    singleton access to everything

    :Example:
        from datatypes import MultiSettings
        from <SOME-PACKAGE> import settings as external_settings
        from <SOME-OTHER-PACKAGE> import environ as external_environ

        class Settings(MultiSettings):
            def __init__(self):
                super().__init__(
                    prefixes=["FOO_", "BAR_"],
                    settings=[external_settings],
                    environs=[external_environ],
                )

        # create the singleton for this project that will have access to
        # all the external configuration also
        settings = Settings()
    """
    def __init__(self, data=None, **kwargs):
        """
        :param data: dict, the local data
        :param **kwargs:
            * prefix: str, the environment prefix, this is merged with
                prefixes but this value takes precedence
            * prefixes: list[str], the environment prefixes
            * configs: list[str], the configuration files
            * settings: list[Settings], any settings to add to this instance
            * environs: list[Environ], any environs to add to this instance
            * configs: list[Config], any configuration to add to this instance
        """
        super().__init__(data, **kwargs)

        self.__dict__["settings"] = self.get_init_settings(**kwargs)

    def get_init_environ(self, environ, **kwargs):
        prefixes = []

        if environ is not None:
            prefixes.append(environ)

        if environs := kwargs.get("environs", []):
            prefixes.extend(environs)

        if p := kwargs.get("prefix", ""):
            prefixes.append(p)

        if ps := kwargs.get("prefixes", []):
            prefixes.extend(ps)

        maps = []
        for prefix in prefixes:
            if isinstance(prefix, Environ):
                maps.append(super().get_init_environ(prefix))

            else:
                maps.append(super().get_init_environ(None, prefix=prefix))

        return ChainMap(*maps)

    def get_init_config(self, config, **kwargs):
        configs = []

        if config:
            configs.append(config)

        if cs := kwargs.get("configs", []):
            configs.extend(cs)

        maps = []
        for c in configs:
            maps.append(super().get_init_config(c))

        return ChainMap(*maps)

    def get_init_settings(self, **kwargs):
        maps = kwargs.get("settings", [])
        return ChainMap(*maps)

    def add_environ(self, environ):
        """Add an Environ instance to the environs pool

        :param environ: Environ, the instance to add to the end of the pool
        """
        self.__dict__["environ"] = ChainMap(*self.environ.maps, environ)

    def add_config(self, config):
        """Add a Config instance to the end of the configs pool

        :param config: Config
        """
        self.__dict__["config"] = ChainMap(*self.config.maps, config)

    def add_settings(self, settings):
        """Add a Settings instance to the end of the settings pool

        :param settings: Settings
        """
        self.__dict__["settings"] = ChainMap(*self.settings.maps, settings)

    def get_environ(self, k):
        k = k.lower()
        for environ in self.environ.maps:
            namespace = getattr(environ, "namespace", "")
            if namespace and namespace.lower().startswith(k):
                return environ

    def get_config(self, k):
        for config in self.config.maps:
            path = getattr(config, "path", "")
            if path and path.fileroot == k:
                return config

    def _get_value(self, chainmap, k):
        """Internal method. Used to check the chainmap for an item value
        and also an attribute"""
        try:
            return super()._get_value(chainmap, k)

        except KeyError:
            for m in chainmap.maps:
                try:
                    return getattr(m, k)

                except AttributeError:
                    pass

            raise

    def get_settings_value(self, k):
        """Given a key k, attempt to get the value from any sub settings
        instances

        :param k: str, the key we're looking for
        :returns: Any
        """
        return self._get_value(self.settings, k)

    def __getitem__(self, k):
        try:
            return super().__getitem__(k)

        except KeyError:
            try:
                return self.get_settings_value(k)

            except KeyError:
                pass

            raise

