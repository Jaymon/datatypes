# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import subprocess
from subprocess import (
    CalledProcessError,
    SubprocessError,
    TimeoutExpired,
)
import sys
import re
import signal
import time
import logging
from collections import deque
import threading

from .compat import *
from .collections import Dict
from .utils import make_list
from .decorators import property as cachedproperty
from .string import String


logger = logging.getLogger(__name__)


class CaptureProcess(subprocess.Popen):
    """
    https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    """
    def __init__(self, *args, **kwargs):

        # our default is to capture both stdout and stderr. We change the default
        # behavior a little bit in that None will be treated as /dev/null
        #
        # From the docs:
        #   If you wish to capture and combine both streams into one,
        #   use stdout=PIPE and stderr=STDOUT
        #
        #   Valid values are PIPE, DEVNULL, an existing file descriptor (a
        #   positive integer), an existing file object with a valid file
        #   descriptor, and None. PIPE indicates that a new pipe to the child
        #   should be created. DEVNULL indicates that the special file os.devnull
        #   will be used. 
        #
        #   Additionally, stderr can be STDOUT, which indicates that the stderr
        #   data from the child process should be captured into the same file
        #   handle as for stdout.
        kwargs.setdefault("stderr", subprocess.STDOUT)
        kwargs.setdefault("stdout", subprocess.PIPE)
        self.pipe_name = "stdout"

        if kwargs["stderr"] and not kwargs["stdout"]:
            kwargs["stderr"] = subprocess.PIPE
            self.pipe_name = "stderr"

        elif kwargs["stderr"] and kwargs["stdout"]:
            kwargs["stderr"] = subprocess.STDOUT

        if not kwargs["stderr"]:
            kwargs["stderr"] = subprocess.DEVNULL

        if not kwargs["stdout"]:
            kwargs["stdout"] = subprocess.DEVNULL

        # https://docs.python.org/3/library/collections.html#collections.deque
        #   Deques support thread-safe, memory efficient appends and pops
        self.deque = deque(maxlen=kwargs.pop("bufsize", 1000))
        self.returncodes = kwargs.pop("returncodes", [0])
        self.returncode = None
        super().__init__(*args, **kwargs)

    def __iter__(self):
        output = getattr(self, self.pipe_name)
        try:
            # another round of links
            # http://stackoverflow.com/a/17413045/5006 (what I used)
            # http://stackoverflow.com/questions/2715847/
            #for line in iter(self.stdout.readline, b""):
            for line in iter(output.readline, b""):
                line = line.decode("utf-8")
                self.deque.append(line)
                yield line

        finally:
            output.close()

    def is_running(self):
        return self.poll() is None

    def check_returncode(self, returncodes=None):
        """
        https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.check_returncode
        """
        if not returncodes:
            returncodes = self.returncodes
        returncodes = set(make_list(returncodes))

        if self.returncode is not None:
            if self.returncode not in returncodes:
                raise CalledProcessError(
                    self.returncode,
                    self.args,
                    "".join(self.deque),
                )

#                 raise CalledProcessError(
#                     "{} returned {}, expected one of {}".format(
#                         self.args,
#                         self.returncode,
#                         returncodes,
#                     ),
#                     self.args,
#                 )


