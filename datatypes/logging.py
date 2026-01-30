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
from typing import Literal
import string


type Level = str|int|Callable
type Levels = Mapping[str, Level]|Sequence[tuple[str, Level]]


SHORT_FORMAT = "[%(levelname).1s] %(message)s"

LONG_FORMAT = "|".join([
    "[%(levelname).1s",
    "%(asctime)s",
    "%(process)d.%(thread)d",
    "%(filename)s:%(lineno)s] %(message)s",
])

VERBOSE_FORMAT = "|".join([
    "[%(levelname).1s",
    "%(asctime)s",
    "%(process)d.%(thread)d",
    "%(name)s", # logger name
    "%(pathname)s:%(lineno)s] %(message)s",
])

MSG_FORMAT = "%(message)s"


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


def _get_quick_config(**kwargs) -> Mapping:
    """Internal function. Called from `quick_config` and `Logger.quick_config`
    and shouldn't be called outside of those. THis just normalizes `kwargs`
    and gets it ready to actually configure the Logger instance"""
    if "format" in kwargs:
        if kwargs["format"] == "short":
            kwargs["format"] = SHORT_FORMAT

        elif kwargs["format"] == "long":
            kwargs["format"] = LONG_FORMAT

        elif kwargs["format"] == "verbose":
            kwargs["format"] = VERBOSE_FORMAT

        elif kwargs["format"] == "msg":
            kwargs["format"] = MSG_FORMAT

        elif kwargs["format"] == "basic":
            kwargs["format"] = BASIC_FORMAT

    else:
        verbose = kwargs.pop("verbose_format", False)
        long = kwargs.pop("long_format", False)
        short = kwargs.pop("short_format", False)
        msg = kwargs.pop("msg_format", False)
        basic = kwargs.pop("basic_format", False)
        if verbose:
            kwargs["format"] = VERBOSE_FORMAT

        elif long:
            kwargs["format"] = LONG_FORMAT

        elif msg:
            kwargs["format"] = MSG_FORMAT

        elif basic:
            kwargs["format"] = BASIC_FORMAT

        else:
            kwargs["format"] = SHORT_FORMAT

    kwargs.setdefault("level", logging.DEBUG)

    if "stream" in kwargs and isinstance(kwargs["stream"], str):
        if kwargs["stream"] == "stdout":
            kwargs["stream"] = sys.stdout

        elif kwargs["stream"] == "stderr":
            kwargs["stream"] = sys.stderr

        else:
            raise ValueError(f"Unrecognized stream value: {kwargs['stream']}")

    else:
        kwargs.setdefault("stream", sys.stdout)

    return kwargs


def _set_levels(levels: Levels) -> None:
    """Configure certain loggers

    :param levels: keys are logger names, value is the level for that logger
    """
    # https://github.com/Jaymon/testdata/issues/34
    if isinstance(levels, Mapping):
        levels = levels.items()

    for logger_name, logger_level in levels:
        l = getLogger(logger_name)
        l.setLevel(logger_level)


