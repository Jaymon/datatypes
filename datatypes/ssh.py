"""
Generic SSH client

:example:
    from datatypes.ssh import SSH

    client = SSH(
        server_address=("<HOSTNAME>", <PORT>),
        username="<USERNAME>",
    )

    async with client:
        client.run(...)

This is not imported into the root namespace because this actually has a 
dependency on `asyncssh`, so it will fail to import if the dependency hasn't
been installed

Links that are handy:

    * https://asyncssh.readthedocs.io/en/stable/
    * https://github.com/ronf/asyncssh
"""
import os
from contextlib import (
    contextmanager,
    AbstractContextManager,
    asynccontextmanager,
    AbstractAsyncContextManager,
)
from collections.abc import Sequence, Generator
from typing import Self
import subprocess
import sys
import tempfile

import asyncssh

from . import logging
from .path import Dirpath
from .string import String
from .datetime import Datetime
from .url import Host


logger = logging.getLogger(__name__)


class SSHError(Exception):
    """Generic SSH error"""
    pass


class SSHProcessError(asyncssh.ProcessError, SSHError, RuntimeError):
    """Wraps the vanilla ProcessError to make it also a RuntimeError which is
    common error I used when failing processes for years. Otherwise this quacks
    just like the vanilla asyncssh.ProcessError

    https://github.com/ronf/asyncssh/blob/develop/asyncssh/process.py#L654
    """
    pass


class RemotePath(String):
    """Represents a path on the remote host"""
    @property
    def basename(self) -> str:
        """Return the fileroot.ext portion of a directory/fileroot.ext path"""
        return os.path.basename(self)

    def __new__(
        cls,
        path,
        size=0,
        user="",
        group="",
        created=None,
        updated=None
    ) -> Self:
        path = super().__new__(cls, path)
        path.size = int(size)
        path.user = user
        path.group = group
        path.created = Datetime(created) if created else None
        path.updated = Datetime(updated) if updated else None
        return path

    def is_file(self) -> bool:
        return False

    def is_dir(self) -> bool:
        return False


class RemoteFilepath(RemotePath):
    """Represents a file on the remote host"""
    def is_file(self) -> bool:
        return True


class RemoteDirpath(RemotePath):
    """Represents a dir on the remote host"""
    def is_dir(self) -> bool:
        return True


