# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import re
import os
import fnmatch
import stat
import codecs
import shutil
import hashlib
from collections import deque
from distutils import dir_util, file_util
from zipfile import ZipFile

try:
    from pathlib import Path as Pathlib
except ImportError:
    Pathlib = None

from .compat import *
from . import environ
from .string import String, ByteString


class Path(String):
    """Provides a more or less compatible interface to the pathlib.Path api of
    python 3 that can be used across py2 and py3 codebases. The biggest difference
    is the Path instances are actually string instances and are always resolved, if
    you don't want that behavior then you should use Pathlib in py3 or your own
    solution in py2

    This finally brings into a DRY location my path code from testdata and bang
    among other places I've needed this functionality. I've also tried to standardize
    the interface to be very similar to Pathlib so you can, hopefully, swap between
    them

    https://docs.python.org/3/library/pathlib.html
    https://github.com/python/cpython/blob/3.8/Lib/pathlib.py
    """
    @property
    def permissions(self):
        # https://stomp.colorado.edu/blog/blog/2010/10/22/on-python-stat-octal-and-file-system-permissions/
        mode = stat.S_IMODE(os.stat(self.path).st_mode)
        mode = oct(mode)
        return mode.replace("o", "")

    @permissions.setter
    def permissions(self, v):
        self.chmod(v)

    @property
    def pathlib(self):
        if is_py2:
            raise NotImplementedError()
        return Pathlib(self.path)

    @property
    def parts(self):
        """A tuple giving access to the path’s various components

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parts
        """
        if is_py2:
            parts = self.path.split("/")
            if not parts[0]:
                parts[0] = self.anchor

        else:
            parts = self.pathlib.parts

        return parts

    @property
    def root(self):
        """A string representing the (local or global) root, if any

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.root
        """
        if is_py2:
            ret, tail = os.path.splitdrive(self.path)
            if not ret:
                ret = "/"

        else:
            ret = self.pathlib.root

        return ret

    @property
    def anchor(self):
        """The concatenation of the drive and root

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.anchor
        """
        if is_py2:
            ret = self.root
            if ":" in ret:
                ret = "{}\\".format(ret)

        else:
            ret = self.pathlib.anchor

        return ret

    @property
    def parents(self):
        """An immutable sequence providing access to the logical ancestors of the path

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parents
        """
        if is_py2:
            parents = []
            parent = self
            while True:
                p = parent.parent
                if p != parent:
                    parents.append(p)
                    parent = p
                else:
                    break

        else:
            parents = [self.create_dir(p) for p in self.pathlib.parents]

        return parents

    @property
    def parent(self):
        """The logical parent of the path

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parent
        """
        return self.directory

    @property
    def directory(self):
        """return the directory portion of a directory/fileroot.ext path"""
        return self.create_dir(os.path.dirname(self.path))

    @property
    def name(self):
        """A string representing the final path component, excluding the drive and root

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.name
        """
        return self.basename

    @property
    def basename(self):
        """Return the fileroot.ext portion of a directory/fileroot.ext path"""
        return os.path.basename(self.path)

    @property
    def fileroot(self):
        """Return the fileroot portion of a directory/fileroot.ext path"""
        # https://stackoverflow.com/questions/2235173/
        # https://stackoverflow.com/a/2235762/5006
        fileroot, ext = os.path.splitext(self.name)
        return fileroot

    @property
    def stem(self):
        """The final path component, without its suffix

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.stem
        """
        return self.fileroot

    @property
    def suffix(self):
        """The file extension of the final component

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.suffix
        """
        fileroot, ext = os.path.splitext(self.name)
        return ext

    @property
    def ext(self):
        return self.suffix.lstrip(".")

    @property
    def extension(self):
        return self.ext

    @property
    def suffixes(self):
        """A list of the path’s file extensions

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.suffixes
        """
        if is_py2:
            suffixes = ["." + s for s in self.basename.split(".")[1:]]

        else:
            suffixes = self.pathlib.suffixes

        return suffixes

    @classmethod
    def create_file(cls, *parts, **kwargs):
        kwargs.setdefault("path_class", Filepath)
        return cls.create(*parts, **kwargs)

    @classmethod
    def create_dir(cls, *parts, **kwargs):
        kwargs.setdefault("path_class", Dirpath)
        return cls.create(*parts, **kwargs)

    @classmethod
    def create_path(cls, *parts, **kwargs):
        kwargs.setdefault("path_class", Path)
        return cls.create(*parts, **kwargs)

    @classmethod
    def create(cls, *parts, **kwargs):
        path_class = kwargs.pop("path_class", cls)
        return path_class(*parts, **kwargs)

    @classmethod
    def create_inferred(cls, *parts, **kwargs):
        if "path_class" in kwargs:
            p = cls.create(*parts, **kwargs)

        else:
            p = cls.create(*parts, **kwargs)
            if p.is_file():
                p = cls.create_file(p, **kwargs)

            elif p.is_dir():
                p = cls.create_dir(p, **kwargs)

            else:
                # let's assume a file if it has an extension
                if p.ext:
                    p = cls.create_file(p, **kwargs)

        return p

    @classmethod
    def join(cls, *parts):
        """like os.path.join but normalizes for directory separators

        Differences from the standard os.path.join:

            >>> os.path.join("/foo", "/bar/", "/che")
            '/che'

            >>> Path.join("/foo", "/bar/", "/che")
            '/foo/bar/che'
        """
        ps = []
        for p in parts:
            if isinstance(p, Path):
                p = p.path

            elif not isinstance(p, basestring) and isinstance(p, Iterable):
                p = cls.join(*p)

            else:
                if p:
                    p = String(p)

                else:
                    p = "/"

            if ps:
                ps.append(p.strip("/").strip("\\"))

            else:
                if p == "/":
                    ps.append(p)

                else:
                    ps.append(p.rstrip("/").rstrip("\\"))

        return os.path.join(*ps)

    @classmethod
    def normpath(cls, *parts, **kwargs):
        '''normalize a path, accounting for things like windows dir seps'''
        path = cls.join(*parts)
        path = os.path.abspath(os.path.expanduser(path))
        return path

    def __new__(cls, *parts, **kwargs):
        path = cls.normpath(*parts, **kwargs)
        instance = super(Path, cls).__new__(
            cls,
            path,
            encoding=kwargs.pop("encoding", environ.ENCODING),
            errors=kwargs.pop("errors", environ.ENCODING_ERRORS),
        )
        instance.path = path
        return instance

    def as_file(self, **kwargs):
        """return a new instance of this path as a Filepath"""
        return self.create_file(self, **kwargs)

    def as_dir(self, **kwargs):
        """return a new instance of this path as a Dirpath"""
        return self.create_dir(self, **kwargs)

    def as_path(self):
        """return a new instance of this path as a Path"""
        return self.create_path(self, **kwargs)

    def stat(self):
        """Return a os.stat_result object containing information about this path,
        like os.stat(). The result is looked up at each call to this method

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.stat

        :returns: os.stat_result tuple, https://docs.python.org/3/library/os.html#os.stat_result
            0: st_mode
            1: st_ino
            2: st_dev
            3: st_nlink
            4: st_uid
            5: st_gid
            6: st_size
            7: st_atime
            8: st_mtime
            9: st_ctime
        """
        if is_py2:
            ret = os.stat(self.path)

        else:
            ret = self.pathlib.stat()

        return ret

    def chmod(self, mode):
        """Change the file mode and permissions, like os.chmod()

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.chmod
        """
        if isinstance(mode, int):
            mode = "{0:04d}".format(mode)

        try:
            mode = int(mode, 8)
        except TypeError:
            pass

        return os.chmod(self.path, mode)

    def expanduser(self):
        """Return a new path with expanded ~ and ~user constructs, as returned
        by os.path.expanduser()

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.expanduser
        """
        return self

    def owner(self):
        """Return the name of the user owning the file. KeyError is raised if the file’s
        uid isn’t found in the system database.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.owner
        """
        if is_py2:
            import pwd
            return String(pwd.getpwuid(self.stat().st_uid).pw_name)

        else:
            ret = self.pathlib.owner()

        return ret

    def group(self):
        """Return the name of the group owning the file. KeyError is raised if the file’s
        gid isn’t found in the system database.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.group
        """
        if is_py2:
            import grp
            return String(grp.getgrgid(self.stat().st_gid).gr_name)

        else:
            ret = self.pathlib.group()

        return ret

    def exists(self):
        """Whether the path points to an existing file or directory

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.exists
        """
        return os.path.exists(self.path)

    def is_dir(self):
        """Return True if the path points to a directory (or a symbolic link pointing to a directory),
        False if it points to another kind of file.

        False is also returned if the path doesn’t exist or is a broken symlink;
        other errors (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_dir
        """
        return os.path.isdir(self.path)

    def isdir(self):
        return self.is_dir()

    def is_file(self):
        """Return True if the path points to a regular file (or a symbolic link pointing to a regular file),
        False if it points to another kind of file.

        False is also returned if the path doesn’t exist or is a broken symlink;
        other errors (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_file
        """
        return os.path.isfile(self.path)

    def isfile(self):
        return self.is_file()

    def is_mount(self):
        """Return True if the path is a mount point: a point in a file system where
        a different file system has been mounted. On POSIX, the function checks whether
        path’s parent, path/.., is on a different device than path, or whether path/..
        and path point to the same i-node on the same device — this should detect
        mount points for all Unix and POSIX variants. Not implemented on Windows.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_mount
        """
        return os.path.ismount(self)

    def is_symlink(self):
        """Return True if the path points to a symbolic link, False otherwise.

        False is also returned if the path doesn’t exist; other errors
        (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_symlink
        """
        return os.path.islink(self)

    def is_absolute(self):
        """Return whether the path is absolute or not. A path is considered absolute
        if it has both a root and (if the flavour allows) a drive

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_absolute
        """
        return True

    def is_reserved(self):
        """With PureWindowsPath, return True if the path is considered reserved
        under Windows, False otherwise. With PurePosixPath, False is always returned.

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_reserved
        """
        raise NotImplementedError()

    def is_root(self):
        """Return True if path is root (eg, / on Linux), False otherwise"""
        return self.name == ""

    def joinpath(self, *other):
        """Calling this method is equivalent to combining the path with each of the
        other arguments in turn

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.joinpath
        """
        if is_py2:
            ret = self.create(self.path, *other)

        else:
            ret = self.create(self.pathlib.joinpath(*other))
        return ret

    def child(self, *other):
        return self.joinpath(*other)

    def match(self, pattern):
        """Match this path against the provided glob-style pattern. Return True if
        matching is successful, False otherwise.

        If pattern is relative, the path can be either relative or absolute, and matching
        is done from the right

        If pattern is absolute, the path must be absolute, and the whole path must match

        As with other methods, case-sensitivity follows platform defaults

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.match
        """
        if is_py2:
            ret = True
            parts = list(reversed(self.parts))
            patterns = list(reversed(pattern.split("/")))

            for i, part in enumerate(parts):
                if len(patterns) <= i:
                    break

                if part == "/":
                    if patterns[i]:
                        ret = False
                        break

                elif not fnmatch.fnmatch(part, patterns[i]):
                    ret = False
                    break

        else:
            ret = self.pathlib.match(pattern)

        return ret

    def relative_to(self, *other):
        """Compute a version of this path relative to the path represented by other.
        If it’s impossible, ValueError is raised

        returns the relative part to the *other

        :Example:
            d = Path("/foo/bar/baz/che")
            d.relative_to("/foo/bar") # baz/che
            d.relative_to("/foo") # bar/baz/che

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.relative_to

        :param *other: string|Directory, the directory you want to return that self
            is a child of
        :returns: string, the part of the path that is relative, because these are
            relative paths they can't return Path instances
        """
        if is_py2:
            ancestor_dir = self.join(*other)

            ret = os.path.relpath(self.path, ancestor_dir)
            if ret.startswith(".."):
                raise ValueError("'{}' does not start with '{}'".format(self.path, ancestor_dir))

        else:
            ret = String(self.pathlib.relative_to(*other))

        return ret

    def with_name(self, name):
        """Return a new path with the name changed. If the original path doesn’t
        have a name, ValueError is raised

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.with_name
        """
        if self.is_root():
            raise ValueError("{} has an empty name".format(self))
        return self.create_inferred(self.parent, name)

    def with_suffix(self, suffix):
        """Return a new path with the suffix changed. If the original path doesn't
        have a suffix, the new suffix is appended instead. If the suffix is an empty string,
        the original suffix is removed

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.with_suffix
        """
        parent = self.parent
        fileroot = self.fileroot
        basename = fileroot

        if not suffix:
            basename = fileroot

        elif not suffix.startswith("."):
            basename += "." + suffix

        else:
            basename += suffix

        return self.create_inferred(parent, basename)

    def rename(self, target):
        """Rename this file or directory to the given target, and return a new Path
        instance pointing to target. On Unix, if target exists and is a file,
        it will be replaced silently if the user has permission. target can be
        either a string or another path object

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rename

        :returns: the new Path instance
        """
        return self.mv(target)

    def replace(self, target):
        """Rename this file or directory to the given target, and return a new Path
        instance pointing to target. If target points to an existing file or directory,
        it will be unconditionally replaced.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.replace

        :returns: the new Path instance.
        """
        return self.mv(target)

    def mv(self, target):
        raise NotImplementedError()

    def cp(self, target):
        """copy self to target"""
        raise NotImplementedError()

    def copy_to(self, target):
        return self.cp(target)

    def resolve(self, strict=False):
        """Make the path absolute, resolving any symlinks. A new path object is returned

        If the path doesn’t exist and strict is True, FileNotFoundError is raised.
        If strict is False, the path is resolved as far as possible and any remainder
        is appended without checking whether it exists. If an infinite loop is
        encountered along the resolution path, RuntimeError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve
        """
        ret = self.create_inferred(os.path.realpath(self.path))
        if strict:
            if not self.exists():
                raise OSError(self.path)

        return self

    def symlink_to(self, target, target_is_directory=False):
        """Make this path a symbolic link to target. Under Windows, target_is_directory
        must be true (default False) if the link’s target is a directory.
        Under POSIX, target_is_directory’s value is ignored

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.symlink_to
        """
        target = self.create(target)
        if is_py2:
            os.symlink(self.path, target)

        else:
            self.pathlib.symlink_to(target, target_is_directory=target_is_directory)

        return target

    def samefile(self, other_path):
        """Return whether this path points to the same file as other_path, which
        can be either a Path object, or a string. The semantics are similar to
        os.path.samefile() and os.path.samestat().

        An OSError can be raised if either file cannot be accessed for some reason.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.samefile
        """
        other_path = self.create_inferred(other_path)
        return os.path.samefile(self.path, other_path)

    def touch(self, mode=0o666, exist_ok=True):
        """Create a file at this given path. If mode is given, it is combined with
        the process’ umask value to determine the file mode and access flags.
        If the file already exists, the function succeeds if exist_ok is true
        (and its modification time is updated to the current time), otherwise
        FileExistsError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.touch
        """
        raise NotImplementedError()

    def rm(self):
        """remove file/dir, does not raise error on file/dir not existing"""
        raise NotImplementedError()

    def delete(self):
        """remove file/dir, alias of .rm(), does not raise error on file/dir not existing"""
        return self.rm()

    def remove(self):
        """remove file/dir, alias of .rm(), does not raise error on file/dir not existing"""
        return self.rm()

    def clear(self):
        """clear the file/directory but don't delete it"""
        raise NotImplementedError()

    def __fspath__(self):
        """conform to PathLike abstract base class for py3.6+

        https://docs.python.org/3/library/os.html#os.PathLike
        """
        return self.path

    def __truediv__(self, other):
        """Synctactic sugar, allows self / "bit" to work"""
        return self.joinpath(other)

    def __div__(self, other): # 2.x
        return self.__truediv__(other)


