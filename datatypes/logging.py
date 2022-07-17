# -*- coding: utf-8 -*-
from logging import * # allow using this module as a passthrough for builtin logging
import logging
import sys


def null_config(name):
    """This will configure a null logger for name, it is meant to avoid the "no handler found"
    warnings when libraries would use logging that hadn't been configured, but it
    seems like it is no longer needed in python 3

    :param name: str, usually __name__
    """
    # get rid of "No handler found" warnings (cribbed from requests)
    logging.getLogger(__name__).addHandler(logging.NullHandler())


def quick_config(**kwargs):
    """Lots of times I have to add a basic logger, it's basically the
    same code over and over again, this will just make that a little easier to do

    this was ripped from testdata.basic_logging() on 7-15-2022

    :example:
        from datatypes import logging
        logging.quick_config() # near top of file

    this basically does this:
        import sys, logging
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        log_handler = logging.StreamHandler(stream=sys.stderr)
        log_formatter = logging.Formatter('[%(levelname).1s] %(message)s')
        log_handler.setFormatter(log_formatter)
        logger.addHandler(log_handler)

    :param **kwargs: key/val, these will be passed into logger.basicConfig method
    """
    levels = kwargs.pop("levels", [])

    # configure root logger
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