class SSH(object):
    """An SSH client

    :example:
        client = SSH(
            server_address=("<HOSTNAME>", <PORT>)
            username="<USERNAME>",
        )

        async with client:
            await client.run(...)

    This tries to have a very similar interface to the `subprocess` module.
    Notable differences:
        * When the `subprocess` functions are passed a string:
            If passing a single string, either shell must be True (see below)
            or else the string must simply name the program to be executed
            without specifying any arguments.
          But this treats sequences and strings the same regardless of any
          `shell` setting

    https://github.com/ronf/asyncssh
    https://asyncssh.readthedocs.io/en/latest/
    https://asyncssh.readthedocs.io/en/latest/api.html
    """
    connection = None
    """The SSHClient instance, this is set in .connect and .close"""

    @property
    def connection_host(self) -> str:
        """Returns the connection host

        this is mainly useful for logging

        :returns: str, the host in the form <USERNAME>@<HOSTNAME>:<PORT>
        """
        if not self.connection:
            raise ValueError("Not connected")

        return "{}@{}:{}".format(
            self.connection._username,
            self.connection._host,
            self.connection._port
        )

    @property
    def username(self) -> str:
        """Return the username"""
        if self.connection:
            return self.connection._username

        else:
            return self.connect_kwargs["username"]

    def __init__(self, **kwargs):
        """Create an instance

        :param **kwargs: merged with whatever is passed into .connect, see
            .connect for specific information about what keys can be passed
            in
        """
        self.connect_kwargs = kwargs
        self.context_kwargs = {}

    async def __aenter__(self) -> AbstractAsyncContextManager[Self]:
        """Enable `with SSH() as s:` syntax that handles connect and close
        (cleanup)"""
        await self.connect()
        return self

    async def __aexit__(self, exception_type, exception_val, trace):
        await self.close()

    async def connect(self, **kwargs):
        """Connect to the ssh server

        https://github.com/ronf/asyncssh/blob/develop/asyncssh/connection.py
        https://asyncssh.readthedocs.io/en/stable/api.html#asyncssh.connect

        :keyword username: str, the username to use
        :keyword server_address: tuple[str, int|None], the host and port
            https://docs.python.org/3/library/socketserver.html#socketserver.BaseServer.server_address
        :keyword host: str, a host string in the form of `<HOSTNAME>[:<PORT>]`,
            this is only checked if `server_address` isn't passed in
        :keyword port: int, the port, can override ports in both
            `server_address` and `host`
        :keyword identity_files: list[str], one or more paths to private keys
        :keyword config: list[str], I'm guessing this is basically an ssh
            configuration file where each line in the file would be an
            item in the list
                * https://asyncssh.readthedocs.io/en/stable/api.html#asyncssh.connect
                * https://asyncssh.readthedocs.io/en/stable/api.html#supportedclientconfigoptions
            * Here is the list of all the config keywords that can
                be passed directly into asyncssh.connect:
                    * https://asyncssh.readthedocs.io/en/stable/api.html#asyncssh.SSHClientConnectionOptions
        """
        if self.connection:
            return

        kwargs = {**self.connect_kwargs, **kwargs}

        if identity_files := kwargs.pop("identity_files", []):
            # it needs both client_keys and agent_identities to succeed when
            # passing the identity_file, I'm not sure why
            kwargs.update({
                "client_keys": identity_files,
                "agent_identities": identity_files,
            })

        kwargs.setdefault("agent_forwarding", True)
        kwargs.setdefault("known_hosts", None)

        if server_address := kwargs.pop("server_address", None):
            kwargs["host"] = server_address[0]
            if "port" not in kwargs:
                if port := server_address[1]:
                    kwargs["port"] = port

        elif host := kwargs.pop("host", ""):
            server_address = Host(host)
            kwargs["host"] = server_address[0]
            if "port" not in kwargs:
                if port := server_address[1]:
                    kwargs["port"] = port

        self.connection = await asyncssh.connect(**kwargs)

    async def close(self):
        if self.connection is not None:
            try:
                self.connection.close()
                await self.connection.wait_closed()

            except AttributeError:
                pass

            finally:
                self.connection = None

    @asynccontextmanager
    async def __call__(self, **kwargs) -> AbstractContextManager[Self]:
        """Syntactic sugar that allows fluid `async with client(...)` syntax
        to set options when the client already exists

        :example:
            client = SSH()

            # a common use case
            async with client:
                with client.options(sudo=True):
                    ...

            # that can be simplified
            async with client(sudo=True):
                ...

        https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager

        :keyword **kwargs: passed trough to `.options`
        """
        with self.options(**kwargs):
            async with self:
                yield self
        #return self.options(**kwargs)

    @contextmanager
    def options(self, **kwargs) -> AbstractContextManager[Self]:
        """Give a set of commands some context, whatever is passed into this
        context manager will be just like it was passed directly to the .run
        method

        :example:
            with client.options(sudo=True, cwd="/foo/bar"):
                await client.check_output("id -u -n") # root
                await client.check_output("pwd") # /foo/bar

        :param **kwargs: saved for the life of the context manager and used
            in .run to set the environment the command will run in
        """
        old_context_kwargs = self.context_kwargs
        self.context_kwargs = {**self.context_kwargs, **kwargs}

        try:
            yield self

        finally:
            self.context_kwargs = old_context_kwargs

    def list2cmdline(self, command) -> str:
        """Wrapper around subprocess's method of the same name

        https://github.com/python/cpython/blob/3.11/Lib/subprocess.py#L576

        :param command: str|list[str], the command as either a string or a
            list of string parts
        :returns: str
        """
        if isinstance(command, str):
            pass

        elif isinstance(command, bytes):
            command = String(command)

        else:
            command = subprocess.list2cmdline(command)

        return command

    async def runscript(
        self,
        data: str|bytes,
        path: str = "",
        mode: int|None = 0o755,
        **kwargs,
    ) -> asyncssh.SSHCompletedProcess:
        """Sometimes you want to create a script and run it

        :example:
            await client.runscript((
                "#!/usr/bin/env bash\n"
                "echo 'line 1'\n"
                "echo 'line 2'\n"
                "echo 'line 3'\n"
            ))

        :param path: if not passed in then a file will be created in the
            temp directory of the server
        """
        if not path:
            # https://superuser.com/a/332616
            tmpdir = (await self.check_output("echo $TMPDIR")).strip()
            if not tmpdir:
                tmpdir = "/tmp"
            path = os.path.join(tmpdir, next(tempfile._RandomNameSequence()))

        await self.create_file(data=data, path=path, mode=mode)
        return await self.run(path, **kwargs)

    async def run(
        self,
        command: list|str,
        **kwargs
    ) -> asyncssh.SSHCompletedProcess:
        """Run a command

        https://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SSHClientConnection.run

        All the asyncssh kwargs are here:
            https://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.SSHClientConnection.create_session

        https://github.com/ronf/asyncssh/blob/develop/asyncssh/connection.py

        To set the environment on the remote machine take a look at `env` and
        `send_env`
            https://asyncssh.readthedocs.io/en/latest/#setting-environment-variables

        :param command: the command to run on the remote machine
        :keyword sudo: bool, shortcut for `prefix="sudo"`, if prefix is passed
            in then this is a noop
        :keyword prefix: str, prepended to the command before command is run
        :keyword cwd: str, change to this directory before running command
        :keyword environ: dict[str, str], set the environment to this
        :keyword env: dict[str, str], adds to the environment
        :keyword check: bool|int|Sequence[int], if True then raise error if
            command fails. If int(s) then only raise the error if the
            return code doesn't match any of the int(s)
        :keyword passthrough: bool, passes stdout and stderr through to sys.
            This doesn't pass through stdin because at the end of the command
            asyncssh wants to close stdin and there isn't a way to not have it
            close stdin like you can with stderr and stdin
        :returns: asyncssh.SSHCompletedProcess
        :raises: SSHProcessError, if the command fails and check is True
        """
        kwargs = {**self.context_kwargs, **kwargs}

        command = self.list2cmdline(command)

        if kwargs.pop("sudo", False):
            kwargs.setdefault("prefix", "sudo")

        if prefix := kwargs.pop("prefix", ""):
            command = prefix + " " + command

        if cwd := kwargs.pop("cwd", ""):
            command = f"cd \"{cwd}\" && " + command

        # normalize environ and env keyword arguments
        if environ := kwargs.pop("environ", {}):
            kwargs["env"] = {**environ, **kwargs.get("env", {})}

        if passthrough := kwargs.pop("passthrough", False):
            kwargs.setdefault("stdout", sys.stdout)
            kwargs.setdefault("stderr", sys.stderr)
            # !!! asyncssh closes the passed in stdin when the command is done
            # so to passthrough stdin I'll need a new approach, like a buffer
            # that passes through stdin or something, this seemed like more
            # work than I wanted to do right now (2025-12), especialy since
            # I didn't need stdin support right now
            #kwargs.setdefault("stdin", sys.stdin)

            kwargs.setdefault("send_eof", False)
            kwargs.setdefault("recv_eof", False)

        expected_exit_statuses = set()
        if check := kwargs.pop("check", False):
            kwargs["check"] = True # asyncssh expects a bool

            if not isinstance(check, bool):
                if isinstance(check, int):
                    expected_exit_statuses.add(check)

                elif isinstance(check, Sequence):
                    expected_exit_statuses.update(check)

        try:
            host = self.connection_host
            logger.info(f"[{host}] Running: `{command}`")

            response = await self.connection.run(command, **kwargs)

            logger.debug(
                f"[{host}] Finished {response.exit_status}: `{command}`"
            )

        except asyncssh.ProcessError as e:
            logger.debug(
                f"[{host}] Failed {e.exit_status}:"
                f" `{command}` with stderr: {e.stderr}"
            )

            if e.exit_status in expected_exit_statuses:
                response = e

            else:
                raise SSHProcessError(
                    e.env,
                    e.command,
                    e.subsystem,
                    e.exit_status,
                    e.exit_signal,
                    e.returncode,
                    e.stdout,
                    e.stderr
                ) from e

        return response

    async def call(self, command: str|list[str], **kwargs) -> int:
        """This mimics python's subprocess.call

        https://docs.python.org/3/library/subprocess.html#subprocess.call
            Run the command ... Wait for command to complete, then return the
            returncode attribute.
        """
        r = await self.run(command, **kwargs)
        return r.exit_status

    async def check_call(self, command: str|list[str], **kwargs) -> int:
        """This mimics python's subprocess.check_call

        Run command with arguments. Wait for command to complete. If the return
        code was zero then return, otherwise raise CalledProcessError.

        https://asyncssh.readthedocs.io/en/latest/#checking-exit-status

        :param command: str, the command to run on the remote host
        :param **kwargs:
        :returns: int, the return code
        """
        kwargs.setdefault("check", True)
        r = await self.run(command, **kwargs)
        return r.exit_status

    async def check_success(self, command: str|list[str], **kwargs) -> bool:
        """Returns True if the command was successful, False if the command
        failed, because sometimes you want to run a command in an if statement

        :example:
            if not (await self.check_success("false")):
                print("command failed")

            if await self.check_success("true"):
                print("command succeeded")

            if await self.check_success("false"):
                print("this will never be printed")

        :param command: passthrough to .run
        :param **kwargs: passthrough to .run
        :returns: bool, True if the command was successful (0 exit status) or
            False if the command failed (positive or negative exit status)
        """
        try:
            r = await self.run(command, **kwargs)
            return False if r.exit_status else True

        except asyncssh.ProcessError:
            return False

    async def check_output(self, command: str|list[str], **kwargs) -> str:
        """This mimics python's subprocess.check_output with some exceptions

        By default, this will combine stdout and stderr

        Run command with arguments and return its output.

        :param command: str, the command to run on the remote host
        :keyword text: bool, True to return str instead of bytes
        :keyword encoding: str|None, the encoding to use. If this is set then
            the `text` keyword is ignored
        :keyword stderr: None|io.IOBase, by default is combined with stdout
        :returns: str
        """
        # match subprocess.check_output
        for k in ["stdout", "passthrough"]:
            if k in kwargs:
                raise ValueError(
                    f"{k} argument not allowed, it will be overridden."
                )

        #kwargs.setdefault("stdout", asyncssh.STDOUT)
        kwargs.setdefault("stderr", asyncssh.STDOUT)
        kwargs["check"] = True

        if not kwargs.pop("text", False):
            # we set encoding to None to mimic `subprocess.check_output`
            # returning bytes by default
            kwargs.setdefault("encoding", None)

        r = await self.run(command, **kwargs)
        return r.stdout

    async def upload(self, srcpath: str, destpath: str, **kwargs):
        """Upload srcpath on the local machine to destpath on the remote
        machine

        https://asyncssh.readthedocs.io/en/latest/#scp-client
        https://asyncssh.readthedocs.io/en/latest/api.html#asyncssh.scp

        :param srcpath: str|Path
        :param destpath: str
        :param **kwargs: passed directly to asyncssh.scp function
        """
        if os.path.isdir(srcpath):
            kwargs.setdefault("recurse", True)
            kwargs.setdefault("preserve", True)

        host = self.connection_host
        logger.info(f"[{host}] Uploading: {srcpath} to {destpath}")

        return await asyncssh.scp(
            srcpath,
            (self.connection, destpath),
            **kwargs
        )

    async def is_file(self, path, **kwargs) -> bool:
        """Checks if path exists and is a file on the remote host

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_file

        :param path: str|Pathlib, the file path on a remote host
        :returns: bool, True if path exists on remote machine
        """
        return await self.check_success(f"test -f \"{path}\"", **kwargs)

    async def is_dir(self, path, **kwargs) -> bool:
        """Checks if path exists and is a dir on the remote host

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_dir

        :param path: str|Pathlib, the dir path on a remote host
        :returns: bool, True if path exists on remote machine
        """
        return await self.check_success(f"test -d \"{path}\"", **kwargs)

    async def iterdir(self, path, **kwargs) -> Generator[RemotePath]:
        """Iterate the files and directories of path on the remote host

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir

        :param path: str|Pathlib, a directory path
        :returns: generator[RemotePath]
        """
        sep = kwargs.get("sep", " =|= ")
        command = (
            f"find $(realpath \"{path}\") -maxdepth 1 -print0"
            " | xargs -0"
            f" stat -c \"%n{sep}%F{sep}%s{sep}%U:%G{sep}%w{sep}%z\""
        )

        r = await self.run(command, check=True)
        for line in r.stdout.splitlines(False):
            parts = line.split(sep)
            path_class = kwargs.get("file_class", RemoteFilepath)
            if parts[1] == "directory":
                path_class = kwargs.get("dir_class", RemoteDirpath)

            user = group = ""
            if parts[3]:
                user, group = parts[3].split(":")

            yield path_class(
                parts[0],
                size=int(parts[2]),
                user=user,
                group=group,
                created=None if parts[4] == "-" else parts[4],
                updated=None if parts[5] == "-" else parts[5],
            )

    async def create_file(self,
        path: str,
        data: str|bytes|None = None,
        mode: int|None = None,
        parents: bool = False,
        exist_ok: bool = False,
        user: int|str|None = None,
        group: int|str|None = None,
        **kwargs,
    ):
        """Very similar to `.mkdir` but creates a file instead"""
        if not exist_ok:
            if await self.is_file(path, **kwargs):
                raise FileExistsError(path)

        if parents:
            await self.mkdir(os.path.dirname(path), exist_ok=True, **kwargs)

        if data:
            await self.check_call(
                ["tee", path],
                input=data,
                **kwargs,
            )

        else:
            await self.check_call(["touch", path], **kwargs)

        if mode:
            await self.chmod(path, mode, **kwargs)

        if user or group:
            await self.chown(path, user, group, **kwargs)

    async def mkdir(
        self,
        path: str,
        mode: int|None = None, # 0o777,
        parents: bool = False,
        exist_ok: bool = False,
        user: int|str|None = None,
        group: int|str|None = None,
        **kwargs,
    ):
        """
        https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir

        Changed from Path.mkdir, the `mode` defaults to None, and `user` and
        `group` can be set, they default to the connected user

        :param path: the remote directory to create
        :param mode: the permissions the directory should have
        :param parents: True if parent folders should be created
        :param exist_ok: True if the folder already existing is not an error
        :param user: the owner of the directory
        :param group: the group of the directory
        """
        if not exist_ok:
            if await self.is_dir(path):
                raise FileExistsError(path)

        mkdir_cmd = ["mkdir"]

        if parents:
            mkdir_cmd.append("-p")

        mkdir_cmd.append(path)

        try:
            await self.check_call(mkdir_cmd, **kwargs)

        except SSHProcessError as e:
            if exist_ok:
                if not (await self.is_dir(path)):
                    raise e

        if mode:
            await self.chmod(path, mode, **kwargs)

        if user or group:
            await self.chown(path, user, group, **kwargs)

    async def chmod(self, path: str, mode: int|str, **kwargs):
        """Change the permissions for the path

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.chmod


        :param path: the remote path (file/directory) to change permssions on
        :param mode: if an int, usually something like 0o777. If str then
            you can pass in "777" or "a+rwx"
        """
        if isinstance(mode, int):
            mode = f"{mode:o}"

        chmod_cmd = ["chmod", mode, path]
        await self.check_call(chmod_cmd, **kwargs)

    async def chown(
        self,
        path: str,
        user: int|str|None = None,
        group: int|str|None = None,
        **kwargs
    ):
        """Change the ownership and or the group of the path

        https://docs.python.org/3/library/os.html#os.chown
        https://docs.python.org/3/library/shutil.html#shutil.chown

        At least one of `user` or `group` should be passed in
        """
        if not user and not group:
            raise ValueError("user and/or group must be set")

        chown_cmd = ["chown"]

        perms = ""
        if user:
            perms = str(user)

        if group:
            perms += f":{group}"

        chown_cmd.extend([perms, path])
        await self.check_call(chown_cmd, **kwargs)

    async def read_bytes(self, path: str, **kwargs) -> bytes:
        """Return the contents of the remote file at `path`"""
        kwargs["text"] = False
        return await self.check_output(["cat", path], **kwargs)

    async def read_text(self, path: str, **kwargs) -> str:
        """Return the contents of the remote file at `path`"""
        kwargs["text"] = True
        return await self.check_output(["cat", path], **kwargs)

    def set_debug(self, debug: bool):
        log_level = getattr(self, "_debug_log_level", None)
        debug_level = getattr(self, "_debug_debug_level", None)

        if debug:
            if log_level is None and debug_level is None:
                self._debug_log_level = asyncssh.logger.getEffectiveLevel()
                self._debug_debug_level = asyncssh.logger._debug_level

                # https://github.com/ronf/asyncssh/blob/develop/asyncssh/logging.py
                asyncssh.set_log_level("DEBUG")
                asyncssh.set_debug_level(2)

        else:
            if log_level is not None and debug_level is not None:
                asyncssh.set_log_level(log_level)
                asyncssh.set_debug_level(debug_level)

                self._debug_log_level = None
                self._debug_debug_level = None


class InfraSSH(SSH):
    """Infrastructure SSH client that has methods helpful for DevOps

    I've broken these out from `SSH` because they aren't as generic, or
    necessarily needed in a basic base SSH client
    """
    async def has_package(self, package_name: str, **kwargs) -> bool:
        """True if `package_name` is installed, False otherwise

        This is apt and dpkg (debian based systems) specific

        https://askubuntu.com/a/1393059
        https://www.reddit.com/r/Ubuntu/comments/1agbcie/comment/kofogik/
        """
        host = self.connection_host
        kwargs["text"] = True

        try:
            output = await self.check_output(
                [
                    "dpkg-query",
                    "--show",
                    "--showformat", "'${status}'",
                    package_name,
                ],
                **kwargs,
            )

            logger.info(f"[{host}] package {package_name} is installed")

            return output.startswith("install ok") # "install ok installed"

        except SSHProcessError:
            logger.debug(f"[{host}] package {package_name} is NOT installed")
            return False