class Command(object):
    """makes running a command from a non CLI environment easy peasy

    This is handy when you need to test some CLI functionality of your python
    modules.

    https://docs.python.org/3/library/subprocess.html

    Moved here from testdata.client.Command on 7-9-2023

    :Example:
        c = Command("echo")
        r = c.run("hello")
        print(r) # hello
    """
    quiet = False
    """this is the default quiet setting for running a script, it can
    be overriden in run()"""

    process_class = CaptureProcess
    """The class that will be used in .create_process, needs to be a subclass
    of Popen, honestly, it will have to be a subclass of CaptureProcess since
    it relies on the deque property and check_returncode method

    https://docs.python.org/3/library/subprocess.html#subprocess.Popen
    """
    @cachedproperty(cached="_environ")
    def environ(self):
        environ = dict(os.environ)
        pythonpath = self.cwd
        if "PYTHONPATH" in environ:
            environ["PYTHONPATH"] += os.pathsep + pythonpath
        else:
            environ["PYTHONPATH"] = pythonpath

        if os.getcwd() not in environ["PYTHONPATH"]:
            environ["PYTHONPATH"] += os.pathsep + os.getcwd()

        return environ

    def __init__(self, command, cwd="", environ=None, **kwargs):
        self.cwd = os.path.realpath(cwd) if cwd else os.getcwd()
        self.command = command

        self.logger_prefix = kwargs.pop("logger_prefix", None)
        self.logger = self.get_logger(**kwargs)

        self.sudo = kwargs.pop("sudo", False)

        if environ is not None:
            self.environ = environ

        self.kwargs = kwargs

    def _flush(self, process, line):
        """flush the line to stdout"""
        if not process.quiet:
            if self.logger_prefix is None:
                self.logger_prefix = "{:0>5}: ".format(process.pid)
            self.logger.info("{}{}".format(self.logger_prefix, line.rstrip()))

    def get_logger(self, **kwargs):
        logger = logging.getLogger(f"{__name__}.Command")
        if len(logger.handlers) == 0:
            logger.setLevel(logging.INFO)
            log_handler = logging.StreamHandler(stream=sys.stdout)
            log_handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(log_handler)
            logger.propagate = False
        return logger

    def create_cmd(self, command, arg_str):
        if command:
            if isinstance(command, basestring):
                cmd = command
                if arg_str:
                    if isinstance(arg_str, basestring):
                        cmd += " " + arg_str
                    else:
                        cmd += " ".join(arg_str)

            else:
                cmd = list(command)
                if arg_str:
                    if isinstance(arg_str, basestring):
                        cmd.append(arg_str)
                    else:
                        cmd.extend(arg_str)

        else:
            cmd = arg_str

        if self.sudo:
            if isinstance(cmd, basestring):
                if not cmd.startswith("sudo"):
                    cmd = "sudo " + cmd

            else:
                if not cmd[0] == "sudo":
                    cmd.insert(0, "sudo")

        return cmd

    def create_process(self, arg_str, **kwargs):
        """
        https://docs.python.org/3/library/subprocess.html
        """
        process = None
        cmd = self.create_cmd(self.command, arg_str)

        kwargs = Dict(self.kwargs, kwargs)
        quiet = kwargs.pop("quiet", self.quiet)

        retcode = kwargs.pops([
            "returncodes",
            "returncode",
            "code",
            "ret_code",
            "retcode",
            "expected_ret_code",
            "expected_returncode",
            "codes",
            "ret_codes",
            "retcodes",
            "expected_ret_codes",
            "expected_returncodes",
        ], 0)
        kwargs["returncodes"] = retcode

        environ = self.environ
        environ.update(kwargs.pop("environ", {}))
        environ.update(kwargs.pop("env", {}))
        # any kwargs with all capital letters should be considered environment
        # variables
        for k in list(kwargs.keys()):
            if k.isupper():
                environ[k] = kwargs.pop(k)

        # make sure each value is a string
        for k in environ.keys():
            if not isinstance(environ[k], basestring):
                environ[k] = String(environ[k])

        # we will not allow these to be overridden via kwargs
        kwargs["shell"] = isinstance(cmd, basestring)
        kwargs["cwd"] = self.cwd
        kwargs["env"] = environ

        try:
            process = self.process_class(
                cmd,
                **kwargs
            )

        except CalledProcessError as e:
            process.returncode = e.returncode

        finally:
            if process:
                process.quiet = quiet

        return process

    def run(self, arg_str="", **kwargs):
        """runs the passed in arguments

        :param arg_str: string, the argument flags that will be passed to the command
        :param **kwargs: These will be passed to subprocess or consumed
        :returns: string, the string of the output and will have .returncode attribute
        """
        process = self.create_process(arg_str, **kwargs)

        # consume all the output from the process
        for line in process:
            self._flush(process, line)

        process.wait()
        process.check_returncode()

        # we wrap the output in a String so we can set returncode
        ret = String("".join(process.deque))
        ret.returncode = process.returncode
        return ret


