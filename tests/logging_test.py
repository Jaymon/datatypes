# -*- coding: utf-8 -*-
import time

from datatypes.compat import *
from datatypes.logging import (
    LogMixin,
)
from datatypes import logging

from . import TestCase


class LogMixinTest(TestCase):
    def test_log_for_sentinel_1(self):
        s = LogMixin()

        # https://docs.python.org/3/library/unittest.html#unittest.TestCase.assertLogs
        with self.assertNoLogs(level="INFO") as cm:
            s.log_for(
                info=(f"info called", {"sentinel": False}),
            )

    def test_log_for_sentinel_2(self):
        s = LogMixin()

        with self.assertLogs(level="INFO") as cm:
            for x in range(100):
                s.log_for(
                    debug=(f"debug {x}",),
                    info=(f"info {x}", {"sentinel": (x % 10) == 0}),
                )
            self.assertEqual(10, len(cm[0]))

        with self.assertLogs(level="DEBUG") as cm:
            for x in range(100):
                s.log_for(
                    debug=(f"debug {x}",),
                    info=(f"info {x}", {"sentinel": (x % 10) == 0}),
                )
            self.assertEqual(100, len(cm[0]))

    def test_log_for_str(self):
        s = LogMixin()

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info="info 1",
            )
            self.assertTrue("info 1" in cm[1][0])

    def test_log_for_list(self):
        s = LogMixin()

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=["info {} {}", "1", "2"],
            )
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=["info {}", "2"],
            )
            self.assertTrue("info 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=[["info {}", "2", "{}"], "1", "3"],
            )
            self.assertTrue("info 1 2 3" in cm[1][0])

    def test_log_for_tuple(self):
        s = LogMixin()

        with self.assertLogs(level="DEBUG") as cm:
            s.log_for(
                debug=(["{} - {} - {}", 1, 2, 3],),
            )
            self.assertTrue("1 - 2 - 3" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=("info {} {}", "1", "2"),
            )
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=("info 1 2",),
            )
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=(["info", "1", "2"],),
            )
            self.assertTrue("info 1 2" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            s.log_for(
                info=([["info {}", "2", "{}"], "1", "3"]),
            )
            self.assertTrue("info 1 2 3" in cm[1][0])

        with self.assertLogs(level="INFO") as cm:
            logstr = [
                "1.",
                "foo",
                "-> bar"
            ]
            s.log_for(
                info=(logstr, {"sentinel": True}),
            )
            self.assertTrue("1. foo -> bar" in cm[1][0])


class SetdefaultTest(TestCase):
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

