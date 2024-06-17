# -*- coding: utf-8 -*-
from logging import * # allow this module as a passthrough for builtin logging
import logging
import logging.config
from logging import config
import sys
from collections.abc import (
    Mapping,
    Sequence,
)
from string import Formatter


def get_loggers(prefix=""):
    """Return loggers matching prefix or all loggers if prefix is empty

    :params prefix: str, the logger prefix to filter returned loggers
    :returns: dict[str, logging.Logger]
    """
    loggers = Logger.manager.loggerDict
    if prefix:
        loggers = {}
        for logname, logger in Logger.manager.loggerDict.items():
            if logname.startswith(prefix):
                loggers[logname] = logger

    else:
        loggers = Logger.manager.loggerDict

    return loggers


def getlro(logger):
    """Get the Logger Resolution Order for the given logger

    This is named similar to `inspect.getmro`

    :param logger: logging.Logger
    :returns: list[logging.Logger]
    """
    loggers = [logger]
    if logger.propagate:
        while pl := logger.parent:
            loggers.append(pl)
            if not pl.propagate:
                break

    return loggers


def setdefault(name, val):
    """Set the default logging level for name to val, this will only be set if
    it wasn't configured previously

    :param name: str, the logger name
    :param val: str|int, the logger level (eg, "DEBUG", "INFO")
    """
    if name not in Logger.manager.loggerDict:
        if isinstance(val, (str, int)):
            logger = getLogger(name)
            logger.setLevel(getLevelName(val))

        else:
            raise NotImplementedError("Not sure what to do with val")


def null_config(name):
    """This will configure a null logger for name, it is meant to avoid the
    "no handler found" warnings when libraries would use logging that hadn't
    been configured, 

    NOTE -- it seems like it is no longer needed in python 3

    :param name: str, usually __name__
    """
    # get rid of "No handler found" warnings (cribbed from requests)
    logging.getLogger(name).addHandler(logging.NullHandler())


def quick_config(levels=None, **kwargs):
    """Lots of times I have to add a basic logger, it's basically the
    same code over and over again, this will just make that a little easier to
    do

    this was ripped from testdata.basic_logging() on 7-15-2022

    :example:
        from datatypes import logging
        logging.quick_config() # near top of file

        # fine-tune the levels
        testdata.basic_logging(
            levels={
                "datatypes": "WARNING",
            }
        )

    this basically does this:
        import sys, logging
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        log_handler = logging.StreamHandler(stream=sys.stderr)
        log_formatter = logging.Formatter('[%(levelname).1s] %(message)s')
        log_handler.setFormatter(log_formatter)
        logger.addHandler(log_handler)

    :param levels: dict[str, str], the key is the logger name and the value is
        the level. This can also be a list[tuple] where the tuple is (name,
        level)
    :param **kwargs: key/val, these will be passed into logger.basicConfig
        method
        * verbose_format: bool, pass in True to set the "format" key to a format
            that contains a lot more information
    """
    levels = levels or {}
    verbose = kwargs.pop("verbose_format", False)

    # configure root logger
    if verbose:
        kwargs.setdefault(
            "format",
            "|".join([
                '[%(levelname).1s',
                '%(asctime)s',
                '%(process)d.%(thread)d',
                '%(name)s', # logger name
                '%(pathname)s:%(lineno)s] %(message)s',
            ])
        )

    else:
        kwargs.setdefault("format", "[%(levelname).1s] %(message)s")

    kwargs.setdefault("level", logging.DEBUG)
    kwargs.setdefault("stream", sys.stdout)
    logging.basicConfig(**kwargs)

    # configure certain loggers
    # https://github.com/Jaymon/testdata/issues/34
    if isinstance(levels, dict):
        levels = levels.items()

    for logger_name, logger_level in levels:
        l = logging.getLogger(logger_name)
        if isinstance(logger_level, str):
            logger_level = getattr(logging, logger_level)
        l.setLevel(logger_level)

#     rlogger = logging.getLogger()
#     if not rlogger.handlers:
#         rlogger.setLevel(kwargs["level"])
#         handler = logging.StreamHandler(stream=kwargs["stream"])
#         formatter = logging.Formatter(kwargs["format"])
#         handler.setFormatter(formatter)
#         rlogger.addHandler(handler)
basic_logging = quick_config


