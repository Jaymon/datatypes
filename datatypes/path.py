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
#from zipfile import ZipFile
import zipfile
import tarfile
import site
import logging
import tempfile
import itertools
import glob
import datetime
import re
import string
import random

try:
    from pathlib import Path as Pathlib
except ImportError:
    Pathlib = None

try:
    import cPickle as pickle
except ImportError:
    import pickle

from .compat import *
from . import environ
from .string import String, ByteString


logger = logging.getLogger(__name__)


class Path(String):
    """Provides a more or less compatible interface to the pathlib.Path api of
    python 3 that can be used across py2 and py3 codebases. However, The Path
    instances are actually string instances and are always resolved

    This finally brings into a DRY location my path code from testdata, stockton,
    and bang, among others. I've needed this functionality. I've also tried to standardize
    the interface to be very similar to Pathlib so you can, hopefully, swap between
    them

    Directories: 
        * path: /parent/basename
        * fileroot: basename
        * basename: basename
        * filename: basename
        * directory: /parent
        * parent: /parent
        * stempath: /parent/basename
        * ext: ""
        * suffix: ""

    Files: 
        * path: /parent/fileroot.ext
        * fileroot: fileroot
        * filename: fileroot.ext
        * basename: fileroot.ext
        * directory: /parent
        * parent: /parent
        * stempath: /parent/fileroot
        * ext: ext
        * suffix: .ext

    https://en.wikipedia.org/wiki/Fully_qualified_name#Filenames_and_paths
    https://docs.python.org/3/library/pathlib.html
    https://github.com/python/cpython/blob/3.8/Lib/pathlib.py
    https://docs.python.org/3/library/os.path.html

    Path takes advantage of these semi-standard python modules:
        * https://docs.python.org/3/library/shutil.html
        * https://github.com/python/cpython/blob/2.7/Lib/distutils/dir_util.py)
        * https://github.com/python/cpython/blob/2.7/Lib/distutils/file_util.py
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
        return self.create_dir(os.path.dirname(self.path))

    @property
    def directory(self):
        """return the directory portion of a directory/fileroot.ext path"""
        return self.parent

    @property
    def dirname(self):
        return self.parent

    @property
    def basedir(self):
        return self.parent

    @property
    def name(self):
        """A string representing the final path component, excluding the drive and root

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.name
        """
        return self.basename

    @property
    def filename(self):
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
    def stempath(self):
        """The complete path, without its suffix

        :Example:
            p = Path("/foo/bar/fileroot.ext")
            p.stempath # /foo/bar/fileroot

        :returns: String, the full path and fileroot without suffix (ext)
        """
        return os.path.splitext(self.path)[0]

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
    def path_class(self):
        return Path

    @classmethod
    def dir_class(self):
        return Dirpath

    @classmethod
    def file_class(self):
        return Filepath

    @classmethod
    def create_file(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.file_class()
        return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create_dir(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.dir_class()
        return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create_path(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.path_class()
        return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create(cls, *parts, **kwargs):
        """Create a path instance using the full inferrencing (guessing code) of
        cls.path_class().__new__()"""
        # we want inference to work so we don't want any path_class being passed
        # to the __new__ method but we will use it to create the instance if
        # passed in
        path_class = kwargs.pop("path_class", cls.path_class())
        return path_class(*parts, **kwargs)

    @classmethod
    def create_as(cls, instance, path_class, **kwargs):
        """Used by .__new__() to convert a Path to one of the children. This is 
        a separate method so it could be augmented by children classes if desired

        take note that this has a different signature than all the other create_*
        methods

        :param instance: Path, a Path instance created by __new__()
        :param path_class: type, the path class that was passed in to __new__()
        :param **kwargs: the keywords passed into __new__()
        :returns: Path, either the same instance or a different one
        """
        if path_class or (cls is not cls.path_class()):
            return instance

        if instance.is_file():
            instance = instance.as_file()

        elif instance.is_dir():
            instance = instance.as_dir()

        else:
            # let's assume a file if it has an extension
            if instance.ext:
                instance = instance.as_file()

        return instance

    @classmethod
    def split(cls, *parts):
        """Does the opposite of .join()"""
        ps = []
        for p in parts:
            if isinstance(p, Path):
                for pb in p.parts:
                    if pb == "/":
                        if not ps:
                            ps.append(pb)

                    else:
                        ps.append(pb)

            elif not isinstance(p, basestring) and isinstance(p, Iterable):
                for pb in cls.split(*p):
                    if pb == "/":
                        if not ps:
                            ps.append(pb)

                    else:
                        ps.append(pb)

            else:
                for pb in String(p).split("/"):
                    if pb:
                        ps.append(pb.rstrip("\\/"))

                    else:
                        if not ps:
                            ps.append("/")

        return ps

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
                ps.append(p.strip("\\/"))

            else:
                if p == "/":
                    ps.append(p)

                else:
                    ps.append(p.rstrip("\\/"))

        return os.path.join(*ps)

    @classmethod
    def normpath(cls, *parts, **kwargs):
        '''normalize a path, accounting for things like windows dir seps'''
        path = cls.join(*parts)
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(path)))

        suffix = kwargs.pop("suffix", kwargs.pop("ext", ""))
        if suffix:
            if not path.endswith(suffix):
                path = "{}.{}".format(path, suffix.lstrip("."))

        return path

    def __new__(cls, *parts, **kwargs):
        path = cls.normpath(*parts, **kwargs)
        path_class = kwargs.pop("path_class", None)

        instance = super(Path, cls).__new__(
            path_class if path_class else cls,
            path,
            encoding=kwargs.pop("encoding", environ.ENCODING),
            errors=kwargs.pop("errors", environ.ENCODING_ERRORS),
        )
        instance.path = path

        instance = cls.create_as(instance, path_class, **kwargs)
        return instance

    def as_class(self, **kwargs):
        kwargs.setdefault("encoding", self.encoding)
        kwargs.setdefault("errors", self.errors)
        return kwargs["path_class"](self.path, **kwargs)

    def as_file(self, **kwargs):
        """return a new instance of this path as a Filepath"""
        kwargs["path_class"] = self.file_class()
        return self.as_class(**kwargs)
        #return self.create_file(self.path, **kwargs)

    def as_dir(self, **kwargs):
        """return a new instance of this path as a Dirpath"""
        kwargs["path_class"] = self.dir_class()
        return self.as_class(**kwargs)
        #return self.create_dir(self.path, **kwargs)

    def as_path(self):
        """return a new instance of this path as a Path"""
        kwargs["path_class"] = self.path_class()
        return self.as_class(**kwargs)
        #return self.create_path(self.path, **kwargs)

    def as_uri(self):
        """Represent the path as a file URI

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.as_uri
        """
        return "file://{}".format(self.path)

    def empty(self):
        """Return True if the file/directory is empty"""
        raise NotImplementedError()

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

    def with_name(self, name):
        """Return a new path with the name changed. If the original path doesn’t
        have a name, ValueError is raised

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.with_name
        """
        if self.is_root():
            raise ValueError("{} has an empty name".format(self))
        return self.create(self.parent, name)

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

        return self.create(parent, basename)

    def backup(self, suffix=".bak", ignore_existing=True):
        """backup the file to the same directory with given suffix

        :param suffix: str, what will be appended to the file name (eg, foo.ext becomes
            foo.ext.bak)
        :param ignore_existing: boolean, if True overwrite an existing backup, if false
            then don't backup if a backup file already exists
        :returns: instance, the backup Path
        """
        target = self.create("{}{}".format(self.path, suffix))
        return self.backup_to(target)

    def backup_to(self, target, ignore_existing=True):
        target = self.create(target)
        if ignore_existing or not target.exists():
            self.cp(target)
        return target

    def rename(self, target):
        """Rename this file or directory to the given target, and return a new Path
        instance pointing to target. On Unix, if target exists and is a file,
        it will be replaced silently if the user has permission. target can be
        either a string or another path object

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rename

        :returns: the new Path instance
        """
        target = self.create_path(target)
        os.rename(self.path, target)
        return self.create(target)

    def replace(self, target):
        """Rename this file or directory to the given target, and return a new Path
        instance pointing to target. If target points to an existing file or directory,
        it will be unconditionally replaced.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.replace

        :returns: the new Path instance.
        """
        if is_py2:
            ret = self.rename(target)

        else:
            target = self.create_path(target)
            self.pathlib.replace(target)
            ret = self.create(target)

        return ret

    def mv(self, target):
        """mimics the behavior of unix mv command"""
        raise NotImplementedError()

    def move_to(self, target):
        return self.mv(target)

    def cp(self, target):
        """mimics the behavior of unix cp command"""
        raise NotImplementedError()

    def copy_to(self, target):
        return self.cp(target)

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

    def archive_to(self, target):
        raise NotImplementedError("Waiting for Archivepath api to be finalized")

    def resolve(self, strict=False):
        """Make the path absolute, resolving any symlinks. A new path object is returned

        If the path doesn’t exist and strict is True, FileNotFoundError is raised.
        If strict is False, the path is resolved as far as possible and any remainder
        is appended without checking whether it exists. If an infinite loop is
        encountered along the resolution path, RuntimeError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve
        """
        ret = self.create(os.path.realpath(self.path))
        if strict:
            if not ret.exists():
                raise OSError(self.path)

        return ret

    def samefile(self, other_path):
        """Return whether this path points to the same file as other_path, which
        can be either a Path object, or a string. The semantics are similar to
        os.path.samefile() and os.path.samestat().

        An OSError can be raised if either file cannot be accessed for some reason.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.samefile
        """
        other_path = self.create(other_path)
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

    def created(self):
        """return a datetime.datetime of when the file was created"""
        t = os.path.getctime(self.path)
        return datetime.datetime.fromtimestamp(t)

    def modified(self):
        """return a datetime.datetime of when the file was modified"""
        # http://stackoverflow.com/a/1526089/5006
        t = os.path.getmtime(self.path)
        return datetime.datetime.fromtimestamp(t)

    def updated(self):
        return self.modified()

    def accessed(self):
        """return a datetime.datetime of when the file was accessed"""
        t = os.path.getatime(self.path)
        return datetime.datetime.fromtimestamp(t)

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
    """Represents a directory so extends Path with methods to iterate through
    a directory"""
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

    def empty(self):
        """Return True if directory is empty"""
        ret = True
        for p in self.iterdir():
            ret = False
            break
        return ret

    def rm(self):
        try:
            shutil.rmtree(self.path)

        except OSError:
            # we don't care if the directory doesn't exist
            pass

    def rmdir(self):
        """Remove this directory. The directory must be empty

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rmdir
        """
        os.rmdir(self.path)

    def clear(self):
        """Remove all the contents of this directory but leave the directory"""
        for p in self.iterdir():
            p.rm()

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
        if not exist_ok:
            if self.is_dir():
                raise OSError("FileExistsError")

        if parents:
            os.makedirs(self.path, mode)

        else:
            os.mkdir(self.path, mode)

    def mv(self, target):
        """Move the entire contents of the directory at self into a directory at target

        :Example:
            $ mv src target
            target/src if target exists
            error is thrown if target/src exists and target/src is not empty
                (mv: rename src to target/src: Directory not empty)
            src is moved to target/src if target/src exists but is empty
            src is moved to target if target does not exist
        """
        target = self.create_dir(target)

        if target.is_dir():
            # https://stackoverflow.com/a/15034373/5006
            target = self.create_dir(target, self.basename)

            if target.is_dir() and not target.empty():
                # this will error out if target is not empty
                raise OSError("Directory not empty: {}".format(target))

        # dir_util says it creates all the parent directories but for some
        # reason it wasn't working, this makes sure the target exist before
        # trying to copy everything over from src (self.path)
        target.touch()
        dir_util.copy_tree(self.path, target, update=1)

        self.rm()

        return target

    def cp(self, target):
        """Copy the entire contents of the directory at self into a directory at target

        :Example:
            $ cp -R src target
            src is copied to target if target does not exist
            target/src if target exists
            src is merged into target/src if target/src exists
        """
        target = self.create_dir(target)

        if target.is_dir():
            target = self.create_dir(target, self.basename)

        target.touch()
        dir_util.copy_tree(self.path, target, update=1)

        return target

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

    def glob(self, pattern):
        """Glob the given relative pattern in the directory represented by this path,
        yielding all matching files (of any kind)

        The “**” pattern means "this directory and all subdirectories, recursively".
        In other words, it enables recursive globbing

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob
        """
        if is_py2:
            # https://docs.python.org/2/library/glob.html
            for fp in glob.iglob(os.path.join(self.path, pattern)):
                yield self.create(fp)

        else:
            for fp in self.pathlib.glob(pattern):
                yield self.create(fp)

    def rglob(self, pattern):
        """This is like calling Path.glob() with “**/” added in front of the given
        relative pattern, meaning it will match files in this directory and all
        subdirectories

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rglob
        """
        if is_py2:
            for fp in self.glob(pattern):
                yield fp

            for dp in self.iterdirs(recursive=True):
                for fp in glob.iglob(os.path.join(dp, pattern)):
                    yield self.create(fp)

        else:
            for fp in self.pathlib.rglob(pattern):
                yield self.create(fp)

    def reglob(self, pattern, recursive=True):
        """A glob but uses a regex instead of the common glob syntax"""
        for fp in self.iterfiles(recursive=recursive):
            if re.search(pattern, fp):
                yield fp

    def filecount(self, recursive=True):
        """return how many files in directory"""
        return len(list(self.iterfiles(recursive=recursive)))

    def dircount(self, recursive=True):
        """return how many directories in directory"""
        return len(list(self.iterdirs(recursive=recursive)))

    def count(self, recursive=True):
        """return how many files and directories in directory"""
        return self.filecount(recursive=recursive) + self.dircount(recursive=recursive)

    def scandir(self):
        """
        https://docs.python.org/3.5/library/os.html#os.scandir

        https://github.com/benhoyt/scandir
        https://bugs.python.org/issue11406
        """
        # TODO -- make this work similarly for py2
        for entry in os.scandir(self.path):
            yield entry

    def iterdir(self):
        """When the path points to a directory, yield path objects of the directory contents

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir
        """
        if is_py2:
            for basename in os.listdir(self.path):
                yield self.create(self.path, basename)

        else:
            for p in self.pathlib.iterdir():
                yield self.create(p)

    def iterdirs(self, recursive=True):
        """iterate through all the directories similar to .iterdir() but only
        returns directories

        :param recursive: boolean, if True then iterate through directories in
            self and 
        """
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in directories:
                yield self.create_dir(basedir, basename)

            if not recursive:
                break

    def iterfiles(self, recursive=True):
        """iterate through all the files in this directory only"""
        """iterate through all the files in this directory and subdirectories"""
        for basedir, directories, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for basename in files:
                yield self.create_file(basedir, basename)

            if not recursive:
                break

    def __iter__(self):
        for basedir, dirs, files in os.walk(self.path, topdown=True):
            basedir = self.create_dir(basedir)
            for i in range(len(dirs)):
                dirs[i] = self.create_dir(basedir, dirs[i])

            for i in range(len(files)):
                files[i] = self.create_file(basedir, files[i])

            yield basedir, dirs, files


class Filepath(Path):
    """Represents a file so extends Path with file reading/writing methods"""
    def empty(self):
        """Return True if file is empty"""
        ret = True
        if self.exists():
            st = self.stat()
            ret = False if st.st_size else True
        return ret

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

    def __call__(self, mode="w+", **kwargs):
        """Allow an easier interface for opening a writing file descriptor

        This uses the class defaults for things like encoding, so it's better to
        use .open() or .write_bytes() if you want to write non-encoded raw text

        :Example:
            p = Filepath("foo/bar.ext")
            with p("a+) as fp:
                fp.write("some value")
        """
        return self.open(
            mode=mode,
            buffering=kwargs.get("buffering", -1),
            newline=kwargs.get("newline", None),
            encoding=kwargs.get("encoding", self.encoding),
            errors=kwargs.get("errors", self.errors),
        )

    def __enter__(self):
        """Allow an easier interface for opening a writing file descriptor

        :Example:
            p = Filepath("foo/bar.ext")
            with p as fp:
                fp.write("some value")
        """
        self._context_fp = self()
        return self._context_fp

    def __exit__(self, exception_type, exception_val, trace):
        self._context_fp.close()
        del self._context_fp

    def read_bytes(self):
        """Return the binary contents of the pointed-to file as a bytes object

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.read_bytes
        """
        # https://stackoverflow.com/a/32957860/5006
        with self.open(mode="rb") as fp:
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
        target = self.create(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        shutil.copy(self.path, target)
        return target.as_file()

    def mv(self, target):
        target = self.create(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        shutil.move(self.path, target)
        return target.as_file()

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
        if self.exists():
            if not exist_ok:
                raise OSError("FileExistsError")

            os.utime(self.path, None)

        else:
            self.parent.touch(mode, exist_ok)

            # http://stackoverflow.com/a/1160227/5006
            with self.open("a") as f:
                os.utime(self.path, None)

    def linecount(self):
        """return line count"""
        return len(list(self.splitlines()))

    def lc(self):
        return self.linecount()

    def count(self):
        """how many characters in the file"""
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

    def splitlines(self, keepends=False):
        """iterate through all the lines"""
        with self.open("r", encoding=self.encoding, errors=self.errors) as f:
            for line in f:
                yield line if keepends else line.rstrip()

    def __iter__(self):
        for line in self.splitlines():
            yield line


class Archivepath(Dirpath):
    """This was based off of code from herd.path but as I was expanding it I realized
    it was going to be more work than my needs currently warranted so I'm leaving
    this here and I'll get back to it another time


    https://docs.python.org/3/library/tarfile.html 
    https://docs.python.org/2/library/tarfile.html#tarfile-objects

    https://docs.python.org/3/library/zipfile.html
    https://docs.python.org/2/library/zipfile.html#zipfile-objects
    """
    def __new__(cls, *parts, **kwargs):
        instance = super(Archivepath, cls).__new__(cls, *parts, **kwargs)

        archive_info = {
            ".zip": {
                "archive_class": zipfile.ZipFile,
                "archive_format": "zip",
                "write_mode": "w",
                "write_method": "write",
                "__iter__": "namelist",
            },
            ".tar": {
                "archive_class": tarfile.TarFile,
                "archive_format": "tar",
                "write_mode": "w:",
                "write_method": "add"
            },
            ".tar.gz": {
                "archive_class": tarfile.TarFile,
                "archive_format": "gztar",
                "write_mode": "w:gz",
                "write_method": "add"
            },
            ".tar.bz2": {
                "archive_class": tarfile.TarFile,
                "archive_format": "bztar",
                "write_mode": "w:bz2",
                "write_method": "add"
            },
            ".tar.xz": {
                "archive_class": tarfile.TarFile,
                "archive_format": "xztar",
                "write_mode": "w:xz",
                "write_method": "add"
            },
        }

        instance.info = {}
        for suffix, info in archive_info.items():
            if instance.endswith(suffix):
                instance.info = info
                break

        if not instance.info:
            raise ValueError("No archive info found for archive file {}".format(instance.path))

        return instance

    def __iter__(self):
        z = self.info["archive_class"](self.path)
        for n in getattr(z, self.info["__iter__"])():
            yield n

    def add(self, target, arcname=""):
        target = self.create(target)

        # !!! This works but it overwrites the zip file on every call, a
        # solution would be to make this a context manager so you could do
        # something like:
        #
        # with self as z:
        #     z.add(path1)
        #     z.add(path2)
        #     z.add(path3)
        #
        # so each .add copies the files/directories to a temp directory and when the __exit__
        # fires you would use shutil.make_archive to create the actual archive
        # file, this method would then be renamed .set()


        # if the archive doesn't exist we want to make sure at least the directory
        # exists because the file will be created when target is added to the
        # archive
        if not self.exists():
            self.parent.touch()

        if target.is_file():
            if not arcname:
                arcname = target.basename

            with self.info["archive_class"](self.path, mode=self.info["write_mode"]) as z:
                getattr(z, self.info["write_method"])(target, arcname=arcname)

        elif target.is_dir():
            if not arcname:
                arcname = target.path

            target = self.stempath
            # https://docs.python.org/3/library/shutil.html#shutil.make_archive
            # https://stackoverflow.com/a/25650295/5006
            shutil.make_archive(self.stempath, self.info["archive_format"], root_dir=arcname)

        else:
            raise ValueError("Target is neither a file or a directory")

    def extract_to(self, target):
        target = self.create_dir(target)


# !!! Ripped from herd.path
class TempDirpath(Dirpath):
    """Create a temporary directory

    https://docs.python.org/3/library/tempfile.html

    :Example:
        d = TempDirpath("foo", "bar")
        print(d) # $TMPDIR/foo/bar
    """

    def __new__(cls, *parts, **kwargs):

        # https://docs.python.org/3/library/tempfile.html#tempfile.mkdtemp
        path = tempfile.mkdtemp(
            suffix=kwargs.pop("suffix", ""),
            prefix=kwargs.pop("prefix", ""),
            dir=kwargs.pop("dir", tempfile.gettempdir()),
        )

        instance = super(TempDirpath, cls).__new__(cls, path, *parts, **kwargs)
        if kwargs.get("create", kwargs.get("touch", True)):
            instance.touch()
        return instance
Dirtemp = TempDirpath


class TempFilepath(Filepath):
    """Create a temporary file

    :Example:
        f = TempFilepath("foo", "bar.ext")
        print(f) # $TMPDIR/foo/bar.ext
    """
    def __new__(cls, *parts, **kwargs):
        parts = cls.split(*parts)
        basedir = TempDirpath(*parts[:-1], **kwargs)

        basename = parts[-1:]
        if not basename:
            basename = "".join(random.sample(string.ascii_letters, random.randint(3, 11)))

        instance = super(TempFilepath, cls).__new__(cls, basedir, basename, **kwargs)
        if kwargs.get("create", kwargs.get("touch", True)):
            instance.touch()
        return instance
Filetemp = TempFilepath


class Cachepath(Filepath):
    """A file that can contain cached data

    :Example:
        c = Cachepath("key")
        if c:
            data = c.read()
        else:
            data = do_something_long()
            c.write(data)
    """
    prefix = ''
    """set the key prefix"""

    ttl = 0
    """how long to cache the result in seconds, 0 for unlimited"""

    def __new__(cls, *keys, **kwargs):
        if not keys:
            raise ValueError("*keys was empty")

        ttl = kwargs.pop("ttl", cls.ttl)
        prefix = kwargs.pop("prefix", cls.prefix)

        basedir = kwargs.get("dir", "")
        if not basedir:
            basedir = environ.CACHE_DIR

        key = cls.create_key(*keys, prefix=prefix)
        instance = super(Cachepath, cls).__new__(cls, basedir, key)

        instance.ttl = ttl
        instance.prefix = prefix
        return instance

    @classmethod
    def create_key(cls, *keys, **kwargs):
        parts = []
        prefix = kwargs.pop("prefix", cls.prefix)
        if prefix:
            parts.append(prefix)
        parts.extend(keys)

        badchars = String(string.punctuation).stripall(".-_")

        keys = map(lambda s: String(s).stripall(badchars), parts)
        return '.'.join(keys)

    def __nonzero__(self):
        ret = True
        if self.empty():
            ret = False

        else:
            if self.ttl:
                ret = self.modified_within(seconds=self.ttl)

        return ret

    def __bool__(self):
        return self.__nonzero__()

    def write(self, data):
        b = pickle.dumps(data, pickle.HIGHEST_PROTOCOL)
        self.write_bytes(b)

    def read(self):
        return pickle.loads(self.read_bytes())

    def modified_within(self, seconds=0, **timedelta_kwargs):
        """returns true if the file has been modified within the last seconds

        :param seconds: integer, how many seconds
        :param **timedelta_kwargs: dict, can be thing like days, must be passed
            as a named keyword
        :returns: boolean, True if file has been modified after the seconds back
        """
        now = datetime.datetime.now()
        then = self.modified()
        timedelta_kwargs["seconds"] = seconds
        td_check = datetime.timedelta(**timedelta_kwargs)
        #pout.v(now, td_check, then)
        return (now - td_check) < then


class Sentinel(Cachepath):
    """Creates a file after the first failed boolean check, handy when you only want
    to check things at certain intervals

    :Example:
        s = Sentinel("foo")
        if not s:
            # do something you don't want to do all the time
        if not s:
            # this won't ever be ran because the last `if not s` check will have
            # created the sentinel file
    """
    def __new__(cls, *keys, **kwargs):
        """Create the sentinel file

        :param *keys: same arguments as Cachepath
        :param **kwargs:
            yearly: bool, create the file once per year
            monthly: bool, create the file once per month
            weekly: bool, create the file once per week
            daily: bool, create the file once per day
            hourly: bool, create the file once per hour
            ttl: bool, create the file every ttl seconds
        """
        now = datetime.datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        week = now.strftime("%W")
        hour = now.strftime("%H")

        dates = []
        if kwargs.pop("yearly", False):
            dates = [year]

        elif kwargs.pop("monthly", False):
            dates = [year, month]

        elif kwargs.pop("weekly", False):
            dates = [year, week]

        elif kwargs.pop("daily", False):
            dates = [year, month, day]

        elif kwargs.pop("hourly", False):
            dates = [year, month, day, hour]

        keys = list(keys) + dates

        instance = super(Sentinel, cls).__new__(cls, *keys, **kwargs)
        return instance

    def __nonzero__(self):
        ret = False
        if self.exists():
            ret = True
            if self.ttl:
                ret = not self.modified_within(seconds=self.ttl)

        else:
            # we create the file after the first failed exists check
            self.touch()

        return ret


# !!! Ripped from pyt.path which was ripped from pout.path
class SitePackagesDirpath(Dirpath):
    """Finds the site-packages directory and sets the value of this string to that
    path"""
    def __new__(cls):
        basepath = cls._basepath
        if not basepath:
            try:
                paths = site.getsitepackages()
                basepath = paths[0] 
                logger.debug(
                    "Found site-packages directory {} using site.getsitepackages".format(
                        basepath
                    )
                )

            except AttributeError:
                # we are probably running this in a virtualenv, so let's try a different
                # approach
                # try and brute-force discover it since it's not defined where it
                # should be defined
                sitepath = os.path.join(os.path.dirname(site.__file__), "site-packages")
                if os.path.isdir(sitepath):
                    basepath = sitepath
                    logger.debug(
                        "Found site-packages directory {} using site.__file__".format(
                            basepath
                        )
                    )

                else:
                    for path in sys.path:
                        if path.endswith("site-packages"):
                            basepath = path
                            logger.debug(
                                "Found site-packages directory {} using sys.path".format(
                                    basepath
                                )
                            )
                            break

                    if not basepath:
                        for path in sys.path:
                            if path.endswith("dist-packages"):
                                basepath = path
                                logger.debug(
                                    "Found dist-packages directory {} using sys.path".format(
                                        basepath
                                    )
                                )
                                break

        if not basepath:
            raise IOError("Could not find site-packages directory")

        return super(SitePackagesDirpath, cls).__new__(cls, basepath)