class Dirpath(Path):

    @classmethod
    def cwd(cls):
        """Return a new path object representing the current directory (as returned by os.getcwd())

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.cwd
        """
        return os.getcwd()

    @classmethod
    def home(cls):
        """Return a new path object representing the user’s home directory
        (as returned by os.path.expanduser() with ~ construct)

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.home
        """
        return os.path.expanduser("~")

    def glob(self, pattern):
        """Glob the given relative pattern in the directory represented by this path,
        yielding all matching files (of any kind)

        The “**” pattern means "this directory and all subdirectories, recursively".
        In other words, it enables recursive globbing

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob
        """

    def mkdir(self, mode=0o777, parents=False, exist_ok=False):
        """Create a new directory at this given path. If mode is given, it is combined
        with the process’ umask value to determine the file mode and access flags.
        If the path already exists, FileExistsError is raised.

        If parents is true, any missing parents of this path are created as needed;
        they are created with the default permissions without taking mode into account
        (mimicking the POSIX mkdir -p command).

        If parents is false (the default), a missing parent raises FileNotFoundError.

        If exist_ok is false (the default), FileExistsError is raised if the target directory already exists.

        If exist_ok is true, FileExistsError exceptions will be ignored
        (same behavior as the POSIX mkdir -p command), but only if the last path
        component is not an existing non-directory file.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.mkdir
        """

    def rglob(self, pattern):
        """This is like calling Path.glob() with “**/” added in front of the given relative pattern

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rglob
        """

    def rm(self):
        shutil.rmtree(self.path)

    def rmdir(self):
        """Remove this directory. The directory must be empty

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rmdir
        """

    def touch(self, mode=0o666, exist_ok=True):
        """Create the directory at this given path.  If the directory already exists,
        the function succeeds if exist_ok is true (and its modification time is
        updated to the current time), otherwise FileExistsError is raised."""
        if self.exists():
            if not exist_ok:
                raise OSError("FileExistsError")

            os.utime(self.path, None)

        else:
            dir_util.mkpath(self.path)

    def zip_to(self, target):
        target = self.create_file(target)
        if target.endswith(".zip"):
            target = os.path.splitext(target)[0]
        # https://docs.python.org/3/library/shutil.html#shutil.make_archive
        # https://stackoverflow.com/a/25650295/5006
        return shutil.make_archive(target, 'zip', self.path)

    def iterdir(self):
        """When the path points to a directory, yield path objects of the directory contents

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir
        """
        if is_py2:
            for basename in os.listdir(self.path):
                pout.v(basename)

        else:
            for p in self.pathlib.iterdir():
                pout.v(p)

    def iterdirs(self):
        """iterate through all the directories in this directory only"""
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in directories:
                yield self.create_dir(basedir, basename)
            break

    def dirs(self):
        """iterate through all the directories in this directory only"""
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in directories:
                yield self.create_dir(basedir, basename)

    def iterfiles(self):
        """iterate through all the files in this directory only"""
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in files:
                yield self.create_file(basedir, basename)
            break

    def files(self):
        """iterate through all the files in this directory and subdirectories"""
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in files:
                yield self.create_file(basedir, basename)

    def __iter__(self):
        for basedir, dirs, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for i in range(len(dirs)):
                dirs[i] = self.create_dir(basedir, dirs[i])

            for i in range(len(files)):
                files[i] = self.create_file(basedir, files[i])

            yield basedir, dirs, files