def project_config(config=None, **kwargs):
    """I have a tendency to set up projects roughly the same way, and I've been
    copy/pasting some version of this dict_config for years, this is an effort
    to DRY this config a little bit

    This will set loggers for some of the modules I use the most, moved here
    on 2-11-2023

    :param config: dict, this dict will override the default configuration
    :param **kwargs: any specific keys will override passed in config dict
    """
    level = kwargs.pop("level", "DEBUG")
    config = config or {}
    config.update(kwargs)

    # avoid circular dependency
    from .collections import Dict

    dict_config = Dict({
        'version': 1,
        'formatters': {
            # https://docs.python.org/3/library/logging.html#logrecord-attributes
            'shortformatter': {
                'format': '[%(levelname).1s] %(message)s',
            },
            'longformatter': {
                'format': "|".join(['[%(levelname).1s',
                    '%(asctime)s',
                    '%(process)d.%(thread)d',
                    '%(filename)s:%(lineno)s] %(message)s',
                ])
            },
            'verboseformatter': {
                'format': "|".join([
                    '[%(levelname).1s',
                    '%(asctime)s',
                    '%(process)d.%(thread)d',
                    '%(name)s', # logger name
                    '%(pathname)s:%(lineno)s] %(message)s',
                ])
            },
        },
        'handlers': {
            'streamhandler': {
                'level': level,
                'class': 'logging.StreamHandler',
                'formatter': 'shortformatter',
                'filters': [],
            },
        },
        'root': {
            'level': level,
            'filters': [],
            'handlers': ['streamhandler'],
        },
        'loggers': {
    #         'botocore': {
    #             'level': 'ERROR',
    #         },
    #         'boto3': {
    #             'level': 'ERROR',
    #         },
    #         'boto': {
    #             'level': 'ERROR',
    #         },
    #         'paramiko': {
    #             'level': 'WARNING',
    #         },
            'dsnparse': {
                'level': 'INFO',
            },
            'prom': {
                #'level': 'CRITICAL',
                #'level': 'WARNING',
                #'level': 'DEBUG',
                'level': 'INFO',
            },
            'morp': {
                'level': 'INFO',
                #'level': 'DEBUG',
            },
            'decorators': {
                'level': 'WARNING',
                #'level': 'DEBUG',
            },
            'datatypes': {
                'level': 'WARNING',
                #'level': 'DEBUG',
            },
            'caches': {
                'level': 'WARNING',
                #'level': 'DEBUG',
            },
            'requests': {
                'level': 'WARNING',
            },
            'asyncio': {
                'level': 'INFO',
            },
        },
        'incremental': False,
        'disable_existing_loggers': False,
    })

    dict_config.merge(config)
    logging.config.dictConfig(dict_config)


