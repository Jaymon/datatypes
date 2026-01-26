# -*- coding: utf-8 -*-
import time

from datatypes.compat import *
from datatypes import logging
from datatypes.logging import (
    Logger,
)

from . import TestCase


class LoggingTest(TestCase):
    def test_getLevelMethod(self):
        logger = Logger("getLevelMethod")
        lm = logging.getLevelMethod("DEBUG", logger)
        self.assertEqual("debug", lm.__name__)

    def test_setdefault_found(self):
        modpath = self.create_module([
            "from datatypes import logging",
            "",
            "logging.setdefault(__name__, logging.INFO)",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            "logger.debug('debug')",
            "logger.info('info')",
            "logger.warning('warning')",
        ])

        with self.assertLogs() as cm:
            # no logger was set so just info and warning should print
            m = modpath.module()

        self.assertEqual(2, len(cm[1]))
        self.assertTrue(cm[1][0].startswith("INFO:"))
        self.assertTrue(cm[1][1].startswith("WARNING:"))

    def test_setdefault_ignored(self):
        modpath = self.create_module([
            "from datatypes import logging",
            "",
            "logging.setdefault(__name__, logging.INFO)",
            "",
            "logger = logging.getLogger(__name__)",
            "",
            "logger.debug('debug')",
            "logger.info('info')",
            "logger.warning('warning')",
        ])

        logger = logging.getLogger(modpath.fileroot)
        logger.setLevel(logging.DEBUG)

        with self.assertLogs(level="DEBUG") as cm:
            # logger was configured before so all logs should print
            m = modpath.module()

        self.assertEqual(3, len(cm[1]))
        self.assertTrue(cm[1][0].startswith("DEBUG:"))
        self.assertTrue(cm[1][1].startswith("INFO:"))
        self.assertTrue(cm[1][2].startswith("WARNING:"))


class LoggerTest(TestCase):
    def get_logger(self, name: str) -> Logger:
        logger = logging.getLogger(name)
        #logger.quick_config()

        # assert*Logs needs the root logger to capture logs
        #logger.parent = logging.root
        return logger

    def test_quick_config(self):
        logger = self.get_logger("quick_config")
        logger.quick_config() # no errors == passed

    def test_isEnabledFor(self):
        logger = self.get_logger("IsEnabledFor")

        r = logger.isEnabledFor("DEBUG")
        self.assertTrue(isinstance(r, bool))

        r = logger.isEnabledFor(logging.DEBUG)
        self.assertTrue(isinstance(r, bool))

        r = logger.isEnabledFor(logging.debug)
        self.assertTrue(isinstance(r, bool))

    def test_log_for_1(self):
        logger = self.get_logger("log_for_1")

        logger.setLevel("INFO")
        with self.assertLogs(level="INFO") as cm:
            logger.log_for(info="info log")

        logger.setLevel("WARNING")
        # https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs
        with self.assertNoLogs(level="INFO") as cm:
            logger.log_for(info="info log")

    def test_log_for_str(self):
        logger = self.get_logger("log_for_str")

        logger.setLevel("INFO")
        with self.assertLogs(level="INFO") as cm:
            logger.log_for(info="info 1")
            self.assertTrue("info 1" in cm[1][0])

    def test_log_for_list(self):
        logger = self.get_logger("log_for_list")
        logger.setLevel("INFO")

        with self.assertLogs(level="INFO") as cm:
            logger.log_for(info=["info %s %s", "1", "2"])
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            logger.log_for(info=["info %s", "2"])
            self.assertTrue("info 2" in cm[1][0])

    def test_log_for_tuple(self):
        logger = self.get_logger("log_for_list")

        with self.assertLogs(logger=logger, level="INFO") as cm:
            logger.log_for(info=("%d - %d - %d", 1, 2, 3))
            self.assertTrue("1 - 2 - 3" in cm[1][0])

        with self.assertLogs(logger=logger, level="INFO") as cm:
            logger.log_for(info=("info {} {}", "1", "2"), style="{")
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(logger=logger, level="INFO") as cm:
            logger.log_for(info=("info 1 2",))
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(logger=logger, level="INFO") as cm:
            logger.log_for(info=["info %s %s", "1", "2"])
            self.assertTrue("info 1 2" in cm[1][0])