class AsyncCommand(Command):
    thread_class = threading.Thread
    """the threading class to use when .run is called

    Could I switch to using ThreadPoolExecutor instead?
    https://docs.python.org/3/library/concurrent.futures.html

    :Example:
        c = AsyncCommand("<SOME COMMAND>")
        c.run()
        while r := c.wait(1):
            if "<SOME SENTINAL STRING>" in r:
                break
    """
    def is_running(self):
        """True if the process is running"""
        return self.process.poll() is None

    def quit(self, timeout=1):
        """same as .terminate but uses signals"""
        return self.finish("send_signal", timeout=timeout, args=(signal.SIGTERM,))

    def kill(self, timeout=1):
        """kill -9 the script running asyncronously"""
        return self.finish("kill", timeout=timeout)

    def terminate(self, timeout=1):
        """terminate the script running asyncronously"""
        return self.finish("terminate", timeout=timeout)

    def murder(self, timeout=1):
        """use pkill to kill any process that matches self.process.args"""
        process_cmd = self.process.args
        cmd = self.create_cmd(["pkill", "-f", process_cmd], "")
        logger.debug("Murdering {}".format(process_cmd))
        subprocess.run(cmd, check=False)
        return self.wait(timeout)

    def finish(self, method_name, timeout=1, maxcount=5, args=None, kwargs=None):
        """Internal method that kills the async process, if it can't shut it down
        soft it will shut it down hard

        :param method_name: str, the method name that will first be attempted
        :param timeout: int, how long to wait for each attempted method_name call
        :param maxcount: int, how many times to attempt calling method_name
        :param *args: passed to method_name call
        :param **kwargs: passed to method_name call
        :returns: str, the buffer
        """
        ret = []

        args = args or ()
        kwargs = kwargs or {}
        process = self.process

        while self.is_running():
            getattr(process, method_name)(*args, **kwargs)
            ret.append(self.wait(timeout=timeout))
            if process.returncode is None:
                count += 1
                if count >= maxcount:
                    ret.append(self.murder())

        return "".join(ret)

    def start(self, *args, **kwargs): return self.run(*args, **kwargs)
    def run(self, arg_str="", **kwargs):
        """Run the command asyncronously, see parent's .run"""
        self.process = self.create_process(arg_str, **kwargs)

        def target():
            for line in self.process:
                self._flush(self.process, line)

        t = self.thread_class(target=target)
        t.daemon = True
        t.start()
        self.async_thread = t
        return self.process

    def join(self, *args, **kwargs): return self.wait(*args, **kwargs)
    def wait(self, timeout=None):
        """After .run is called you can call this to return current output from
        when .run was called or when this method was last called

        :param timeout: int, how long to wait
        :returns: str, the output, the str also has a returncode value, which
            will be None if the process isn't done yet
        """
        try:
            self.process.wait(timeout=timeout)

        except subprocess.TimeoutExpired:
            pass

        retcode = self.process.returncode
        if retcode is not None and retcode > 0:
            self.process.check_returncode()

        ret = "".join(self.process.deque)
        self.process.deque.clear()

        ret = String(ret)
        ret.returncode = retcode

        return ret

    def wait_for(self, callback, timeout=0.1, maxcount=10):
        """Wait until callback returns True or until maxcount * timeout is hit

        :param callback: callable|str|re.Pattern, if a callable, then pass the
            program output to callable until it returns True. If a string then
            check string in output. If regex pattern then run search on output
        :param timeout: float, each incremental timeout before next check
        :param maxcount: int, the maximum times to check callback before failing
            and just returning output
        :returns str, the output, same as .wait()
        """
        if not callable(callback):
            if isinstance(callback, str):
                needle = callback
                callback = lambda haystack: needle in haystack

            elif isinstance(callback, re.Pattern):
                regex = callback
                callback = lambda haystack: regex.search(haystack)

            else:
                raise ValueError(f"Not sure what to do with {callback}")

        haystack = String("")
        haystack.returncode = None

        count = 0
        while count < maxcount:
            count += 1

            hay = self.wait(timeout=timeout)
            haystack = String(haystack + hay)
            haystack.returncode = hay.returncode

            if callback(haystack):
                break

            if haystack.returncode is not None:
                break

        return haystack