class LogMixin(object):
    """A mixin object that can be added to classes to add some logging methods

    This was inspired by .log() methods in both morp and prom, I wanted to add
    .log_for() to prom and then thought it would be nice to have it in morp also
    so I moved the functionality into here on 2-11-2023
    """
    @classmethod
    def get_logger_instance(cls, instance_name="logger", **kwargs):
        """Get the logger class for this class

        :param instance_name: str, the name of the module level variable defined
            in the module that the child class resides. If this doesn't exist
            then a new instance will be created using the module classpath
        :returns: Logger instance
        """
        module_name = cls.__module__
        module = sys.modules[module_name]
        return getattr(module, instance_name, None) or getLogger(module_name)

    @classmethod
    def get_logging_module(cls, module_name="logging", **kwargs):
        """get the logging module defined in classes module

        :param module_name: the logging module you want to get
        :returns: module
        """
        module = sys.modules[cls.__module__]
        return sys.modules[module_name]

    @classmethod
    def get_log_level(cls, level=NOTSET, **kwargs):
        """Get the log level for class's logger

        :param level_name: str, the name of the logger level (eg, "DEBUG")
        :returns: int, the internal logging log level
        """
        if level == NOTSET:
            default_level = kwargs.get("default_level", "DEBUG")
            level = kwargs.get(
                "level_name",
                kwargs.get("level_name", default_level)
            )

        if not isinstance(level, int):
            logmod = cls.get_logging_module(**kwargs)
            # getLevelName() returns int if passed in arg is string
            level = logmod.getLevelName(level.upper())
        return level

    @classmethod
    def is_logging(cls, level, **kwargs):
        """Wrapper around logger.isEnabledFor

        :param level: str|int, the logging level we want to check
        :param **kwargs:
        :returns: bool, True if the level has logging enabled
        """
        if not isinstance(level, int):
            level = cls.get_log_level(level, **kwargs)

        logger = cls.get_logger_instance(**kwargs)
        return logger.isEnabledFor(level)

    def log_for(self, **kwargs):
        """set different logging messages for different log levels

        :Example:
            self.log_for(
                debug=(["debug log message {}", debug_msg], {}),
                INFO=(["info log message {}", info_msg],),
                warning=(["warning message"], {}),
                ERROR=(["error message"],),
            )

        :param **kwargs: each key can have a tuple of (args, kwargs) that will
            be passed to .log(), the key should be a log level name and can be
            either upper or lower case
        """
        logger = self.get_logger_instance(**kwargs)
        logmod = self.get_logging_module(**kwargs)
        level_name = logmod.getLevelName(logger.getEffectiveLevel())

        if level_name not in kwargs:
            level_name = level_name.lower()

        if level_name in kwargs:
            args = kwargs[level_name]
            if isinstance(args, str):
                # debug="a string value"
                log_args = [args]
                log_kwargs = {}

            elif isinstance(args, Sequence):
                if len(args) == 2:
                    if (
                        isinstance(args[0], Sequence)
                        and isinstance(args[1], Mapping)
                    ):
                        # debug=("a string value", {})
                        # debug=(["a", "list", "value"], {})
                        log_args = [args[0]]
                        log_kwargs = args[1]

                    else:
                        # debug=["a list", "value"]
                        log_args = args
                        log_kwargs = {}

                else:
                    log_args = args
                    log_kwargs = {}

            else:
                raise ValueError(f"Unknown value for {level_name}")

            if len(log_args) == 1 and isinstance(log_args[0], list):
                # https://docs.python.org/3/library/string.html#string.Formatter
                parts = list(Formatter().parse(log_args[0][0]))
                if len(parts) > 1 or parts[0][1] is not None:
                    log_args = log_args[0] 

            log_kwargs["level"] = level_name
            self.log(*log_args, **log_kwargs)

    def get_log_message(self, format_str, *format_args, **kwargs):
        """Returns the logging message that will be logged using .log()"""
        if format_args:
            return format_str.format(*format_args)

        else:
            return format_str

    def log(self, format_str, *format_args, **kwargs):
        """wrapper around the module's logger

        :param format_str: str|list[str], the message to log, if this is a list
            then it will be joined with a space
        :param *format_args: list, if format_str is a string containing {},
            then format_str.format(*format_args) is ran
        :param **kwargs:
            level: str|int, something like logging.DEBUG or "DEBUG"
            sentinel: callable|bool, if evaluates to False then the log will be
                ignored
        """
        sentinel = kwargs.pop("sentinel", None)
        if sentinel is None:
            sentinel = True

        else:
            if callable(sentinel):
                sentinel = sentinel()

        logger = self.get_logger_instance(**kwargs)
        if isinstance(format_str, Exception):
            level = self.get_log_level(default_level="ERROR", **kwargs)
            if self.is_logging(level) and sentinel:
                logger.log(level, f"{format_str}", *format_args)

        else:
            if isinstance(format_str, list):
                format_str = " ".join(filter(None, format_str))

            level = self.get_log_level(**kwargs)
            if self.is_logging(level) and sentinel:
                try:
                    logger.log(
                        level,
                        self.get_log_message(format_str, *format_args, **kwargs)
                    )

                except UnicodeError as e:
                    logger.exception(e)

    def log_warning(self, *args, **kwargs):
        kwargs["level"] = "WARNING"
        return self.log(*args, **kwargs)

    def logw(self, *args, **kwargs):
        return self.log_warning(*args, **kwargs)

    def log_info(self, *args, **kwargs):
        kwargs["level"] = "INFO"
        return self.log(*args, **kwargs)

    def logi(self, *args, **kwargs):
        return self.log_info(*args, **kwargs)

    def log_debug(self, *args, **kwargs):
        kwargs["level"] = "DEBUG"
        return self.log(*args, **kwargs)

    def logd(self, *args, **kwargs):
        return self.log_debug(*args, **kwargs)

    def log_error(self, *args, **kwargs):
        kwargs["level"] = "ERROR"
        return self.log(*args, **kwargs)

    def loge(self, *args, **kwargs):
        return self.log_error(*args, **kwargs)

    def log_critical(self, *args, **kwargs):
        kwargs["level"] = "CRITICAL"
        return self.log(*args, **kwargs)

    def logc(self, *args, **kwargs):
        return self.log_critical(*args, **kwargs)