#         with self.assertLogs(level="INFO") as cm:
#             s.log_for(
#                 info=([["info {}", "2", "{}"], "1", "3"]),
#             )
#             self.assertTrue("info 1 2 3" in cm[1][0])
# 
#         with self.assertLogs(level="INFO") as cm:
#             logstr = [
#                 "1.",
#                 "foo",
#                 "-> bar"
#             ]
#             s.log_for(
#                 info=(logstr, {"sentinel": True}),
#             )
#             self.assertTrue("1. foo -> bar" in cm[1][0])


    def test__log_enabled_for(self):
        logger = self.get_logger("log_enabled_for")

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.warning("warning", enabled_for="DEBUG")
        self.assertEqual(1, len(cm.records))
        self.assertEqual("WARNING", cm.records[0].levelname)

        with self.assertRaises(AssertionError):
            with self.assertLogs(logger=logger, level="INFO") as cm:
                logger.warning("warning", enabled_for="DEBUG")

    def test__log_style_format(self):
        logger = self.get_logger("log_style_format")

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("format {} {}", 1, 2, style="{")
        self.assertTrue(cm.output[0].endswith("format 1 2"))

    def test__log_style_golang(self):
        logger = self.get_logger("log_style_golang")

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("golang", "k1", "v1", "k2", "v 2", style="=")
        self.assertTrue(cm.output[0].endswith("golang k1=v1 k2=\"v 2\""))

    def test__log_style_printf(self):
        logger = self.get_logger("log_style_printf")

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("printf %d %d", 1, 2, style="%")
        self.assertTrue(cm.output[0].endswith("printf 1 2"))

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("printf %d %d", 1, 2)
        self.assertTrue(cm.output[0].endswith("printf 1 2"))

    def test__log_style_template(self):
        logger = self.get_logger("log_style_template")

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("template $one $two", {"one": 1, "two": 2}, style="$")
        self.assertTrue(cm.output[0].endswith("template 1 2"))

        with self.assertLogs(logger=logger, level="DEBUG") as cm:
            logger.debug("template $one $two", one=1, two=2, style="$")
        self.assertTrue(cm.output[0].endswith("template 1 2"))

    def test_hierarchy(self):
        l1 = self.get_logger("abc.def.g")
        l2 = self.get_logger("abc.def.h")

        #l1.propogate = False
        l1.setLevel("DEBUG")

        #l2.propogate = False
        l2.setLevel("DEBUG")

        l1.manager.root.setLevel("WARNING")

        for l in [l1, l2, l1.manager.root]:
            l.debug(f"{l.name} - debug")
            l.info(f"{l.name} - info")
            l.warning(f"{l.name} - warning")
            l.error(f"{l.name} - error")
            l.critical(f"{l.name} - critical")





#         return
# 
# 
#         logger = logging.getLogger("log_for_1")
#         logger.debug("debug")
#         logger.info("info")
#         logger.warning("warning")
#         logger.error("error")
#         logger.critical("critical")
#         pout.v(type(logger).__module__, type(logger).__qualname__)
#         return
# 
#         logger = Logger("log_for_1")
# 
#         pout.v(logging.getLevelName(logging.root.getEffectiveLevel()))
#         return
# 
#         for l in logging.getlro(logger):
#             pout.v(l)
# 
#         return
# 
# 
# 
#         import sys
#         log_handler = logging.StreamHandler(stream=sys.stderr)
#         log_formatter = logging.Formatter('[%(levelname).1s] %(message)s')
#         log_handler.setFormatter(log_formatter)
#         logger.addHandler(log_handler)
# 
#         logger.setLevel("DEBUG")
#         pout.v(logging.getLevelName(logger.getEffectiveLevel()))
#         pout.v(logger.isEnabledFor("INFO"))
# 
#         logger.debug("debug")
#         logger.info("info")
#         logger.warning("warning")
#         logger.error("error")
#         logger.critical("critical")
#         return
#         with self.assertLogs(level="INFO") as cm:
#             logger.log_for(info="info log")
# 
# 
#         logger.setLevel("WARNING")
#         # https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs
#         with self.assertNoLogs(level="INFO") as cm:
#             logger.log_for(info="info log")

#     def test_log_for_sentinel_1(self):
#         logger = Logger("log_for_sentinel_1")
# 
#         # https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs
#         with self.assertNoLogs(level="INFO") as cm:
#             logger.log_for(
#                 info=(f"info called", {"sentinel": False}),
#             )