def quick_config(levels: Levels|None = None, **kwargs):
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
                "datatypes": "DEBUG",
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

    https://docs.python.org/3/library/logging.html#logging.basicConfig

    :param levels: dict[str, str], the key is the logger name and the value is
        the level. This can also be a list[tuple] where the tuple is (name,
        level)
        method
    :keyword format: Literal["verbose", "long", "short", "msg", "basic"],
        defaults to "short", this is the type of output wanted
    :keyword stream: io.IOBase|Literal["stdout", "stderr"]
    :keyword name: str, if passed in this is considered the primary logger
        name and this will cause root to default to warning and the logger
        at this name to default to debug
    :keyword **kwargs: key/val, these will be passed into logger.basicConfig
    """
    #setLoggerClass(Logger)
    #setLogRecordFactory(LogRecord)
    levels = levels or {}

    # https://github.com/Jaymon/datatypes/issues/69
    if name := kwargs.pop("name", ""):
        name = name.split(".", 1)[0]
        kwargs.setdefault("level", "WARNING")
        levels.setdefault(name, "DEBUG")

    kwargs = _get_quick_config(**kwargs)
    basicConfig(**kwargs)
    _set_levels(levels)


def project_config(config: Mapping|None = None, **kwargs) -> None:
    """I have a tendency to set up projects roughly the same way, and I've been
    copy/pasting some version of this dict_config for years, this is an effort
    to DRY this config a little bit

    This will set loggers for some of the modules I use the most, moved here
    on 2-11-2023

    https://docs.python.org/3/library/logging.config.html#logging.config.dictConfig

    :param config: dict, this dict will override the default configuration
    :keyword level: Level, the minimum level unless `name` is passed in, then
        it is the level of the `name` logger, defaults to debug
    :keyword root_level: Level, the minimum root level logger, set to `level`
        unless `name` is passed in, then set to warning unless passed in
        explicitly
    :keyword name: str, the project logger name that is being configured, if
        this is passed in then the logger at `name` will be configured at
        level `level` (defaults to debug) and `root_level` will default to
        warning
    :keyword levels: Levels, passed to `._set_levels`
    :keyword **kwargs: any specific keys will override passed in config dict
    """
    setLoggerClass(Logger)
    #setLogRecordFactory(LogRecord)

    config = config or {}
    levels = kwargs.pop("levels") or {}

    level = getLevelName(kwargs.pop("level", "DEBUG"))

    if name := kwargs.pop("name", ""):
        name = name.split(".", 1)[0]
        root_level = kwargs.pop("root_level", "WARNING")

        config.setdefault("loggers", {})
        config["loggers"].setdefault(name, {})
        config["loggers"][name].setdefault("level", level)

    else:
        root_level = kwargs.pop("root_level", level)

    config.update(kwargs)

    # avoid circular dependency
    from .collections import Dict

    dict_config = Dict({
        "version": 1,
        "formatters": {
            # https://docs.python.org/3/library/logging.html#logrecord-attributes
            "short": {
                "format": SHORT_FORMAT,
            },
            "long": {
                "format": LONG_FORMAT,
            },
            "verbose": {
                "format": VERBOSE_FORMAT,
            },
            "msg": {
                "format": MSG_FORMAT,
            },
            "basic": {
                "format": BASIC_FORMAT,
            },
        },
        "handlers": {
            "stream": {
                #'level': level,
                "class": "logging.StreamHandler",
                "formatter": "short",
                #'filters': [],
            },
        },
        "root": {
            "level": getLevelName(root_level),
            "filters": [],
            "handlers": ["stream"],
        },
        "loggers": {
            "asyncio": {
                "level": "INFO",
            },
            "dsnparse": {
                "level": "INFO",
            },
            "prom": {
                "level": "INFO",
            },
            "morp": {
                "level": "INFO",
            },
            "decorators": {
                "level": "WARNING",
            },
            "datatypes": {
                "level": "WARNING",
            },
            "caches": {
                "level": "WARNING",
            },
            "requests": {
                "level": "WARNING",
            },
        },
        "incremental": False,
        "disable_existing_loggers": False,
    })

    dict_config.merge(config)
    logging.config.dictConfig(dict_config)
    _set_levels(levels)


def getLevelName(
    level: Level
) -> Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
    """Wrapper around stdlib `getLevelName` that can also take the logging
    methods"""
    if callable(level):
        level = level.__name__

    if isinstance(level, str):
        level = level.upper()

    return logging.getLevelName(level)


def getLevel(
    level: Level
) -> Literal[NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL]:
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
        if len(self.handlers) == 0:
            _acquireLock()
            try:
                kwargs = _get_quick_config(**kwargs)
                log_handler = StreamHandler(stream=kwargs["stream"])
                log_handler.setFormatter(Formatter(kwargs["format"]))
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

    def _log(
        self,
        level: int,
        msg: str,
        args: Sequence,
        exc_info: BaseException|bool|tuple|None = None,
        extra: Mapping|None = None,
        stack_info: bool = False,
        stacklevel: int = 1, 
        **kwargs,
    ) -> None:
        """Wrapper around parent's internal method, mostly everything is the
        same except this can take a few more keywords to customize behavior

        :keyword enabled_for: Level, set this to only log if self is
            enabled for the level, this allows you to do thing like only log a 
            warning if debug is enabled and is just another way to fine tune
            the logging
        :keyword style: Literal["%", "{", "=", "$"]
            * `%` = printf, the default, `msg % args` will be called
                https://docs.python.org/3/library/stdtypes.html#old-string-formatting
            * `{` = format, use `msg.format` will be called with args and
                kwargs
                https://docs.python.org/3/library/string.html#format-string-syntax
            * `$` = template, msg will be wrapped in string.Template and
                `Template.substitute` will be called with args and kwargs
                https://docs.python.org/3/library/string.html#template-strings-strings
            * `=` = golang slog, similar to golang's slog logger, the main
                message is followed by key, value arguments that are added
                to the end of the message
                https://pkg.go.dev/log/slog#TextHandler
        """
        enabled_level = kwargs.pop("enabled_for", None)
        if enabled_level is not None:
            if not self.isEnabledFor(enabled_level):
                return

        # the style keyword matches `.basicConfig` style keyword
        if style := kwargs.pop("style", ""):
            if self.isEnabledFor(level):
                if style == "{":
                    msg = msg.format(*args, **kwargs)
                    args = []

                elif style == "=":
                    for i in range(0, len(args), 2):
                        key = args[i]
                        value = args[i + 1]
                        if value.find(" ") >= 0:
                            value = "\"" + value + "\""

                        msg += " " + key + "=" + value

                    args = []

                elif style == "$":
                    msg = string.Template(msg).substitute(*args, **kwargs)
                    args = []

        return super()._log(
            level,
            msg,
            args,
            exc_info,
            extra,
            stack_info,
            stacklevel,
        )

    def log_for(self, **kwargs) -> None:
        """set different logging messages for different log levels

        :example:
            logger.log_for(
                debug=("debug log message {}", debug_msg),
                INFO=("info log message {}", info_msg),
                warning=(["warning message"], {}),
                ERROR="error message",
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
                    # debug=(["msg %s", "value"], {"k1": "v1"})
                    log_args = args[0]
                    log_kwargs = args[1]

                else:
                    # debug=["msg %s", "value"]
                    log_args = [args[0], tuple(args[1:])]

            self._log(level, *log_args, **kwargs, **log_kwargs)

