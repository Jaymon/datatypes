# -*- coding: utf-8 -*-
import time
import re

from datatypes.compat import *
from datatypes.command import (
    Command,
    ModuleCommand,
    FileCommand,
    CalledProcessError,
    SimpleCommand,
)

from . import TestCase


class SimpleCommandTest(TestCase):
    def test_std_output(self):
        with self.assertRaises(Exception):
            c = SimpleCommand(">&2 echo foo stderr; echo bar stdout; false")
            r = c.run()


class CommandTest(TestCase):
    def test_return_code_expected(self):
        c = Command("true")
        r = c.run()
        self.assertEqual("", r)
        self.assertEqual(0, r.returncode)

        c = Command("false", returncode=1)
        r = c.run()
        self.assertEqual(1, r.returncode)

    def test_return_code_unexpected(self):
        c = Command("false")
        with self.assertRaises(CalledProcessError):
            c.run()

        c = Command("true", returncode=1)
        with self.assertRaises(CalledProcessError):
            r = c.run()

    def test_run_output_on_failure(self):
        """I had an issue where a module command was failing and printing the
        error but I was just getting the error stacktrace and not the stderr
        wasn't printing to the terminal"""
        with self.capture() as output:
            with self.assertRaises(CalledProcessError):
                c = Command(">&2 echo 'failure'; false")
                c.run()

        self.assertTrue("failure" in output)

    def test_stdout_capture(self):
        c = Command("for i in {1..10}; do echo $i; done")
        r = c.run()
        self.assertTrue("1\n" in r)
        self.assertTrue("10\n" in r)

        c = Command(">&2 echo foo", stderr=None)
        r = c.run()
        self.assertEqual("", r)

    def test_stderr_capture(self):
        c = Command("for i in {1..10}; do >&2 echo $i; done")
        r = c.run()
        self.assertTrue("1\n" in r)
        self.assertTrue("10\n" in r)

        c = Command(">&2 echo foo; echo bar", stdout=False)
        r = c.run()
        self.assertTrue("foo" in r)
        self.assertFalse("bar" in r)

    def test_environ_1(self):
        environ = {}
        contents = "some value"
        environ["TEST_RUN_ENVIRON"] = contents

        c = Command("echo $TEST_RUN_ENVIRON", environ=environ)
        r = c.run()
        self.assertEqual(contents, r.rstrip())

        c = Command("echo $TEST_RUN_ENVIRON")
        r = c.run(environ=environ)
        self.assertEqual(contents, r.rstrip())

    def test_environ_int(self):
        """https://github.com/Jaymon/testdata/issues/37"""
        c = Command("echo 1")
        c.environ["FOOINT"] = 0
        r = c.run() # if it doesn't error out then it was a success
        self.assertEqual(0, r.returncode)

    def test_run_basic(self):
        r1 = Command("echo 1").run()
        r2 = Command(["echo", "1"]).run()
        self.assertEqual(r1, r2)

    def test_create_cmd(self):
        c = Command("sleep 1")

        cmd = c.create_cmd("echo foo", "")
        self.assertEqual("echo foo", cmd)

        c.sudo = True
        cmd = c.create_cmd(["echo", "foo"], "")
        self.assertEqual("sudo", cmd[0])

    def test_async(self):
        start = time.time()

        c = Command("sleep 1.0")
        c.start()

        mid = time.time()

        r = c.wait()
        stop = time.time()

        self.assertTrue((stop - start) > 0.5)
        self.assertTrue((mid - start) < 0.5)
        self.assertEqual(0, r.returncode)

        s = "foo-bar-che"
        c = Command(f"echo {s}")
        c.start()
        r = c.wait()
        self.assertEqual(s, r.strip())

    def test_quit(self):
        start = time.time()
        c = Command("sleep 5.0")
        c.start()
        time.sleep(0.1)
        c.quit()
        c.wait()
        stop = time.time()
        self.assertTrue((stop - start) < 4.0)

    def test_kill(self):
        start = time.time()
        c = Command("sleep 5.0")
        c.start()
        time.sleep(0.1)
        c.kill()
        c.join()
        stop = time.time()
        self.assertTrue((stop - start) < 4.0)

    def test_terminate(self):
        start = time.time()
        c = Command("sleep 5.0")
        c.start()
        time.sleep(0.1)
        c.terminate()
        c.join()
        stop = time.time()
        self.assertTrue((stop - start) < 4.0)

    def test_murder(self):
        start = time.time()
        c = Command("sleep 15")
        c.start()
        c.murder(5)
        stop = time.time()
        self.assertTrue((stop - start) < 10)

    def test_wait_for(self):
        start = time.time()
        c = Command("for i in {1..10}; do echo $i; sleep 0.1; done")
        c.start()
        r = c.wait_for("2")
        stop = time.time()
        self.assertTrue("2" in r)
        self.assertTrue((stop - start) < 1)

        regex = re.compile(r"5")
        r = c.wait_for(regex)
        stop = time.time()
        self.assertTrue("5" in r)
        self.assertTrue((stop - start) < 1)

    def test_passthrough(self):
        """This test was added to check that the Command prints out as it
        runs because I was having issues a while back. Sadly, I can't
        reproduce the problem I was having but I am going to leave the test
        here for when it pops up again so I can finally fix it (2025-02-07)
        """
        fp = self.create_file("""
            for i in {1..100}; do
                echo $i
            done
        """)
        fp.chmod(755)

        c = Command(fp)
        r = c.run()
        self.assertTrue("100" in r)


class ModuleCommandTest(TestCase):
    def test_unicode_output(self):
        modpath = self.create_module(modpath="foo.__main__", data=[
            "import testdata",
            "print('foo')",
            "print(testdata.get_unicode_words().encode('utf8'))",
        ])

        c = ModuleCommand("foo", cwd=modpath.basedir)
        r = c.run()
        self.assertTrue("foo" in r)

    def test_run_module(self):
        modpath = self.create_module(modpath="foo.bar.__main__", data="print(1)")
        c = ModuleCommand("foo.bar", cwd=modpath.basedir)
        r = c.run()
        self.assertTrue("1" in r)


class FileCommandTest(TestCase):
    def test_run_file(self):
        path = self.create_file(data="print(1)")

        c = FileCommand(path)
        r = c.run()
        self.assertTrue("1" in path)

