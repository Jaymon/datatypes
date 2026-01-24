# -*- coding: utf-8 -*-
from logging import * # allow this module as a passthrough for builtin logging
from logging import (
    config,
    root,
    _acquireLock,
    _releaseLock,
)
import logging # access to stdlib if needed
import sys
from collections.abc import (
    Mapping,
    Sequence,
    Generator,
    Callable,
)
import string


type Level = str|int|Callable

FORMAT_SHORT = "[%(levelname).1s] %(message)s"

FORMAT_LONG = "|".join([
    "[%(levelname).1s",
    "%(asctime)s",
    "%(process)d.%(thread)d",
    "%(filename)s:%(lineno)s] %(message)s",
])

FORMAT_VERBOSE = "|".join([
    "[%(levelname).1s",
    "%(asctime)s",
    "%(process)d.%(thread)d",
    "%(name)s", # logger name
    "%(pathname)s:%(lineno)s] %(message)s",
])


def has_logger(name: str) -> bool:
    """Return True if name exists in the loggers"""
    if name in Logger.manager.loggerDict:
        return True

    else:
        if name == "root":
            return Logger.manager.root is not None


def get_loggers(prefix: str = "") -> Generator[str, Logger]:
    """Return loggers matching prefix or all loggers if prefix is empty

    :params prefix: str, the logger prefix to filter returned loggers
    :returns: all the loggers, including the root logger
    """
    loggers = Logger.manager.loggerDict
    if prefix:
        loggers = {}
        for logname, logger in Logger.manager.loggerDict.items():
            if logname.startswith(prefix):
                yield logname, logger

    else:
        yield from Logger.manager.loggerDict.items()

    if not prefix or Logger.manager.root.name.startswith(prefix):
        yield Logger.manager.root.name, Logger.manager.root


def get_handlers(logger: Logger|None = None) -> Generator[Logger, Handler]:
    """Return loggers and their handlers

    :param logger: if a logger is passed in then only returns the handlers
        of this logger
    :returns: tuples of the logger instance and a handler instance for that
        logger
    """
    if logger is None:
        for _, logger in get_loggers():
            yield from get_handlers(logger)

    else:
        for handler in getattr(logger, "handlers", []):
            yield logger, handler


def getlro(logger: Logger) -> Generator[Logger]:
    """Get the Logger Resolution Order for the given logger

    This is named similar to `inspect.getmro`

    :returns: the loggers in resolution order starting with the passed in
        logger
    """
    yield logger

    if logger.propagate:
        while pl := logger.parent:
            yield pl
            if not pl.propagate:
                break


def setdefault(name: str, val: str|int):
    """Set the default logging level for name to val, this will only be set if
    it wasn't configured previously

    :param name: str, the logger name
    :param val: str|int, the logger level (eg, "DEBUG", "INFO")
    """
    if not has_logger(name):
        if isinstance(val, (str, int)):
            logger = getLogger(name)
            logger.setLevel(getLevelName(val))

        else:
            raise NotImplementedError("Not sure what to do with val")


def _get_quick_config(**kwargs) -> str:
    if "format" in kwargs:
        if kwargs["format"] == "short":
            kwargs["format"] = FORMAT_SHORT

        elif kwargs["format"] == "long":
            kwargs["format"] = FORMAT_LONG

        elif kwargs["format"] == "verbose":
            kwargs["format"] = FORMAT_VERBOSE

    else:
        verbose = kwargs.pop("verbose_format", False)
        long = kwargs.pop("long_format", False)
        short = kwargs.pop("short_format", False)
        if verbose:
            kwargs["format"] = FORMAT_VERBOSE

        elif long:
            kwargs["format"] = FORMAT_LONG

        else:
            kwargs["format"] = FORMAT_SHORT

    kwargs.setdefault("level", logging.DEBUG)
    kwargs.setdefault("stream", sys.stdout)
    return kwargs