class Filepath(Path):

    def open(self, mode='r', buffering=-1, encoding=None, errors=None, newline=None):
        """Open the file pointed to by the path, like the built-in open() function does

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.open
        """
        if not mode:
            mode = "r" if encoding else "rb"

        if is_py2:
            if encoding:
                fp = codecs.open(
                    self.path,
                    mode=mode,
                    encoding=encoding,
                    errors=errors,
                    buffering=buffering,
                )

            else:
                fp = open(
                    self.path,
                    mode=mode,
                    buffering=buffering,
                )

        else:
            fp = open(
                self.path,
                mode=mode,
                encoding=encoding,
                errors=errors,
                buffering=buffering,
                newline=newline,
            )

        return fp

    def read_bytes(self):
        """Return the binary contents of the pointed-to file as a bytes object

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.read_bytes
        """
        with self.open() as fp:
            return fp.read()

    def read_text(self, encoding=None, errors=None):
        """Return the decoded contents of the pointed-to file as a string

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.read_text
        """
        encoding = encoding or self.encoding
        errors = errors or self.errors
        with self.open(encoding=encoding, errors=errors) as fp:
            return fp.read()

    def write_bytes(self, data):
        """Open the file pointed to in bytes mode, write data to it, and close the file

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.write_bytes
        """
        data = ByteString(data)
        with self.open(mode="wb+") as fp:
            return fp.write(data)

    def write_text(self, data):
        """Open the file pointed to in text mode, write data to it, and close the file

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.write_text
        """
        data = String(data, encoding=self.encoding)
        with self.open(mode="w+", encoding=self.encoding, errors=self.errors) as fp:
            return fp.write(data)

    def append_text(self, data):
        data = String(data, encoding=self.encoding)
        with self.open(mode="a+", encoding=self.encoding, errors=self.errors) as fp:
            return fp.write(data)

    def joinpath(self, *other):
        raise NotImplementedError()

    def cp(self, target):
        """copy self to/into target"""
        target = self.create_inferred(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        shutil.copy(self.path, target)
        return target

    def copy_to(self, dest_path):
        """alias of .cp()"""
        return self.cp(target)

    def mv(self, target):
        target = self.create_inferred(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        shutil.move(self.path, target)
        return target

    def unlink(self, missing_ok=False):
        """Remove this file or symbolic link. If the path points to a directory,
        use Path.rmdir() instead.

        If missing_ok is false (the default), FileNotFoundError is raised if the
        path does not exist.

        If missing_ok is true, FileNotFoundError exceptions will be ignored
        (same behavior as the POSIX rm -f command).

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.unlink
        """
        try:
            os.unlink(self.path)

        except OSError as e:
            if not missing_ok:
                raise

    def rm(self):
        return self.unlink(missing_ok=True)

    def clear(self):
        """clear the file/directory but don't delete it"""
        self.write_bytes(b"")

    def touch(self, mode=0o666, exist_ok=True):
        """Create a file at this given path. If mode is given, it is combined with
        the process’ umask value to determine the file mode and access flags.
        If the file already exists, the function succeeds if exist_ok is true
        (and its modification time is updated to the current time), otherwise
        FileExistsError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.touch
        """
        if is_py2:
            if self.exists():
                if not exist_ok:
                    raise OSError("FileExistsError")

                os.utime(self.path, None)

            else:
                self.parent.touch(mode, exist_ok)
                with self.open("a") as f:
                    os.utime(self.path, None)

        else:
            self.pathlib.touch(mode, exist_ok)

    def linecount(self):
        """return line count"""
        return len(list(self.splitlines()))

    def lc(self):
        return self.linecount()

    def count(self):
        return len(self.read_text())

    def checksum(self):
        """return md5 hash of a file"""
        h = hashlib.md5()
        blocksize = 65536
        # http://stackoverflow.com/a/21565932/5006
        with self.open(mode="rb") as fp:
            for block in iter(lambda: fp.read(blocksize), b""):
                h.update(block)
        return h.hexdigest()

    def hash(self): return self.checksum()
    def md5(self): return self.checksum()

    def head(self, count):
        """get the first count lines of self.path

        :param count: int, how many lines you want from the start of the file
        :returns: list, the lines in a similar format to .lines()
        """
        if count == 0:
            ret = self.splitlines()
        else:
            ret = [l[1] for l in enumerate(self.splitlines()) if l[0] < count]
        return ret

    def tail(self, count):
        """
        get the last count lines of self.path

        https://stackoverflow.com/a/280083/5006

        :param count: int, how many lines you want from the end of the file
        :returns: list, the lines in a similar format to .lines()
        """
        if count == 0:
            ret = self.splitlines()
        else:
            ret = deque(self.splitlines(), maxlen=count)
        return ret

    def zip_to(self, target):
        target = self.create_file(target)
        with ZipFile(target, 'w') as z:
            z.write(self.path)
        return target

    def splitlines(self, keepends=False):
        """iterate through all the lines"""
        with self.open("r", encoding=self.encoding, errors=self.errors) as f:
            for line in f:
                yield line if keepends else line.rstrip()

    def __iter__(self):
        for line in self.splitlines():
            yield line

