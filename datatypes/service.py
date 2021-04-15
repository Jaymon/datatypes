# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import subprocess
import os
import inspect
import sys

from .path import Dirpath


# 9-20-2017 -- I'm still testing these with some projects trying to get
#   the api right and so they aren't fully integrated yet
# 3-29-2018 - I've further integrated this with the testdata.start_service() and
#   testdata.stop_service() methods
# 3-24-2020 - Added Systemd support
# 8-4-2020 - moved this from testdata to datatypes (though it will also be in
#   testdata for a while, this should be considered the DRY master version), this
#   basically converts testdata.start_service() and testdata.stop_service() into
#   Service()
# 3-30-2021 - Removed testdata Service code in favor of this implementation, and 
#   made the code a little easier to follow but also a little more magical (eg, 
#   the Service class now returns other BaseService instances)


class BaseService(object):
    """base class for services"""

    sudo = True
    """If true then sudo should be added to the command"""

    ignore_failure = True
    """If True then failures when running the command will be ignored, failure is
    usually defined as an exit code >0"""

    @property
    def path(self):
        raise NotImplementedError()

    def __init__(self, name, ignore_failure=True, sudo=True):
        self.name = name
        self.ignore_failure = ignore_failure
        self.sudo = sudo

    def format_cmd(self, action, **kwargs):
        cmd = []
        if self.sudo:
            cmd.append("sudo")

        c, kw = self._format_cmd(action, **kwargs)
        cmd.extend(c)
        kwargs.update(kw)
        return cmd, kwargs

    def _format_cmd(self, action, **kwargs):
        raise NotImplementedError()

    def is_running(self):
        raise NotImplementedError()

    def start(self):
        cmd, kwargs = self.format_cmd("start")
        self.run(cmd, kwargs)

    def restart(self):
        self.stop()
        self.start()

    def stop(self):
        cmd, kwargs = self.format_cmd("stop")
        self.run(cmd, kwargs)

    def status(self):
        cmd, kwargs = self.format_cmd("status")
        return self.run(cmd, kwargs)

    def run(self, cmd, kwargs):
        try:
            ret = subprocess.check_output(cmd, **kwargs)

        except subprocess.CalledProcessError as e:
            if self.ignore_failure:
                ret = None
            else:
                raise

        return ret

    def exists(self):
        path = self.path
        return os.path.isfile(path) if path else False


class Upstart(BaseService):
    """Handle starting Upstart services"""
    @property
    def path(self):
        return "/etc/init/{}".format(self.name)

    def _format_cmd(self, action, **kwargs):
        return [action, self.name], kwargs

    def is_running(self):
        return "start/running" in self.status()


class InitD(BaseService):
    """Handle starting init.d services"""
    @property
    def path(self):
        return "/etc/init.d/{}".format(self.name)

    def _format_cmd(self, action, **kwargs):
        return [self.path, action], kwargs

    def is_running(self):
        return self.status() is None


class Systemd(BaseService):
    """Handle starting Systemd services"""
    @property
    def path(self):
        # https://unix.stackexchange.com/a/367237/118750
        ret = getattr(self, "_path", None)
        if ret is None:
            dirs = [
                "/etc/systemd/system",
                "/etc/systemd/user",
                "/usr/local/lib/systemd/system",
                "/usr/lib/systemd/system",
                "/usr/lib/systemd/user",
                "/usr/local/lib/systemd/user",
                "/run/systemd/system",
                "/run/systemd/user",
            ]

            if "XDG_CONFIG_HOME" in os.environ:
                dirs.append(os.path.join(os.environ["XDG_CONFIG_HOME"], "systemd", "user"))
            else:
                dirs.append("~/.config/systemd/user")

            if "XDG_RUNTIME_DIR" in os.environ:
                dirs.append(os.path.join(os.environ["XDG_RUNTIME_DIR"], "systemd", "user"))

            if "XDG_DATA_HOME" in os.environ:
                dirs.append(os.path.join(os.environ["XDG_DATA_HOME"], "systemd", "user"))
            else:
                dirs.append("~/.local/share/systemd/user")

            # go through all the possible locations for systemd unit files and find name
            name = self.name
            if "." not in name:
                name = "{}.".format(name)
            for path in dirs:
                d = Dirpath(path)
                if d.exists():
                    for f in d.iterfiles():
                        if f.basename.startswith(name):
                            ret = f.path
                            self._path = ret
                            break

                if ret:
                    break

        return ret

    def _format_cmd(self, action, **kwargs):
        return ["systemctl", action, self.name], kwargs

    def is_running(self):
        return "Active: active (running)" in self.status()


class Service(BaseService):
    """Catch-all to provide a common interface for any of the other services, it
    will check all the services in the order returned by .service_classes() to find
    the correct type of service and set it in .service_class so you can start/stop
    the service without worrying about the underlying service type (eg, Systemd, Upstart)

    :Example:
        s = Service("postgresql")
        s.restart()
    """
    @classmethod
    def service_classes(cls):
        """Return all the BaseService subclasses that should be checked and the
        order they should be checked in

        :returns: list, the BaseService children to check for a service, in priority
            order
        """
        service_classes = []
        for name, o in inspect.getmembers(sys.modules[__name__]):
            try:
                if issubclass(o, BaseService) and o is not BaseService and not issubclass(o, Service):
                    service_classes.append(o)

            except TypeError:
                pass

        return service_classes

    def __new__(cls, name, *args, **kwargs):
        """Magic new that will return the BaseService instance that matches name"""
        for service_class in cls.service_classes():
            s = service_class(name, *args, **kwargs)
            if s.exists():
                return s

        raise RuntimeError("Could not find a valid service for {}".format(name))