def quick_config(levels=None, **kwargs):
    """Lots of times I have to add a basic logger, it's basically the
    same code over and over again, this will just make that a little easier to
    do

    this was ripped from testdata.basic_logging() on 7-15-2022

    :example:
        from datatypes import logging
        logging.quick_config() # near top of file

        # fine-tune the levels
        logging.quick_config(
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
        method
    :keyword verbose_format: bool, pass in True to set the "format" key to a
        format that contains a lot more information
    :keyword **kwargs: key/val, these will be passed into logger.basicConfig
    """
    #setLoggerClass(Logger)
    #setLogRecordFactory(LogRecord)

    levels = levels or {}

    kwargs = _get_quick_config(**kwargs)
    basicConfig(**kwargs)

    # configure certain loggers
    # https://github.com/Jaymon/testdata/issues/34
    if isinstance(levels, Mapping):
        levels = levels.items()

    for logger_name, logger_level in levels:
        l = getLogger(logger_name)
        if isinstance(logger_level, str):
            logger_level = getattr(logging, logger_level)
        l.setLevel(logger_level)

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
    setLoggerClass(Logger)
    #setLogRecordFactory(LogRecord)

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
                'format': FORMAT_SHORT,
            },
            'longformatter': {
                'format': FORMAT_LONG,
            },
            'verboseformatter': {
                'format': FORMAT_VERBOSE,
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
    config.dictConfig(dict_config)


def getLevelName(level: Level):
    """Wrapper around stdlib `getLevelName` that can also take the logging
    methods"""
    if callable(level):
        level = level.__name__

    if isinstance(level, str):
        level = level.upper()

    return logging.getLevelName(level)


def getLevel(level: Level):
    """This is named `getLevel` instead of `get_level` to match `getLevelName`
    """
    if not isinstance(level, int):
        level = getLevelName(level)
    return level


def getLevelMethod(level: Level, logger: Logger|str) -> Callable:
    """get the logging method from `logger` for `level`"""
    level = getLevel(level)
    level_name = getLevelName(level)
    return getattr(logger, level_name.lower())


def getLogger(name: str|None = None, logger_class:Logger|None = None) -> Logger:
    """Overrides the standard lib `getLogger` class to return this module's
    Logger instance

    :param name: the logger name
    :param logger_class: if you have a customized logger class you can pass
        it in, this allows a little easier Logger instance customization
    """
    if not name or isinstance(name, str) and name == root.name:
        return root

    if logger_class is None:
        logger_class = Logger

    prev_logger_class = Logger.manager.loggerClass
    logger_class.manager.setLoggerClass(logger_class)

    logger = logger_class.manager.getLogger(name)

    logger_class.manager.loggerClass = prev_logger_class

    return logger


# class LogRecord(LogRecord):
#     pass


class Logger(Logger):
    """Wrapper around stdlib logger that adds some helpful methods

    Log message lifecycle:
        * Logger method (eg, `.debug`, `.log`)
        * `Logger._log`
        * `Logger.makeRecord`
        * `Logger.handle`
        * `Logger.filter`
        * `Logger.callHandlers` - call each handler's `handle` method
        * `Handler.handle`
        * `Handler.emit`
        * `Handler.format`
        * `Formatter.format`
        * `LogRecord.getMessage`
        * `Formatter.formatMessage`
    """
    def quick_config(self, **kwargs):
        """Apply a subset of `logging.basicConfig` and `logging.quick_config`
        to this instance

        https://docs.python.org/3/library/logging.html#logging.basicConfig
        """
        _acquireLock()
        try:
            kwargs = _get_quick_config(**kwargs)
            log_formatter = Formatter(kwargs["format"])
            log_handler = StreamHandler(stream=kwargs["stream"])
            log_handler.setFormatter(log_formatter)
            self.addHandler(log_handler)
            self.setLevel(kwargs["level"])

        finally:
            _releaseLock()

    def getEffectiveLevelName(self) -> str:
        """Similar to the `.getEffectiveLevel` but returns the string
        level name, that's why the name is camel cased"""
        level = self.getEffectiveLevel()
        return getLevelName(level)

    def isEnabledFor(self, level: Level) -> bool:
        """Wrapper around parent isEnabledFor that is just a bit more
        loose with how the level needs to be defined

        :param level: 
        :param **kwargs:
        :returns: bool, True if the level has logging enabled
        """
        level = getLevel(level)
        return super().isEnabledFor(level)

    def setLevel(self, level: Level) -> None:
        """Wrapper around parent setLevel that is just a bit more loose with
        how the level needs to be defined"""
        level = getLevel(level)
        return super().setLevel(level)

    def log(self, level: Level, msg: str, *args, **kwargs) -> None:
        """Wrapper around parent method that makes level a bit more loose"""
        level = getLevel(level)
        return super().log(level, msg, *args, **kwargs)

#     def log(self, level: Level, msg: str, *args, **kwargs) -> None:
#         level = getLevel(level)
# 
#         # the style keyword matches `.basicConfig` style keyword
#         style = kwargs.pop("style", "%")
#         # % = printf
#         # { = format
#         # $ = template
#         if style == "{":
#             if self.isEnabledFor(level):
#                 msg = msg.format(*args)
#                 args = []
# 
#         return super().log(level, msg, *args, **kwargs)

#     def makeRecord(self, *args, **kwargs):
#         record = super().makeRecord(*args, **kwargs)
# 
#         pout.v(record.msg)
#         pout.v(record.args)
#         pout.v("%s %s" % tuple(record.args))
# 
# 
# 
#         pout.v(record)
#         return record

    def _log(self, level: int, msg: str, args: Sequence, **kwargs) -> None:
        """Wrapper around parent's internal method, mostly everything is the
        same except this can take a few more keywords to customize behavior

        :keyword enabled_for: Level, set this to only log if self is
            enabled for the level, this allows you to do thing like only log a 
            warning if debug is enabled and is just another way to fine tune
            the logging
        :keyword style: Literal["%", "{", ","]
            * `%` = printf, the default
            * `{` = format, use `msg.format`
            * `$` = template, not supported right now
            * `,` = golang slog, similar to golang's slog logger, the main
                message is followed by key, value arguments that are added
                to the end of the message
        """
        enabled_level = kwargs.pop("enabled_for", None)
        if enabled_level is not None:
            if not self.isEnabledFor(enabled_level):
                return

        # the style keyword matches `.basicConfig` style keyword
        style = kwargs.pop("style", "%")
        if self.isEnabledFor(level):
            # % = printf
            # { = format
            # $ = template
            # , = glang slog
            if style == "{":
                msg = msg.format(*args)
                args = []

            elif style == ",":
                for i in range(0, len(args), 2):
                    key = args[i]
                    value = args[i + 1]
                    if value.find(" ") >= 0:
                        value = "\"" + value + "\""

                    msg += " " + key + "=" + value

                args = []

#             if kwargs["extra"] is None:
#                 kwargs["extra"] = {}
# 
#             kwargs["extra"]["style"] = style

        return super()._log(level, msg, args, **kwargs)

    def log_for(self, **kwargs) -> None:
        """set different logging messages for different log levels

        :example:
            logger.log_for(
                debug=(["debug log message {}", debug_msg], {}),
                INFO=(["info log message {}", info_msg],),
                warning=(["warning message"], {}),
                ERROR=(["error message"],),
            )

        :param **kwargs: each key can have a tuple of (args, kwargs) that will
            be passed to .log(), the key should be a log level name and can be
            either upper or lower case
        """
        level = self.getEffectiveLevel()
        level_name = getLevelName(level)

        if "log" in kwargs:
            kwargs = {**kwargs.pop("log"), **kwargs}
            level_method = getLevelMethod(level, self)
            keys = (level, level_name, level_method, level_method.__name__)

        else:
            keys = (level_name, level_name.lower())

        args = None
        for k in keys:
            if k in kwargs:
                args = kwargs[k]
                break

        if args is not None:
            log_args = []
            log_kwargs = {}

            if isinstance(args, str):
                # debug="msg"
                log_args = [args, []]

            elif isinstance(args, Sequence):
                if (
                    len(args) == 2
                    and (
                        isinstance(args[0], Sequence)
                        and isinstance(args[1], Mapping)
                    )
                ):
                    # debug=("msg", {})
                    log_args = [args[0]]
                    log_kwargs = args[1]

                else:
                    # debug=["msg %s", "value"]
                    log_args = [args[0], tuple(args[1:])]

            for k in ["style", "enabled_for"]:
                if k in kwargs:
                    log_kwargs.setdefault(k, kwargs[k])

            self._log(level, *log_args, **log_kwargs)

#     def debug_info(self, *args, **kwargs):
#         if self.isEnabledFor(DEBUG):
#             self.info(*args, **kwargs)
# 
#     def debug_warning(self, *args, **kwargs):
#         if self.isEnabledFor(DEBUG):
#             self.warning(*args, **kwargs)
# 
#     def debug_error(self, *args, **kwargs):
#         if self.isEnabledFor(DEBUG):
#             self.error(*args, **kwargs)
# 
#     def debug_exception(self, *args, **kwargs):
#         if self.isEnabledFor(DEBUG):
#             self.exception(*args, **kwargs)
# 
#     def debug_critical(self, *args, **kwargs):
#         if self.isEnabledFor(DEBUG):
#             self.critical(*args, **kwargs)

#     def D(self, *args, **kwargs):
#         return self.debug(*args, **kwargs)
# 
#     def I(self, *args, **kwargs):
#         return self.info(*args, **kwargs)
# 
#     def W(self, *args, **kwargs):
#         return self.warning(*args, **kwargs)
# 
#     def E(self, *args, **kwargs):
#         return self.error(*args, **kwargs)
# 
#     def X(self, *args, **kwargs):
#         return self.exception(*args, **kwargs)
# 
#     def C(self, *args, **kwargs):
#         return self.critical(*args, **kwargs)


class LogMixin(object):
    """A mixin object that can be added to classes to add some logging methods

    NOTE -- this is deprecated in favor of just using the custom logger,
    I will remove this once I've audited some other projects to remove this
    mixin

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
                parts = list(string.Formatter().parse(log_args[0][0]))
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

