# -*- coding: utf-8 -*-
import re
import os
import fnmatch
import stat
import codecs
import shutil
import hashlib
from collections import deque, defaultdict
import site
import tempfile
import itertools
import glob
import datetime
import string
import random
import struct
import imghdr
from pathlib import Path as Pathlib
import pickle
from contextlib import contextmanager
import errno
import gzip
#import zipfile
#import tarfile

# not available on Windows
try:
    import fcntl
except ImportError:
    fcntl = None

from .compat import *
from .config.environ import environ
from .string import String, ByteString
from .collections import ListIterator
from .copy import Deepcopy
from .http import HTTPClient
from .url import Url
from .datetime import Datetime
from . import logging


logging.setdefault(__name__, "INFO")
logger = logging.getLogger(__name__)


class Path(String):
    """Provides a more or less compatible interface to the pathlib.Path api of
    python 3 that can be used across py2 and py3 codebases. However, The Path
    instances are actually string instances and are always resolved

    This finally brings into a DRY location my path code from testdata,
    stockton, and bang, among others where I've needed this functionality. I've
    also tried to standardize the interface to be very similar to Pathlib so
    you can, hopefully, swap between them

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
        return Pathlib(self.path)

    @property
    def parts(self):
        """A tuple giving access to the path’s various components

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parts
        """
        return self.pathlib.parts

    @property
    def root(self):
        """A string representing the (local or global) root, if any

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.root
        """
        return self.pathlib.root

    @property
    def anchor(self):
        """The concatenation of the drive and root

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.anchor
        """
        return self.pathlib.anchor

    @property
    def parents(self):
        """An immutable sequence providing access to the logical ancestors of
        the path

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parents
        """
        return [self.create_dir(p) for p in self.pathlib.parents]

    @property
    def parent(self):
        """The logical parent of the path

        NOTE -- this should never be overridden because it is part of the
        Pathlib api

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.parent
        """
        return self.create_dir(os.path.dirname(self.path))

    @property
    def paths(self):
        """Return all the paths in this path

        :returns: list, if we had a path /foo/bar/che.ext then this would
            return /foo, /foo/bar, /foo/bar/che.ext
        """
        paths = self.parents
        paths.reverse()
        paths.append(self)
        return paths

    @property
    def directory(self):
        """return the directory portion of a directory/fileroot.ext path

        This is the base property for many of directory aliases, so this is the
        one that should be overridden if you need to customize behavior. DO NOT
        touch .parent
        """
        return self.parent

    @property
    def basedir(self):
        """
        NOTE -- This is overridden in the Temp* classes to be the basedir the
        temp file/dir was created in because they might create multiple dirs
        when being created and there needs to be a way to figure out relpath
        and things like that
        """
        return self.directory

    @property
    def dirname(self):
        return self.directory

    @property
    def dirpath(self):
        return self.directory

    @property
    def name(self):
        """A string representing the final path component, excluding the drive
        and root

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
        fileroot, ext = self.splitpart(self.name)
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
        return self.splitpart(self.path)[0]

    @property
    def pathroot(self):
        return self.stempath

    @property
    def suffix(self):
        """The file extension of the final component

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.suffix
        """
        # we do not use self.splitpart here because suffix should keep
        # consistent functionality with pathlib
        fileroot, ext = os.path.splitext(self.name)
        return ext

    @property
    def ext(self):
        """Returns the extension

        this will usually be identical to .suffix but it isn't guarranteed
        because this uses self.splitpart() to find the extension which tries to
        be a bit smarter while finding the extension
        """
        _, ext = self.splitbase()
        return ext.lstrip(".")

    @property
    def extension(self):
        return self.ext

    @property
    def suffixes(self):
        """A list of the path’s file extensions

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.suffixes
        """
        return self.pathlib.suffixes

    @classmethod
    def is_absolute_path(cls, path):
        return os.path.isabs(path)

    @classmethod
    def is_file_path(cls, path):
        return os.path.isfile(path)

    @classmethod
    def is_dir_path(cls, path):
        return os.path.isdir(path)

    @classmethod
    def is_path_instance(cls, path):
        return isinstance(path, cls.path_class())

    @classmethod
    def splitpart(cls, part):
        """Split the part to base and extension

        This tries to be a bit smarter than os.path.split() but while that
        will fail by being too naive, this will fail by being to smart

        https://superuser.com/a/315395/
            While you are free to use any length of extension you wish, I would
            not recommend using a very lengthy one for one reason: convention.
            Most file extensions are three to four alphanumeric characters.
            Anything longer, or with funny characters, is going to "stand out"


        https://filext.com/faq/file_extension_information.html

        :param part: str, the part to split
        :returns: tuple, (base, ext), extension will be empty if nothing was
            found
        """
        logger.debug(f"Splitting to base and extension: {part}")
        base, ext = os.path.splitext(part)
        if ext:
            is_valid = True
            if not base:
                # there technically is no length limit, but for my purpose if
                # it is too long it probably isn't valid
                logger.debug("Extension is too long")
                is_valid = False

            else:
                cext = String(ext[1:]) # for comparison let's strip the period

                if cext == "":
                    logger.debug("Extension can't just be a period")
                    is_valid = False

                if not cext.re(r"^[a-zA-Z0-9 \$#&+@!\(\)\{\}'`_~-]+$").match():
                    logger.debug(
                        "Extension contains 1 or more invalid characters"
                    )
                    is_valid = False

                elif cext.re(r"[|<>\^=?/\[\]\";\*]$").match():
                    logger.debug("Extension contains illegal characters")
                    is_valid = False

                elif not cext.isascii():
                    logger.debug("Extension is not just ascii")
                    is_valid = False

                elif cext.re(r"\s").search():
                    # while an extension can contain spaces, I think for my
                    # purpose let's say an extension that contains a space is
                    # invalid
                    logger.debug("Extension has spaces")
                    is_valid = False

                elif len(cext) > 25:
                    # there technically is no length limit, but for my purpose
                    # if it is too long it probably isn't valid
                    logger.debug("Extension is too long")
                    is_valid = False

            if not is_valid:
                base = base + ext
                ext = ""

        logger.debug(f"Returning base: {base}, ext: {ext}")
        return base, ext

    @classmethod
    def splitparts(cls, *parts, **kwargs):
        """Does the opposite of .joinparts()

        :param *parts: mixed, as many parts as you pass in as arguments
        :param **kwargs:
            regex - the regex used to split the parts up
            root - if a root is needed this will be used
        :returns: list, all the normalized parts
        """
        ps = []
        regex = kwargs.get("regex", r"[\\/]+")
        root = kwargs.get("root", "/")
        path_classes = (basestring, cls.path_class())

        for p in parts:
            if isinstance(p, path_classes) or not isinstance(p, Iterable):
                s = String(p)

                if s:
                    for index, pb in enumerate(re.split(regex, s)):
                        if pb:
                            ps.append(re.sub(regex, "", pb))

                        else:
                            if root and not ps and index == 0:
                                ps.append(root)

                else:
                    if not ps and root:
                        ps.append(root)

            else:
                for pb in cls.splitparts(*p, **kwargs):
                    if root and pb == root:
                        if not ps:
                            ps.append(pb)

                    else:
                        ps.append(pb)

        return ps

    @classmethod
    def joinparts(cls, *parts, **kwargs):
        """like os.path.join but normalizes for directory separators

        Differences from the standard os.path.join:

            >>> os.path.join("/foo", "/bar/", "/che")
            '/che'

            >>> Path.join("/foo", "/bar/", "/che")
            '/foo/bar/che'

            >>> Path.join("", "bar")
            '/bar'

        :param *parts: mixed, as many parts as you pass in as arguments
        :param **kwargs:
            sep - if you want to join with a different separator than os.sep
        :returns: str, all the parts joined together
        """
        try:
            ps = cls.splitparts(*parts, **kwargs)
            sep = kwargs.get("sep", "")
            return sep.join(ps) if sep else os.path.join(*ps)

        except TypeError as e:
            raise TypeError("joinparts got an empty parts list") from e

    @classmethod
    def get_basename(cls, ext="", prefix="", name="", suffix="", **kwargs):
        """return just a valid file name

        This method has a strange signature (ext and prefix come before name to
        make it easier for TempPath since this method is more user facing when
        used with temp paths)

        :param ext: str, the extension you want the file to have
        :param prefix: str, this will be the first part of the file's name
        :param name: str, the name you want to use (prefix will be added to the
            front of the name and suffix and ext will be added to the end of
            the name)
        :param suffix: str, if you want the last bit to be posfixed with
            something
        :param **kwargs:
            - safe: bool, if true then remove potentially unsafe characters
              (default: False)
        :returns: str, the random filename
        """
        basename = name or ""

        if prefix:
            basename = prefix + basename

        if ext:
            if not ext.startswith("."):
                ext = "." + ext

            if basename.endswith(ext):
                basename, ext = os.path.splitext(basename)

        if suffix:
            basename += suffix

        if ext:
            basename += ext

        return basename

    @classmethod
    def get_parts(cls, count=1, prefix="", name="", suffix="", ext="", **kwargs):
        """Returns count parts

        :param count: int, how many parts you want in your module path (1 is
            [foo], 2 is [foo, bar], etc)
        :param prefix: string, if you want the last bit to be prefixed with
            something
        :param suffix: string, if you want the last bit to be posfixed with
            something
        :param name: string, the name you want to use for the last bit (prefix
            will be added to the front of the name and postfix will be added to
            the end of the name)
        :returns: list[str], parts are generated by calling .get_basename and
            empty parts returned from .get_basename are ignored
        """
        parts = []
        count = max(count, 1)

        for x in range(count - 1):
            if p := cls.get_basename(**kwargs):
                parts.append(p)

        p = cls.get_basename(
            prefix=prefix,
            name=name,
            suffix=suffix,
            ext=ext,
            **kwargs
        )
        if p:
            parts.append(p)

        return parts

    @classmethod
    def normparts(cls, *parts, **kwargs):
        """Normalize the parts and prepare them to generate the path and value

        :param *parts: list, the parts of the path
        :param **kwargs: anything else needed to generate the parts
        :return: list, a the parts ready to generate path and value
        """
        parts = cls.splitparts(*parts, **kwargs)
        kwargs.setdefault("suffix", kwargs.pop("postfix", ""))
        basedir = kwargs.pop("dir", "")

        name = kwargs.pop("name", kwargs.pop("basename", ""))
        if not name:
            name = parts.pop(-1) if parts else ""

        count = max(1, kwargs.pop("count", 1) - len(parts))

        ps = cls.get_parts(
            count=count,
            name=name,
            **kwargs
        )

        if ps:
            if name:
                parts = ps[:-1] + parts + [ps[-1]]

            else:
                parts = ps + parts

        if basedir:
            parts = cls.splitparts(basedir, **kwargs) + list(parts)

        return parts

    @classmethod
    def normpath(cls, *parts, **kwargs):
        """normalize a path, accounting for things like windows dir seps

        the path is the actual file path located in .path

        :param *parts: list, the already normalized parts of the path
        :param **kwargs: anything else
        :return: str, the full path ready to be placed in .path
        """
        path = ""
        if parts:
            path = cls.joinparts(*parts, **kwargs)
            path = os.path.abspath(
                os.path.expandvars(
                    os.path.expanduser(path)
                )
            )

        return path

    @classmethod
    def normpaths(cls, paths, baseparts="", **kwargs):
        """normalizes the paths from methods like .add_paths() and .add()

        :param paths: dict|list|callable
            * dict: if paths is a dict, then the keys will be the path part and
                the value will be the data/contents of the file at the full
                path. If value is None or empty dict then that path will be
                considered a directory.
            * list: if paths is a list then it will be a list of directories to
                create
            * callable: a callback that takes a Filepath instance
        :param baseparts: list, will be merged with the paths keys to create
            the full path
        :returns list of tuples, each tuple will be in the form of (parts,
            data)
        """
        ret = []
        baseparts = cls.splitparts(baseparts or [], **kwargs)

        if paths:
            if isinstance(paths, Mapping):
                for k, v in paths.items():
                    p = cls.splitparts(baseparts, k, **kwargs)
                    if isinstance(v, Mapping):
                        ret.extend(cls.normpaths(v, p, **kwargs))

                    else:
                        ret.append((p, v))

            elif isinstance(paths, Sequence):
                for k in paths:
                    ret.append((cls.splitparts(baseparts, k, **kwargs), None))

            else:
                raise ValueError("Unrecognized value for paths")

        else:
            ret.append((baseparts, None))

        return ret

    @classmethod
    def normvalue(cls, *parts, **kwargs):
        """normalize a value 

        the value is the actual string value

        :param *parts: list, the already normalized parts of the path
        :param **kwargs: anything else
        :return: str, the string value
        """
        return kwargs["path"]

    @classmethod
    def path_class(cls):
        """Return the Path class this class will use, this is a method because
        we couldn't make them all Path class properties because they are
        defined after Path"""
        return Path

    @classmethod
    def dir_class(cls):
        """Return the Dirpath class to use"""
        return Dirpath

    @classmethod
    def file_class(cls):
        """Return the Filepath class to use"""
        return Filepath

    @classmethod
    def iterator_class(cls):
        return PathIterator

    @classmethod
    def create_file(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.file_class()
        return cls.create(*parts, **kwargs)
        #return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create_dir(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.dir_class()
        return cls.create(*parts, **kwargs)
        #return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create_path(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.path_class()
        return cls.create(*parts, **kwargs)
        #return kwargs["path_class"](*parts, **kwargs)

    @classmethod
    def create(cls, *parts, **kwargs):
        """Create a path instance using the full inferrencing (guessing code)
        of cls.path_class().__new__()"""
        if "path_class" not in kwargs:
            # if a path class isn't passed in and a single part was passed in
            # that is a Path instance, then go ahead and clone that
            if len(parts) == 1:
                if cls.is_path_instance(parts[0]):
                    kwargs["path_class"] = type(parts[0])

        # we want inference to work so we don't want any path_class being
        # passed to the __new__ method but we will use it to create the
        # instance if passed in
        path_class = kwargs.pop("path_class", cls.path_class())
        return path_class(*parts, **kwargs)

    @classmethod
    def create_as(cls, instance, path_class, **kwargs):
        """Used by .__new__() to convert a Path to one of the children. This is
        a separate method so it could be augmented by children classes if
        desired

        take note that this has a different signature than all the other
        create_* methods

        :param instance: Path, a Path instance created by __new__()
        :param path_class: type, the path class that was passed in to __new__()
        :param **kwargs: the keywords passed into __new__()
        :returns: Path, either the same instance or a different one
        """
        instance.path = kwargs["path"]

        if path_class or (cls is not cls.path_class()):
            # makes sure if you've passed in any class explicitely, even the
            # Path class, then don't try and infer anything
            pass

        else:
            if instance.is_file():
                instance = instance.as_file()

            elif instance.is_dir():
                instance = instance.as_dir()

            else:
                # let's assume a file if it has an extension
                if instance.ext:
                    instance = instance.as_file()

        if kwargs.get("touch", kwargs.get("create", False)):
            instance.touch()

        return instance

    def __new__(cls, *parts, **kwargs):
        """Create a new path

        all the arguments are combined like this:

            dir / *parts / prefix + name + suffix + ext

        :param *parts: mixed, parts you want to have in the path, or a full
            path
        :param **kwargs:
            * ext: str, the extension (see .get_basename)
            * prefix: str, a prefix to name (see .get_basename)
            * suffix: str, a suffix to name (see .get_basename)
            * dir: str|Dirpath, a base directory, this will be prepended to
              *parts (see .normparts)
            * name|basename: str, the file name
        """
        parts = cls.normparts(*parts, **kwargs)
        path = cls.normpath(*parts, **kwargs)
        value = cls.normvalue(*parts, path=path, **kwargs)

        # we don't set to cls here because has to be None so create_as works
        # further down
        path_class = kwargs.pop("path_class", None)

        instance = super().__new__(
            path_class if path_class else cls,
            value,
            encoding=kwargs.pop("encoding", environ.ENCODING),
            errors=kwargs.pop("errors", environ.ENCODING_ERRORS),
        )
        return cls.create_as(
            instance, 
            path=path,
            parts=parts,
            path_class=path_class,
            **kwargs
        )

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

    def count(self, *args, **kwargs):
        raise NotImplementedError()

    def size(self, *args, **kwargs):
        return self.count(*args, **kwargs)

    def stat(self):
        """Return a os.stat_result object containing information about this
        path, like os.stat(). The result is looked up at each call to this
        method

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
        """Return the name of the user owning the file. KeyError is raised if
        the file’s uid isn’t found in the system database.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.owner
        """
        if is_py2:
            import pwd
            return String(pwd.getpwuid(self.stat().st_uid).pw_name)

        else:
            ret = self.pathlib.owner()

        return ret

    def group(self):
        """Return the name of the group owning the file. KeyError is raised if
        the file’s gid isn’t found in the system database.

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

    def is_type(self):
        """Syntactic sugar around calling is_dir() if this is a Dirpath
        instance or .is_file() if this is a Filepath instance or .exists() if
        this is just a Path instance

        :returns: bool, True if this is an actual instance of the path type it
            is
        """
        ret = False
        if isinstance(self, self.dir_class()):
            ret = self.is_dir()

        elif isinstance(self, self.file_class()):
            ret = self.is_file()

        else:
            ret = self.exists()
        return ret

    def istype(self):
        return self.is_type()

    def is_dir(self):
        """Return True if the path points to a directory (or a symbolic link
        pointing to a directory), False if it points to another kind of file.

        False is also returned if the path doesn’t exist or is a broken
        symlink; other errors (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_dir
        """
        return os.path.isdir(self.path)

    def isdir(self):
        return self.is_dir()

    def is_dir_instance(self):
        """Return True if self is a Dirpath"""
        return isinstance(self, self.dir_class())

    def is_file(self):
        """Return True if the path points to a regular file (or a symbolic link
        pointing to a regular file), False if it points to another kind of
        file.

        False is also returned if the path doesn’t exist or is a broken
        symlink; other errors (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_file
        """
        return os.path.isfile(self.path)

    def isfile(self):
        return self.is_file()

    def is_file_instance(self):
        """Return True if self is a Filepath"""
        return isinstance(self, self.file_class())

    def is_mount(self):
        """Return True if the path is a mount point: a point in a file system
        where a different file system has been mounted. On POSIX, the function
        checks whether path’s parent, path/.., is on a different device than
        path, or whether path/..  and path point to the same i-node on the same
        device — this should detect mount points for all Unix and POSIX
        variants. Not implemented on Windows.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_mount
        """
        return os.path.ismount(self.path)

    def is_symlink(self):
        """Return True if the path points to a symbolic link, False otherwise.

        False is also returned if the path doesn’t exist; other errors
        (such as permission errors) are propagated.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.is_symlink
        """
        return os.path.islink(self.path)

    def is_absolute(self):
        """Return whether the path is absolute or not. A path is considered
        absolute if it has both a root and (if the flavour allows) a drive

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_absolute
        https://docs.python.org/3/library/os.path.html#os.path.isabs
        """
        return self.is_absolute_path(self.path)

    def isabs(self):
        return self.is_absolute()

    def is_reserved(self):
        """With PureWindowsPath, return True if the path is considered reserved
        under Windows, False otherwise. With PurePosixPath, False is always
        returned.

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_reserved
        """
        raise NotImplementedError()

    def is_root(self):
        """Return True if path is root (eg, / on Linux), False otherwise"""
        return self.name == ""

    def joinpath(self, *other):
        """Calling this method is equivalent to combining the path with each of
        the other arguments in turn

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.joinpath
        """
        return self.create(self.pathlib.joinpath(*other))

    def child(self, *other):
        return self.joinpath(*other)

    def match(self, pattern):
        """Match this path against the provided glob-style pattern. Return True
        if matching is successful, False otherwise.

        If pattern is relative, the path can be either relative or absolute,
        and matching is done from the right

        If pattern is absolute, the path must be absolute, and the whole path
        must match

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
        """Return a new path with the name changed. If the original path
        doesn’t have a name, ValueError is raised

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.with_name
        """
        if self.is_root():
            raise ValueError("{} has an empty name".format(self))
        return self.create(self.parent, name)

    def with_suffix(self, suffix):
        """Return a new path with the suffix changed. If the original path
        doesn't have a suffix, the new suffix is appended instead. If the
        suffix is an empty string, the original suffix is removed

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

    def with_stem(self, stem):
        """Return a new path with the stem/fileroot changed

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.with_stem
        """
        return self.pathlib.with_stem(stem)

    def slug(self):
        """Return this path as a URI slug

        :returns: str, this path with spaces removed and lowercase
        """
        path = re.sub(r"\s+", "-", self.path)
        return path.lower()

    def sanitize(self, callback=None, maxpart=255, maxpath=260, rename=False):
        """Sanitize each part of self.path to make sure all the characters are
        safe

        macos has a 1023 character path limit, with each part limited to 255
        chars: https://discussions.apple.com/thread/250275651

        Dropbox has a max character path of 260 and they say don't use periods
        (which makes no sense), you also can't have emoji or emoticons, there
        is no easy way to just strip emoji though so I'm just going to strip
        all non-ascii characters
            https://help.dropbox.com/files-folders/sort-preview/file-names

        Other references:
            * https://kb.acronis.com/content/39790
            * https://gitlab.com/jplusplus/sanitize-filename

        :param callback: callable, takes a fileroot and extension, and returns
            a sanitized tuple (fileroot, extension) which will be joined by a
            period
        :param chars: string, the characters you want to remove from each part
        :param maxpart: int, the maximum length of each part of the path
        :param maxpath: int, the maximum length of the total path
        :param rename: bool, True if this should sanitize parts that already
            exist
            ??? should this be renamed "rename_existing"?
        :returns: Path, the path with bad characters stripped and within
            maxpath length
        """
        sparts = []

        if maxpart > maxpath:
            maxpart = maxpath
        rempath = maxpath

        paths = self.paths
        remparts = len(paths)

        if not callback:
            def callback(s, ext):
                # strip all these characters from anywhere
                chars = "\\/:*?\"<>|^\0"
                s = String(s).stripall(chars)

                # removes non-ascii characters
                # https://stackoverflow.com/a/2759009/5006
                s = re.compile(r'[^\x00-\x7F]+').sub('', s)

                # remove and consolidate all whitespace to one space (this
                # strips newlines and tabs) and make sure there are no spaces
                # at the beginning or end of the part
                s = re.compile(r'\s+').sub(' ', s.strip())

                return (s, callback(ext, "")[0] if ext else ext)

        logger.debug(
            f"Sanitizing {remparts} part(s) with {maxpart} chars each"
            f" and a total path of {maxpath} chars"
        )

        for p in paths:
            sp = p.basename
            if p.is_root():
                # we can't modify root in any way
                logger.debug(f"Path.sanitize part {p} is root")
                sp = p.path

            elif p.exists() and not rename:
                # if the folder already exists then it makes no sense to try
                # and modify it
                logger.debug(f"Path.sanitize part {p} already exists")
                sp = p.basename

            else:
                if remparts > 1:
                    # since we have more parts still this must be a directory
                    # so no point in splitting it
                    fileroot = sp
                    ext = ""

                else:
                    # we are at the basename so let's split the ext so we make
                    # sure to include it
                    fileroot, ext = self.splitpart(sp)

                logger.debug(f"Path.sanitize part {fileroot}{ext} sanitizing")
                rempart = min(maxpart, rempath // remparts) - len(ext)

                # https://kb.acronis.com/content/39790
                # https://gitlab.com/jplusplus/sanitize-filename
                # strip characters and then truncate
                sp, ext = callback(fileroot, ext)
                sp = String(sp).truncate(size=rempart, postfix="")
                sp = sp + ext

            remparts -= 1
            if sp:
                rempath -= (len(sp) + 1)
                if rempath < 0:
                    raise ValueError(
                        "maxpath is too short to effectively sanitize this path"
                    )

                sparts.append(sp)

        return self.create(*sparts, path_class=type(self))

    def backup(self, suffix=".bak", ignore_existing=True):
        """backup the file to the same directory with given suffix

        :param suffix: str, what will be appended to the file name (eg, foo.ext
            becomes foo.ext.bak)
        :param ignore_existing: boolean, if True overwrite an existing backup,
            if false then don't backup if a backup file already exists
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
        """Rename this file or directory to the given target, and return a new
        Path instance pointing to target. On Unix, if target exists and is a
        file, it will be replaced silently if the user has permission. target
        can be either a string or another path object

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rename

        :returns: the new Path instance
        """
        target = self.create_path(target)
        os.rename(self.path, target)
        return self.create(target)

    def replace(self, target):
        """Rename this file or directory to the given target, and return a new
        Path instance pointing to target. If target points to an existing file
        or directory, it will be unconditionally replaced.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.replace

        :returns: the new Path instance.
        """
        target = self.create_path(target)
        self.pathlib.replace(target)
        return self.create(target)

    def mv(self, target, *args, **kwargs):
        """mimics the behavior of unix mv command"""
        raise NotImplementedError()

    def move_to(self, target, *args, **kwargs):
        return self.mv(target, *args, **kwargs)

    def cp(self, target, *args, **kwargs):
        """mimics the behavior of unix cp command"""
        raise NotImplementedError()

    def copy_to(self, target, *args, **kwargs):
        return self.cp(target, *args, **kwargs)

    def relative_to(self, *other, empty_same=False):
        """Compute a version of this path relative to the path represented by
        other.  If it’s impossible, ValueError is raised

        returns the relative part to the *other

        :Example:
            d = Path("/foo/bar/baz/che")
            d.relative_to("/foo/bar") # baz/che
            d.relative_to("/foo") # bar/baz/che

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.relative_to

        :param *other: string|Directory, the directory you want to return that
            self is a child of
        :param empty_same: bool, by default, this returns "." when other is the
            same path. Both os.path.relpath and Pathlib.relative_to return "."
            so I'm sticking with it by default but set this to True to return
            "" instead
            TODO -- maybe rename this equal_value="." or equal_path="."
        :returns: str, the part of the path that is relative, because these are
            relative paths they can't return Path instances
        :raises: ValueError, if self isn't in the subpath of other or if
            other isn't an absolute path
        """
        ret = String(self.pathlib.relative_to(*other))

        if empty_same and ret == ".":
            ret = ""

        return ret

    def relative_parts(self, *other):
        """Similar to relative_to() but returns a list of each part

        this calls .relative_to(empty_same=True) so it will return an empty
        list if self and other are the same

        Moved from bang.path.Path on 1-2-2023

        :param *other: string|Directory, the directory you want to return that
            self is a child of
        :returns: list[str], the individual parts of the path that is relative
            in list format
        """
        relative = self.relative_to(*other, empty_same=True)
        return re.split(r"[\/]", relative) if relative else []

    def is_relative_to(self, *other):
        """Return whether or not this path is relative to the other path

        https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_relative_to
        """
        try:
            self.relative_to(*other)
            return True

        except ValueError:
            return False

    def symlink_to(self, target, target_is_directory=False):
        """Make this path a symbolic link to target. Under Windows,
        target_is_directory must be true (default False) if the link’s target
        is a directory.  Under POSIX, target_is_directory’s value is ignored

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.symlink_to
        """
        target = self.create(target)
        if is_py2:
            os.symlink(self.path, target)

        else:
            self.pathlib.symlink_to(
                target,
                target_is_directory=target_is_directory
            )

        return target

    def archive_to(self, target):
        raise NotImplementedError(
            "Waiting for Archivepath api to be finalized"
        )

    def resolve(self, strict=False):
        """Make the path absolute, resolving any symlinks. A new path object is
        returned

        If the path doesn’t exist and strict is True, FileNotFoundError is
        raised.

        If strict is False, the path is resolved as far as possible and any
        remainder is appended without checking whether it exists. If an
        infinite loop is encountered along the resolution path, RuntimeError is
        raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.resolve
        """
        ret = self.create(os.path.realpath(self.path))
        if strict:
            if not ret.exists():
                raise OSError(self.path)

        return ret

    def samefile(self, other_path):
        """Return whether this path points to the same file as other_path,
        which can be either a Path object, or a string. The semantics are
        similar to os.path.samefile() and os.path.samestat().

        An OSError can be raised if either file cannot be accessed for some
        reason.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.samefile
        """
        other_path = self.create(other_path)
        return os.path.samefile(self.path, other_path)

    def touch(self, mode=0o666, exist_ok=True):
        """Create a file at this given path. If mode is given, it is combined
        with the process’ umask value to determine the file mode and access
        flags.  If the file already exists, the function succeeds if exist_ok
        is true (and its modification time is updated to the current time),
        otherwise FileExistsError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.touch
        """
        raise NotImplementedError()

    def rm(self):
        """remove file/dir, does not raise error on file/dir not existing"""
        raise NotImplementedError()

    def delete(self):
        """remove file/dir, alias of .rm(), does not raise error on file/dir
        not existing"""
        return self.rm()

    def remove(self):
        """remove file/dir, alias of .rm(), does not raise error on file/dir
        not existing"""
        return self.rm()

    def clear(self):
        """clear the file/directory but don't delete it"""
        raise NotImplementedError()

    def created(self):
        """return a datetime.datetime of when the file was created"""
        try:
            # https://stackoverflow.com/a/947239
            # https://stackoverflow.com/a/39501288
            t = self.stat().st_birthtime

        except AttributeError:
            t = os.path.getctime(self.path)

        return Datetime(t)
        #return datetime.datetime.fromtimestamp(t)

    def modified(self):
        """return a datetime.datetime of when the file was modified"""
        # http://stackoverflow.com/a/1526089/5006
        t = os.path.getmtime(self.path)
        return Datetime(t)
        #return datetime.datetime.fromtimestamp(t)

    def updated(self):
        return self.modified()

    def accessed(self):
        """return a datetime.datetime of when the file was accessed"""
        t = os.path.getatime(self.path)
        return Datetime(t)

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

    def splitext(self):
        """Splits pathroot from ext

        :Example:
            p = Path("/foo/bar/che.ext")
            pathroot, ext = p.slitext() # ("/foo/bar/che", ".ext")

        :returns: tuple, (pathroot, suffix)
        """
        return self.splitpart(self.path)

    def splitbase(self):
        """Splits fileroot from ext, uses the basename instead of the full path

        :Example:
            p = Path("/foo/bar/che.ext")
            fileroot, ext = p.slitbase() # ("che", ".ext")

        :returns: tuple, (fileroot, suffix)
        """
        return self.splitpart(self.name)


class Dirpath(Path):
    """Represents a directory so extends Path with methods to iterate through
    a directory"""
    @property
    def iterator(self):
        """Returns an iterator for this directory"""
        return self.iterator_class()(self)

    @classmethod
    def cwd(cls):
        """Return a new path object representing the current directory (as
        returned by os.getcwd())

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.cwd
        """
        return cls.create_dir(os.getcwd())

    @classmethod
    def home(cls):
        """Return a new path object representing the user’s home directory
        (as returned by os.path.expanduser() with ~ construct)

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.home
        """
        return cls.create_dir(os.path.expanduser("~"))

    @contextmanager
    def as_cwd(self, orig_cwd=None):
        """Switch over to self as the current working directory (cwd) for
        the life of the context, then switch back to the original cwd

        :Example:
            print(Dirpath.cwd()) # /current

            with Dirpath("/not/current") as path:
                print(Dirpath.cwd()) # /not/current

            print(Dirpath.cwd()) # /current

        :param orig_cwd: Path|str, the original cwd, if not supplied then
            the system cwd will be used
        """
        if not orig_cwd:
            orig_cwd = os.getcwd()

        try:
            os.chdir(self)
            yield self

        finally:
            os.chdir(orig_cwd)

    def add_files(self, paths, **kwargs):
        return self.add_paths(paths, **kwargs)

    def add_dirs(self, paths, **kwargs):
        return self.add_paths(paths, **kwargs)

    def add_paths(self, paths, **kwargs):
        """create a whole bunch of files/directories all at once

        :Example:
            Dirpath.add_paths({
                "foo": {
                    "bar": {
                        "baz.txt": "/foo/bar/baz.txt data",
                    },
                    "che": {}, # /foo/che/ directory
                    "bam": None, # /foo/bam/ directory
                }
            })

        :param paths: dict|list|callable
            * dict: if paths is a dict, then the keys will be the path part and
                the value will be the data/contents of the file at the full
                path. If value is None or empty dict then that path will be
                considered a directory.
            * list: if paths is a list then it will be a list of directories to
                create
            * callable: a callback that takes a Filepath instance
        :returns: list, all the created Path instances
        """
        ret = []

        ps = self.normpaths(paths, self.path)
        for parts, data in ps:
            if data is None:
                dp = self.create_dir(*parts, **kwargs)
                dp.touch()
                ret.append(dp)

            else:
                fp = self.create_file(parts, **kwargs)
                if data:
                    if isinstance(data, self.path_class()):
                        data.copy_to(fp)

                    elif isinstance(data, (Bytes, bytearray)):
                        fp.write_bytes(data, **kwargs)

                    elif isinstance(data, Str):
                        fp.write_text(data, **kwargs)

                    elif callable(data):
                        # if it's a callback then we assume the callback will
                        # do whatever it needs with the file
                        data(fp)

                    else:
                        # unknown data is assumed to be something that can be
                        # normalized in .prepare_text()
                        fp.write_text(data, **kwargs)

                else:
                    fp.touch()

                ret.append(fp)

        return ret

    def add(self, paths, **kwargs):
        """add paths to this directory

        :param paths: dict|list, see @add_paths() for description of paths
            structure
        :returns: list, all the created Path instances
        """
        return self.add_paths(paths, **kwargs)

    def add_children(self, paths, **kwargs):
        return self.add_paths(paths, **kwargs)

    def add_file(self, target, data="", **kwargs):
        ps = self.add({self.joinparts(target): data}, **kwargs)
        return ps[0]

    def add_dir(self, target):
        ps = self.add({self.joinparts(target): None})
        return ps[0]

    def add_child(self, target, data=None, **kwargs):
        ps = self.add({self.joinparts(target): data}, **kwargs)
        return ps[0]

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
        """Create a new directory at this given path. If mode is given, it is
        combined with the process’ umask value to determine the file mode and
        access flags.  If the path already exists, FileExistsError is raised.

        If parents is true, any missing parents of this path are created as
        needed; they are created with the default permissions without taking
        mode into account (mimicking the POSIX mkdir -p command).

        If parents is false (the default), a missing parent raises
        FileNotFoundError.

        If exist_ok is false (the default), FileExistsError is raised if the
        target directory already exists.

        If exist_ok is true, FileExistsError exceptions will be ignored
        (same behavior as the POSIX mkdir -p command), but only if the last
        path component is not an existing non-directory file.

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
        """Move the entire contents of the directory at self into a directory
        at target

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

        # https://docs.python.org/3/library/shutil.html#shutil.copytree
        shutil.copytree(self.path, target, dirs_exist_ok=True)

        self.rm()

        return target

    def cp(self, target, recursive=True, into=True):
        """Copy directory at self into/to a directory at target

        Added recursive on 1-4-2023 and into on 1-21-2023 to better mimic
        Bang.path.Directory.copy_to

        Uses this under the hood:
            https://docs.python.org/3/library/shutil.html#shutil.copytree

        :Example:
            # src is copied into, or merged with, target
            src.cp(target) # cp -R src target/

            # src.basename is copied to target if target exists
            # src is copied into target if target does not exist
            # src is merged into target/src if target/src exists
            src.cp(target, recursive=True, into=False) # cp -R src target

        :param target: Dirpath|str, the destination directory
        :param recursive: bool, True if copy files in this dir and all subdirs,
            false to only copy files in self
        :param into: bool, copy into target instead of to
            target/{self.basename} if target exists, check the example for more
            details
        :returns: Dirpath, the target directory
        """
        target = self.create_dir(target)

        if recursive:
            if not into:
                if target.is_dir():
                    target = target.child_dir(self.basename)

            shutil.copytree(self.path, target, dirs_exist_ok=True)

        else:
            for p in self.children(recursive=recursive):
                tp = target.child(p.relative_to(self))
                #tp.touch()
                #p.copy_to(tp)
                p.cp(tp)

        return target

    def touch(self, mode=0o666, exist_ok=True):
        """Create the directory at this given path.  If the directory already
        exists, the function succeeds if exist_ok is true (and its modification
        time is updated to the current time), otherwise FileExistsError is
        raised."""
        if self.exists():
            if not exist_ok:
                raise OSError("FileExistsError")

            os.utime(self.path, None)

        else:
            # https://docs.python.org/3/library/os.html#os.makedirs
            os.makedirs(self.path, exist_ok=True)

    def filecount(self, recursive=True):
        """return how many files in directory, this is O(n)"""
        return len(self.files().recursive(recursive))

    def dircount(self, recursive=True):
        """return how many directories in directory, this is O(n)"""
        return len(self.dirs().recursive(recursive))

    def count(self, recursive=True):
        """return how many files and directories in directory, this is O(n)"""
        return len(self.iterator.recursive(recursive))

    def glob(self, pattern):
        """Glob the given relative pattern in the directory represented by this
        path, yielding all matching files (of any kind)

        The “**” pattern (eg, **/*.txt) means "this directory and all
        subdirectories, recursively".  In other words, it enables recursive
        globbing

        globs are endswith matches, so if you passed in "*.txt" it would match
        any filepath that ended with ".txt", likewise, if you pass in "bar" it
        would match any files/folders that ended with "bar"

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob
        """
        for fp in self.pathlib.glob(pattern):
            yield self.create(fp)

    def rglob(self, pattern):
        """recursive glob

        This is like calling Path.glob() with “**/” added in front of the given
        relative pattern, meaning it will match files in this directory and all
        subdirectories

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.rglob
        """
        for fp in self.pathlib.rglob(pattern):
            yield self.create(fp)

    def scandir(self):
        """I legitimately have never used this method and wouldn't recommend
        using it. It's only here for completeness

        https://docs.python.org/3.5/library/os.html#os.scandir

        https://github.com/benhoyt/scandir
        https://bugs.python.org/issue11406
        """
        for entry in os.scandir(self.path):
            yield entry

    def iterdir(self):
        """When the path points to a directory, yield path objects of the
        directory contents

        This will only yield files/folders found in this directory, it is not
        recursive

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.iterdir

        :returns: generator, yields children Filepath and Dirpath instances
            found only in this directory
        """
        if is_py2:
            for basename in os.listdir(self.path):
                yield self.create(self.path, basename)

        else:
            for p in self.pathlib.iterdir():
                yield self.create(p)

    def children(self, **kwargs):
        """Provides a fluid interface to iterate over all the files and folders
        in this directory. Basicaly, this is syntactic sugar around the
        PathIterator

        For most iteration needs you should either use this method, .files(),
        or .dirs(). Most of the other methods are here mainly for full
        compatibility with pathlib.Path's interface

        .iterdirs() and .iterfiles() are similar to .files() and .dirs() but
        they set recursive=False by default, where .files() and .dirs() are
        recursive by default.

        :param **kwargs: the keys/values will be set onto the PathIterator
        :returns: PathIterator
        """
        it = self.iterator
        for k, v in kwargs.items():
            attr = getattr(it, k, None)
            if attr:
                attr(v)
        return it

    def iterdirs(self, **kwargs):
        """Similar to .iterdir() but only returns the directories in this
        directory only

        Same as .children(recursive=False, dirs=True)
        """
        kwargs.setdefault("recursive", False)
        return self.children(**kwargs).dirs()

    def dirs(self, **kwargs):
        """Provides a fluid interface to iterate all files in this directory

        :Example:
            # makes this possible
            it = self.dirs()

            # this is the normal PathIterator interface
            for it in self.dirs():
                pass

        :returns: PathIterator
        """
        return self.children(**kwargs).dirs()

    def child_dirs(self, **kwargs):
        return self.dirs(**kwargs)

    def iterfiles(self, **kwargs):
        """similar to .iterdir() but only iterate through all the files in this
        directory only

        Same as .children(recursive=False, files=True)
        """
        kwargs.setdefault("recursive", False)
        return self.children(**kwargs).files()

    def files(self, **kwargs):
        """Provides a fluid interface to iterate all directories in this
        directory

        :Example:
            # makes this possible
            it = self.files()

            # this is the normal PathIterator interface
            for it in self.files():
                pass

        :returns: PathIterator
        """
        return self.children(**kwargs).files()

    def child_files(self, **kwargs):
        return self.files(**kwargs)

    def walk(self, *args, **kwargs):
        """passthrough for os.walk

        https://docs.python.org/3/library/os.html#os.walk
        :returns: yields (basedir, dirs, files) in the exact way os.walk does,
            these are not Path instances
        """
        for basedir, dirs, files in os.walk(self.path, *args, **kwargs):
            yield basedir, dirs, files

    def __iter__(self):
        """Iterate through this directory

        :returns: PathIterator
        """
        return self.iterator

    def has(self, *parts, **kwargs):
        """Check for pattern in directory

        :Example:
            d = Dirpath("foo")
            d.add_file("bar/che.txt", "che.txt data")

            d.has(pattern="*/che.txt") # True
            d.has("bar") # True
            d.has("bar/che.txt") # True
            d.has("bar/che") # False
            d.has(pattern="*/bar/che.*") # True

        :param *parts: path parts, these will be passed to .child() so they can
            be relative to self.path
        :param **kwargs: these will be passed to .children()
        :returns: boolean, True if a file/dir was found matching the passed in
            values
        """
        ret = False
        if parts:
            ret = self.child(*parts).exists()

        else:
            ret = bool(self.children(**kwargs))

        return ret

    def has_file(self, *parts, **kwargs):
        """Similar to .has() but only checks files"""
        kwargs.setdefault("files", True)
        return self.child_file(*parts).isfile() if parts else self.has(**kwargs)

    def has_dir(self, *parts, **kwargs):
        """Similar to .has() but only checks directories"""
        kwargs.setdefault("dirs", True)
        return self.child_dir(*parts).isdir() if parts else self.has(**kwargs)

    def child(self, *parts):
        """Return a new instance with parts added onto self.path"""
        return self.path_class()(self.path, *parts)

    def get_child(self, *parts):
        return self.child(*parts)

    def child_file(self, *parts, **kwargs):
        return self.file_class()(self.path, *parts, **kwargs)

    def get_file(self, *parts, **kwargs):
        return self.child_file(*parts, **kwargs)

    def child_dir(self, *parts, **kwargs):
        return self.dir_class()(self.path, *parts, **kwargs)

    def get_dir(self, *parts, **kwargs):
        return self.child_dir(*parts, **kwargs)

    def file_text(self, *parts):
        """return the text of the basename file in this directory"""
        output_file = self.create_file(self.path, *parts)
        return output_file.read_text()

    def file_bytes(self, *parts):
        """return the bytes of the basename file in this directory"""
        output_file = self.create_file(self.path, *parts)
        return output_file.read_bytes()
DirPath = Dirpath


class Filepath(Path):
    """Represents a file so extends Path with file reading/writing methods"""
    def empty(self):
        """Return True if file is empty"""
        ret = True
        if self.exists():
            st = self.stat()
            ret = False if st.st_size else True
        return ret

    @contextmanager
    def flock(self, mode="", operation=None, **kwargs):
        """similar to open but will also lock the file resource and will
        release the resource when the context manager is done

        :Example:
            filepath = Filepath("<PATH>")
            with filepath.lock("r") as fp:
                if fp:
                    # fp exists so we got the lock
                    pass

                else:
                    # fp is None so we didn't get the lock
                    pass

        :param mode: see .open()
        :param operation: defaults to exclusive lock, see fcntl module
        :param **kwargs: will be passed to .open()
        :returns: file descriptor with an active lock, it will return None if
            the lock wasn't successfully acquired
        """
        if fcntl:
            if operation is None:
                operation = fcntl.LOCK_EX | fcntl.LOCK_NB

        else:
            raise ValueError(
                "flock does not work because fcntl module is unavailable"
            )

        try:
            with self.open(mode, **kwargs) as fp:
                fcntl.flock(fp, operation)
                try:
                    yield fp

                finally:
                    fcntl.flock(fp, fcntl.LOCK_UN)

        except OSError as e:
            if e.errno == errno.EACCES or e.errno == errno.EAGAIN:
                yield None

            else:
                raise

    def flock_text(self, mode="", **kwargs):
        kwargs.setdefault("encoding", self.encoding)
        kwargs.setdefault("errors", self.errors)
        return self.flock(mode, **kwargs)

    def open(self, mode="", buffering=-1, encoding=None, errors=None, newline=None):
        """Open the file pointed to by the path, like the built-in open()
        function does

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.open
        """
        if not mode:
            mode = "r" if encoding else "rb"

        open_kwargs = dict(
            mode=mode,
            errors=errors,
            buffering=buffering,
            newline=newline,
        )

        if "b" not in mode:
            open_kwargs["encoding"] = encoding

        logger.debug(
            f"Opening: {self.path} with mode: {mode} and encoding: {encoding}"
        )

        try:
            fp = open(
                self.path,
                **open_kwargs
            )

        except IOError:
            if self.exists():
                raise

            else:
                self.touch()
                fp = self.open(mode, buffering, encoding, errors, newline)

        return fp

    def open_text(self, mode="", **kwargs):
        """Just like .open but will set encoding and errors to class values
        if they aren't passed in"""
        kwargs.setdefault("encoding", self.encoding)
        kwargs.setdefault("errors", self.errors)
        return self.open(mode, **kwargs)

    def __call__(self, mode="", **kwargs):
        """Allow an easier interface for opening a writing file descriptor

        This uses the class defaults for things like encoding, so it's better to
        use .open() or .write_bytes() if you want to write non-encoded raw text

        :Example:
            p = Filepath("foo/bar.ext")
            with p("a+") as fp:
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

    def splitlines(self, keepends=False, encoding=None, errors=None):
        """iterate through all the lines"""
        encoding = encoding or self.encoding
        errors = errors or self.errors
        with self.open("r", encoding=encoding, errors=errors) as f:
            for line in f:
                yield line if keepends else line.rstrip()

    def __iter__(self):
        for line in self.splitlines():
            yield line

    def chunklines(self, linecount=1, keepends=False, encoding=None, errors=None):
        chunk = []
        lines = self.splitlines(
            keepends=keepends,
            encoding=encoding,
            errors=errors
        )
        for i, line in enumerate(lines, 1):
            chunk.append(line)
            if i % linecount == 0:
                yield chunk
                chunk = []

    def prepare_bytes(self, data, **kwargs):
        """Internal method used to prepare the data to be written

        :param data: str, the text that will be written
        :param **kwargs: keywords, you can pass in encoding here
        :returns: tuple, (data, encoding, errors)
        """
        encoding = (
            kwargs.get("encoding", None)
            or getattr(data, "encoding", self.encoding)
        )
        errors = (
            kwargs.get("errors", None)
            or getattr(data, "errors", self.errors)
        )
        data = ByteString(data, encoding=encoding, errors=errors)
        return data, encoding, errors

    def prepare_text(self, data, **kwargs):
        """Internal method used to prepare the data to be written

        :param data: str, the text that will be written
        :param **kwargs: keywords, you can pass in encoding here
        :returns: tuple, (data, encoding, errors)
        """
        encoding = (
            kwargs.get("encoding", None)
            or getattr(data, "encoding", self.encoding)
        )
        errors = (
            kwargs.get("errors", None)
            or getattr(data, "errors", self.errors)
        )
        data = String(data, encoding=encoding, errors=errors)
        return data, encoding, errors

    def write_bytes(self, data, **kwargs):
        """Open the file pointed to in bytes mode, write data to it, and close
        the file

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.write_bytes

        NOTE -- having **kwargs means the interface is different than
        Pathlib.write_bytes

        :param data: bytes
        :param **kwargs: supports errors and encoding keywords to convert data
            to bytes
        """
        data, encoding, errors = self.prepare_bytes(data, **kwargs)
        with self.open(mode="wb+") as fp:
            return fp.write(data)

    def write_text(self, data, **kwargs):
        """Open the file pointed to in text mode, write data to it, and close
        the file

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.write_text

        :param data: str
        :param **kwargs: supports errors and encoding keywords to convert data
            to str/unicode
        """
        data, encoding, errors = self.prepare_text(data, **kwargs)
        with self.open(mode="w+", encoding=encoding, errors=errors) as fp:
            return fp.write(data)

    def write(self, data, **kwargs):
        """Write data as either bytes or text

        :param data: bytes|string
        :return: the amount written
        """
        if isinstance(data, (Bytes, bytearray)):
            return self.write_bytes(data, **kwargs)

        else:
            return self.write_text(data, **kwargs)

    def append_text(self, data, **kwargs):
        data, encoding, errors = self.prepare_text(data, **kwargs)
        with self.open(mode="a+", encoding=encoding, errors=errors) as fp:
            return fp.write(data)

    def append_bytes(self, data):
        data, encoding, errors = self.prepare_bytes(data, **kwargs)
        with self.open(mode="ab+") as fp:
            return fp.write(data)

    def joinpath(self, *other):
        raise NotImplementedError()

    def cp(self, target, recursive=True, **kwargs):
        """copy self to/into target

        uses this under the hood:
            https://docs.python.org/3/library/shutil.html#shutil.copy

        :param target: str|Path, if a directory then self.basename will be the 
            target's basename. If the target is ambiguous this will make a best
            effort to guess if it was a file or a folder
        :param recursive: bool, if True then create any intermediate
            directories if they are missing. If False then this will fail if
            all the folders don't already exist
        :returns: Filpath, the target file path where self. was copied to
        """
        target = self.create(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        else:
            if not target.exists():
                if not target.is_file_instance():
                    # let's try our best to infer if this is a directory or not
                    if not target.ext and self.ext:
                        # target doesn't have an extension but this file does,
                        # so let's assume target is a directory
                        target = self.create_dir(target).child_file(self.basename)

                if recursive:
                    if isinstance(target, self.file_class()):
                        target.parent.touch()
                    else:
                        target.touch()

        shutil.copy(self.path, target)
        return target.as_file()

    def copy_into(self, target, **kwargs):
        """Copy this file to target directory

        Moved from bang.path on 1-3-2023

        :param target: directory, the target directory
        :returns: the new file
        """
        return self.cp(target, **kwargs)

    def mv(self, target):
        target = self.create(target)
        if target.is_dir():
            target = self.create_file(target, self.basename)

        shutil.move(self.path, target)
        return target.as_file()

    def unlink(self, missing_ok=False):
        """Remove this file or symbolic link. If the path points to a
        directory, use Path.rmdir() instead.

        If missing_ok is false (the default), FileNotFoundError is raised if
        the path does not exist.

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
        """Create a file at this given path. If mode is given, it is combined
        with the process’ umask value to determine the file mode and access
        flags.  If the file already exists, the function succeeds if exist_ok
        is true (and its modification time is updated to the current time),
        otherwise FileExistsError is raised.

        https://docs.python.org/3/library/pathlib.html#pathlib.Path.touch
        """
        if self.exists():
            if not exist_ok:
                raise OSError("FileExistsError")

            os.utime(self.path, None)

        else:
            self.parent.touch(mode, exist_ok)

            # http://stackoverflow.com/a/1160227/5006
            with open(self.path, "a"):
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

    def has(self, pattern=""):
        """Check for pattern in the body of the file

        :Example:
            d = Filepath("foo.txt")

            d.has("<TEXT>") # True

        :param pattern: string|callable, the contents in the file. If callable
            then it will do pattern(line) for each line in the file
        :returns: boolean, True if the pattern is in the file
        """
        with self.open("r", encoding=self.encoding, errors=self.errors) as f:
            if pattern:
                if callable(pattern):
                    for line in f:
                        if pattern(line):
                            return True

                else:
                    return pattern in f.read()

            else:
                data = f.read(1)
                return True if data else False

        return False

    def gzip(self, target=""):
        """Gzip the filepath to target

        https://docs.python.org/3/library/gzip.html

        :param target: str, the target output file, if empty then ".gz" will
            be attached to self's path and that will be used as target
        :returns: Path, the gzipped file path
        """
        if not target:
            target = f"{self.path}.gz"

        target = self.create_file(target)

        with open(self.path, "rb") as f_in:
            with gzip.open(target, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

        return target
FilePath = Filepath


class PathIterator(ListIterator):
    r"""Iterate through a directory path

    I was not happy with all the Dirpath iteration methods I've added over the
    last few years, they all were subtlely different and it was annoying trying
    to figure out which one I should use. This is an attempt to fix that. This
    provides a fluid interface to iterating a directory

    You will primarily create/interact with this class through a Dirpath
    instance:

        dp = Dirpath("<SOME-PATH>")

        pi = dp.iterator # get a new iterator through Dirpath.iterator property
        pi = dp.children() # same as dp.iterator
        pi = dp.files() # equal to PathIterator(dp).files()
        pi = dp.dirs() # equal to PathIterator(dp).dirs()

    Sadly, you can't do this even though Dirpath.__iter__ returns a
    PathIterator instance:

        # this does not work
        for p in Dirpath("<SOME-PATH>").pattern(".txt"):
            print(p)

    I'm not sure why the above doesn't work, but I'm sure it has something to
    do with the call hierarchy and not entering the iterator until all the
    methods have been called, I've put this here so I don't forget because I've
    tried to do the above more than once.

    This does work however:

        # this works though
        for p in Dirpath("<SOME-PATH>").iterator.pattern(".txt"):
            print(p)

    For the most part, there are 4 types of filtering criteria:

        * pattern - matches an fnmatch pattern
        * regex - matches a re.search regex
        * callback - matches if callback(path) returns True
        * value - has to match exactly, this is more internal and while it can
            be called externally, it would be better to not use it and use one
            of the other main filtering methods

    There are 4 types of actual filtering:

        * eq - Must match, can apply to both files and directories
        * ne - Must not match, can apply to both files and directories
        * in - Used for traversing directories, only applies to directories, if
            the directory matches it will be traversed, directories that don't
            match will not be traversed
        * nin - inverse of `in` and also only applies to directories

    The filtering criteria methods all have the same signature:

        .<METHOD-NAME>(<VALUE>, **<KEYWORDS>)

    Where the <VALUE> corresponds to whatever the filtering criteria expects:

        .eq_pattern("*.txt")
        .eq_regex(r"\.txt")
        .eq_callback(lambda p: p.endswith(".txt"))

    All methods can take these keywords:

        * filename: bool, True to compare against Filepath.basename
        * dirname: bool, True to compare against Dirpath.basename
        * files: bool, True to apply only to Filepath instances
        * dirs: bool, True to apply only to Dirpath instances
        * depth: bool, only works against directories, sets depth for this
            iterating this specific folder
        * finish: bool, only works against directories, marks this path as the
            end, so don't iterate the contents of this directory
        * basename: bool, applies to Path.basename instead of the whole path
        * inverse: bool, reverse the match, so if it returned True is would be
            False
        * traverse: bool, only apply the criteria to traversing directories,
            not matching directories, this is handy when you want to match
            certain files/directories that only reside in certain directories

    There are also wrapper methods:

        * eq_dir and ne_dir
        * eq_file and ne_file
        * eq_<PATH-ATTRIBUTE> and ne_<PATH-ATTRIBUTE> (eg eq_fileroot, ne_ext)
        * in_dir and nin_dir
        * files
        * dirs

    Wrapper methods have additional keywords they accept:

        * pattern: str, the fnmatch pattern
        * regex: str, the re.search regex pattern
        * callback: callable[Path], the callback

    The interface tries to be fluid to make it easy to dial in exactly what
    you want

    :Example:
        # iterate through only the files in the current directory
        for p in PathIterator(dirpath).depth(1).files():
            print(p)

        # iterate through only the directories in the current directory
        for p in PathIterator(dirpath).depth(1).dirs():
            print(p)

        # find all txt files in the current and all sub-directories
        for p in PathIterator(dirpath).eq_pattern("*.txt"):
            print(p)

        # find any files that aren't txt files
        for p in PathIterator(dirpath).ne_pattern("*.txt").files():
            print(p)

        # iterate through current directory and its subdirectories, but no
        # farther
        for p in PathIterator(dirpath).depth(2):
            print(p)

        # ignore directories/files that start with an underscore
        PathIterator(dirpath).ne_regex(r"^_", basename=True)

        # return all directories named foo
        PathIterator(dirpath).dirs(regex=r"foo")
        PathIterator(dirpath).eq_basename("foo").dirs()

        # stop traversing a directory if that directory contains "stop.txt"
        it = PathIterator(dirpath).dirs().eq_callback(
            lambda p: p.has_file("stop.txt"),
            finish=True
        )

        # or you can finish the directory manually:
        it = PathIterator(dirpath).dirs()
        for p in it:
            if p.has_file("stop.txt"):
                it.finish(p)
    """
    def __init__(self, path: Dirpath):
        """
        :param path: Dirpath, the directory to iterate
        """
        self.path = path

        # subdirectory folder depth to iterate, see .depth()
        self._yield_depth = -1

        # reverse the iteration?
        self._yield_reverse = False

        # sort the iteration? When set this is a tuple (args, kwargs) to pass
        # to sorted
        self._yield_sort = None

        # the following 2 counters are incremented/decremented in .files() and
        # .dirs(), the idea is that you could do self.files().dirs() and that
        # really would iterate files and folders because .files() would
        # increment _yield_files and decrement _yield_dirs, while .dirs() would
        # do the opposite, so the net change to the counters would be 0

        # if value is >0 then iterate files
        self._yield_files = 1

        # if value is >0 then iterate directories
        self._yield_dirs = 1

        # the following are the criteria dicts, they have the following top
        # level criteria keys, see ._add_criteria():
        #   * paths: the filter criteria for all the paths after filenames and
        #     dirnames are filtered
        #   * files: all files will be filtered through these
        #   * dirs: all directories will be filtered through these

        # the glob/fnmatch patterns to filter the iteration through
        self._yield_patterns = defaultdict(list)

        # the regex patterns to filter the iteration through
        self._yield_regexes = defaultdict(list)

        # the callables to filter the iteration through
        self._yield_callbacks = defaultdict(list)

        self._yield_values = defaultdict(list)

        # contains paths that should be ignored on subsequant iterations, see
        # .finish()
        self._finished = set()

    def recursive(self, recursive=True):
        """Only iterate current directory or current and all subdirectories

        This is syntactic sugar around .depth where it sets depth to -1 if
        recursive is True, or depth to 1 if recursive is False

        :param recursive: bool, if True then iterate through directory and all
            subdirectories, otherwise only iterate through current directory
            and ignore subdirectories
        """
        return self.depth(-1) if recursive else self.depth(1)

    def depth(self, depth):
        """Set depth of iteration

        :param depth: int, how many subdirectories should be iterated. -1 for
            all subdirs, 1 would only iterate the current directory, 2 would do
            2 levels of subdirectories, etc.
        """
        self._yield_depth = depth
        return self

    def finish(self, path):
        """When recursively iterating through a directory you might sometimes
        want to cease recursing into a directory, you can do that by passing
        the path into here, that will stop it from recursing into the directory
        any more

        :Example:
            it = PathIterator(dirpath).dirs()
            for dp in it:
                if dp.has_file("sentinal"):
                    # we've found a sentinal file so we don't need to recurse
                    # this directory anymore
                    it.finish(dp)

        :param path: Path, the path to stop traversing
        """
        self._finished.add(path)
        return self

    def files(self, v=True, **kwargs):
        """Iterate only files (this excludes directories)

        :param v: bool, default to True to iterate files, you can pass in False
            to reverse it and make it so you don't iterate files
        :param **kwargs:
            - criteria: dict, this is a dict of values that will be passed as
                **kwargs to any matching value in the rest of kwargs, so if 
                kwargs contains pattern="..." then .pattern("...", **criteria)
                will be called
        :returns: self
        """
        if v:
            self._yield_files += 1
            self._yield_dirs -= 1

        else:
            self._yield_files -= 1
            self._yield_dirs += 1

        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "files": True,
            "inverse": not v,
        })
        return self._add_kwargs(criteria, **kwargs)

    def dirs(self, v=True, **kwargs):
        """Iterate only directories (this excludes files)

        see .files since this signature is the same, it just applies to
        directories instead of files
        """
        if v:
            self._yield_dirs += 1
            self._yield_files -= 1

        else:
            self._yield_dirs -= 1
            self._yield_files += 1

        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "dirs": True,
            "inverse": not v,
        })
        return self._add_kwargs(criteria, **kwargs)

    def in_dir(self, value=None, **kwargs):
        """There is a difference between matching and traversing/iterating a
        directory. You might sometimes want to match a directory who matches
        something but also iterate any directories that don't match it. This
        allows you to do that, you can set separate criteria for traversing
        directories than the criteria used for matching

        NOTE: self.path is currently always considered valid and will be
        traversed no matter what for matches, the criteria set through this
        method only applies to sub-directories of self.path

        :param value: str, the basename to match, if not passed in then the
            `callback`, `regex`, or `pattern` keys in kwargs will be used
        :param **kwargs:
            - pattern: str, the fnmatch pattern
            - regex: str, the re.search regex pattern
            - callback: callable[Path]
        :returns: self, for fluid interface
        """
        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "dirs": True,
            "traversal": True,
        })

        if value:
            kwargs["value"] = value
            criteria.setdefault("attribute", "basename")

        return self._add_kwargs(criteria, **kwargs)

    def in_dirs(self, *args, **kwargs):
        return self.in_dir(*args, **kwargs)

    def nin_dir(self, value=None, **kwargs):
        """Inverses .in_dir"""
        return self.in_dir(value, inverse=True, **kwargs)

    def nin_dirs(self, *args, **kwargs):
        return self.nin_dir(*args, **kwargs)

    def eq_dir(self, value=None, **kwargs):
        """wrapper method to make it a bit more fluid to filter directories for
        matching (not traversal)

        :param value: str, if passed in then filter against Dirpath.basename
        """
        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "dirs": True,
        })

        if value:
            kwargs["value"] = value
            criteria.setdefault("attribute", "basename")

        return self._add_kwargs(criteria, **kwargs)

    def ne_dir(self, value=None, **kwargs):
        """Inverse of eq_dir"""
        return self.eq_dir(value, inverse=True, **kwargs)

    def eq_file(self, value=None, **kwargs):
        """wrapper method to make it a bit more fluid to filter files for
        matching

        :param value: str, if passed in then filter against Filepath.basename
        """
        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "files": True,
        })

        if value:
            kwargs["value"] = value
            criteria.setdefault("attribute", "basename")

        return self._add_kwargs(criteria, **kwargs)

    def ne_file(self, value=None, **kwargs):
        """Inverse of eq_file"""
        return self.eq_file(value, inverse=True, **kwargs)

    def pattern(self, pattern, **kwargs):
        """Only iterate paths that match pattern

        https://docs.python.org/3/library/fnmatch.html#fnmatch.fnmatch

        :param pattern: str, the pattern to match, fnmatch patterns are
            endswith so if you want to match a path part you would need to
            prefix * to the pattern
        :param **kwargs:
            * inverse: bool, Fail the match if pattern matches the path
        """
        return self._add_criteria(self._yield_patterns, pattern, **kwargs)

    def eq_pattern(self, pattern, **kwargs):
        """alias of .pattern to make the fluid more consistent with the wrapper
        methods"""
        return self.pattern(pattern, **kwargs)

    def ne_pattern(self, pattern, **kwargs):
        """Inverse the pattern match, same as calling
        .pattern(pattern, inverse=True)"""
        return self.pattern(pattern, inverse=True, **kwargs)

    def in_pattern(self, pattern, **kwargs):
        """Traverse method for setting a pattern, see .in_dir"""
        return self.in_dir(pattern=pattern, **kwargs)

    def nin_pattern(self, pattern, **kwargs):
        """inverse of in_pattern"""
        return self.in_pattern(pattern, inverse=True, **kwargs)

    def fnmatch(self, pattern, **kwargs):
        """alias of .pattern()"""
        return self.pattern(pattern, **kwargs)

    def glob(self, pattern, **kwargs):
        """alias of .pattern() but will set recursive=True if pattern starts
        with **/

        I attempted to mimic Pathlib's glob, but there is the glob module also:

            https://docs.python.org/3/library/glob.html#glob.glob
            https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob
        """
        self.pattern(pattern, **kwargs)
        return self.recursive("**/" in pattern)

    def rglob(self, pattern, **kwargs):
        """alias of .pattern() but sets recursive=True"""
        self.pattern(pattern, **kwargs)
        return self.recursive(True)

    def regex(self, regex, **kwargs):
        r"""Only iterate paths that match regex, regexes match the entire path
        by default, if you don't want to match the entire path you will need to
        structure your regex accordingly

        :Example:
            # match any file named foo (regardless of extension) or any folder
            PathIterator("<PATH>").regex(r"(?:^|/)foo(?:\.|$)")

        https://docs.python.org/3/library/re.html#re.search

        :param regex: str, the regex pattern to match
        :param **kwargs:
            * inverse: bool, Fail the match if regex matches the path
        """
        return self._add_criteria(self._yield_regexes, regex, **kwargs)

    def eq_regex(self, regex, **kwargs):
        """alias of .regex to make the fluid more consistent with the wrapper
        methods"""
        return self.regex(regex, **kwargs)

    def ne_regex(self, regex, **kwargs):
        """Inverse the regex match, same as calling
        .regex(regex, inverse=True)"""
        return self.regex(regex, inverse=True, **kwargs)

    def in_regex(self, regex, **kwargs):
        """Traverse method for setting a regex, see .in_dir"""
        return self.in_dir(regex=regex, **kwargs)

    def nin_regex(self, regex, **kwargs):
        """inverse of in_pattern"""
        return self.in_regex(regex, inverse=True, **kwargs)

    def callback(self, cb, **kwargs):
        """Only iterate paths that return True from cb(path)

        :param cb: callable, the callback with signature (path)
        :param **kwargs:
            * inverse: bool, Fail the match if callback returns True
        """
        return self._add_criteria(self._yield_callbacks, cb, **kwargs)

    def eq_callback(self, cb, **kwargs):
        """alias of .callback to make the fluid more consistent with the
        wrapper methods"""
        return self.callback(cb, **kwargs)

    def ne_callback(self, cb, **kwargs):
        """Inverse the callback return, same as calling
        .callback(cb, inverse=True)"""
        return self.callback(cb, inverse=True, **kwargs)

    def in_callback(self, callback, **kwargs):
        """Traverse method for setting a callback, see .in_dir"""
        return self.in_dir(callback=callback, **kwargs)

    def nin_callback(self, callback, **kwargs):
        """inverse of in_callback"""
        return self.in_callback(callback, inverse=True, **kwargs)

    def filter(self, cb, **kargs):
        """alias of .callback()"""
        return self.callback(cb, **kwargs)

    def filterfalse(self, cb, **kwargs):
        """alias of .ne_callback to match itertools method

        https://docs.python.org/3/library/itertools.html#itertools.filterfalse
        """
        return self.ne_callback(cb, **kwargs)

    def value(self, value, **kwargs):
        """While you can use this method externally this is more of an internal
        method used by the wrapper methods (eg, .eq_fileroot and other similar
        dynamic methods)

        It has similar signature to .pattern, .regex, and .callback
        """
        return self._add_criteria(self._yield_values, value, **kwargs)

    def eq_value(self, value, **kwargs):
        """alias of .value to make the fluid more consistent with the wrapper
        methods"""
        return self.value(value, **kwargs)

    def ne_value(self, value, **kwargs):
        """Inverse the value return, same as calling .value(v, inverse=True)
        """
        return self.value(value, inverse=True, **kwargs)

    def in_value(self, value, **kwargs):
        """Traverse method for setting a value, see .in_dir"""
        return self.in_dir(value, **kwargs)

    def nin_value(self, value, **kwargs):
        """inverse of in_value"""
        return self.in_value(value, inverse=True, **kwargs)

    def __getattr__(self, key):
        """Allows more advanced wrapper functionality, a wrapper method is a
        method that begins with:

            * eq_ - matches directly
            * ne_ - inverses an eq_ match
            * in_ - matches directories for traversal
            * nin_ - inverses an in_ directory traversal match

        The method name (key) must end with a valid Path attribute:

            * fileroot: matches fileroot of fileroot.ext
            * ext: matches ext of fileroot.ext
            * basename: matches fileroot.ext of a basename
        """
        method = ""

        try:
            command, name = key.split("_", 1)

        except ValueError as e:
            raise AttributeError(key) from e

        if command == "eq":
            method = self._eq_path_attribute

        elif command == "ne":
            method = self._ne_path_attribute

        elif command == "in":
            method = self._in_path_attribute

        elif command == "nin":
            method = self._nin_path_attribute

        if method:
            def callback(*args, **kwargs):
                return method(name, *args, **kwargs)

            return callback

        else:
            raise AttributeError(key)

    def _eq_path_attribute(self, name, value=None, **kwargs):
        """Internal method for handling eq_<PATH-ATTRIBUTE> wrapper methods"""
        criteria = kwargs.pop("criteria", {})
        criteria.update({
            "attribute": name,
        })

        if value:
            kwargs["value"] = value

        return self._add_kwargs(criteria, **kwargs)

    def _ne_path_attribute(self, name, value=None, **kwargs):
        """Internal method for handling ne_<PATH-ATTRIBUTE> wrapper methods"""
        return self._eq_path_attribute(
            name,
            value=value,
            inverse=True,
            **kwargs
        )

    def _in_path_attribute(self, name, value=None, **kwargs):
        """Internal method for handling in_<DIRPATH-ATTRIBUTE> wrapper methods
        """
        kwargs.setdefault("criteria", {"attribute": name})
        return self.in_dir(value, **kwargs)

    def _nin_path_attribute(self, name, value=None, **kwargs):
        """Internal method for handling nin_<DIRPATH-ATTRIBUTE> wrapper methods
        """
        return self._in_path_attribute(
            name,
            value=value,
            inverse=True,
            **kwargs
        )

    def _add_kwargs(self, criteria, **kwargs):
        """Certain methods are considered "wrapper" methods that allow
        passthrough kwargs in order to set criteria (eg eq_<PATH-ATTRIBUTE>
        dynamic methods and instance methods like: .dirs, .files, .eq_ext, etc)

        This internal method will take those passed in kwargs to those methods
        and match them to the passed in criteria. Basically, it takes the
        kwargs and if the key in the kwarg is a method on self (eg, pattern, 
        callback, or regex was passed in through the method's kwargs) it will
        call getattr(self, key)(value, **criteria)

        :Example:
            # filter files by a pattern
            self.files(pattern="*.txt")

        :param criteria: dict, these will also be passed to the callback found
            in kwargs as **criteria (basically the criteria key becomes the
            called method's kwargs
        :param **kwargs: keys are method names and values will be passed to the
            method named in key:
                - pattern: calls .pattern
                - regex: calls .regex
                - callback: calls .callback
        :returns: self, for fluid interface
        """
        # switch certain keys passed through the wrapper method as kwargs to
        # keys in criteria so they get passed through correctly
        if "finish" in kwargs:
            criteria["finish"] = kwargs.pop("finish")

        if "depth" in kwargs:
            criteria["depth"] = kwargs.pop("depth")

        if "inverse" in kwargs:
            criteria["inverse"] = kwargs.pop("inverse")

        for k, v in kwargs.items():
            cb = getattr(self, k, None)
            if callable(cb):
                cb(v, **criteria)

        return self

    def _add_criteria(self, criteria, v, **kwargs):
        """Adds (v, kwargs) to a criteria dict (the criteria dicts are defined
        in __init__ and contain teh actual filtering criteria values that will
        be used to decide if a certain path should be yielded or not

        :param criteria: dict, the criteria dict contains the patterns that
            should be filtered against a given path when iterating matching
            paths, this is an instance dictionary that will be added to
        :param v: mixed, the pattern/regex/callback
        :param **kwargs: By default the filtering criteria applies to Path,
            but can be focused depending on passed in keywords:
                - filename: bool, filtering criteria will apply to
                    Filepath.basename
                - dirname: bool, filtering criteria will apply to
                    Dirpath.basename
                - dirs: bool, filtering applies to Dirpath
                - files: bool, filtering applies to Filepath
                - basename: bool, filtering applies to Path.basename
        """
        if kwargs.pop("filename", kwargs.pop("filenames", False)):
            kwargs["attribute"] = "basename"
            criteria["files"].append((v, kwargs))

        elif kwargs.pop("dirname", kwargs.pop("dirnames", False)):
            kwargs["attribute"] = "basename"
            criteria["dirs"].append((v, kwargs))

        elif kwargs.pop("basename", kwargs.pop("basenames", False)):
            kwargs["attribute"] = "basename"
            criteria["files"].append((v, kwargs))
            criteria["dirs"].append((v, kwargs))

        elif kwargs.pop("dirs", False):
            criteria["dirs"].append((v, kwargs))

        elif kwargs.pop("files", False):
            criteria["files"].append((v, kwargs))

        else:
            criteria["paths"].append((v, kwargs))

        return self

    def _failed_match(self, matched, **kwargs):
        """internal method, this handles the inversing logic of the match and
        will always return False if the match failed according to the
        configured logic

        :param matched: bool, the original match value
        :param **kwargs:
            * inverse: bool, inverses matched
        :returns: bool, True if the match failed, False otherwise
        """
        inverse = kwargs.get(
            "inverse",
            kwargs.get("exclude", kwargs.get("ignore", False))
        )

        if matched:
            if inverse:
                failed = True

            else:
                failed = False

        else:
            if inverse:
                failed = False

            else:
                failed = True

        return failed

    def _haystack_yield(self, criteria_type, criterias, path, traversal):
        """Internal method that figures out what needle to use and what
        haystack will be used to find the needle

        :param criteria_type: str, one of `value`, `pattern`, `regex`, and
            `callback`
        :param criterias: list[tuple[Any, dict]], the criterias that should be
            checked. This corresponds to an item in a criteria dict defined in
            __init__ (eg, self._yield_patterns["paths"])
        :param path: Path, the original haystack
        :param traversal: bool, True if these criteria correspond to traversing
            directories instead of matching directories/files
        :returns: generator[tuple[Any, Path|str, dict]], the indexes are:
            - 0, needle, the criteria that will be used to check haystack, this
              could be things like a pattern to pass to fnmatch, a regex to
              pass to re.search, or a callable
            - 1, haystack, either the Path instance or the value of
                Path.<ATTRIBUTE>
            - 2, kwargs, these can be used to further refine the criteria check
        """
        for needle, kwargs in criterias:
            if traversal != kwargs.get("traversal", False):
                continue

            haystack = path
            if "attribute" in kwargs:
                haystack = getattr(path, kwargs["attribute"], path)

            else:
                if criteria_type == "pattern":
                    if not needle.startswith("*"):
                        haystack = getattr(path, "basename", path)

            yield needle, haystack, kwargs

    def _should_yield(self, criteria_key, path, traversal=False):
        """internal method, returns True if path should be yielded by the
        iterator

        This runs path through all filtering cases (patterns, regexes,
        callbacks) and accounts for inverse values

        :param criteria_key: str, each criteria dict has various keys, if the
            key exists on the criteria dict then the values/patterns/regexes
            found at this key will be checked against path
        :param path: Path
        :returns: bool, True if path should be yielded
        """
        should_yield = True
        yield_kwargs = {}

        criteria_types = [
            ("value", self._yield_values[criteria_key]),
            ("pattern", self._yield_patterns[criteria_key]),
            ("regex", self._yield_regexes[criteria_key]),
            ("callback", self._yield_callbacks[criteria_key]),
        ]

        for criteria_type, criterias in criteria_types:
            it = self._haystack_yield(
                criteria_type,
                criterias,
                path,
                traversal
            )
            for needle, haystack, kwargs in it:
                if criteria_type == "value":
                    should_yield = not self._failed_match(
                        haystack == needle,
                        **kwargs
                    )

                elif criteria_type == "pattern":
                   should_yield = not self._failed_match(
                       fnmatch.fnmatch(haystack, needle),
                       **kwargs
                   )

                elif criteria_type == "regex":
                    m = re.search(
                        needle,
                        haystack,
                        flags=kwargs.get("flags", 0)
                    )
                    should_yield = not self._failed_match(m, **kwargs)

                elif criteria_type == "callback":
                    should_yield = not self._failed_match(
                        needle(haystack),
                        **kwargs
                    )

                if should_yield:
                    yield_kwargs.update(kwargs)

                else:
                    yield_kwargs = {}
                    break

            if not should_yield:
                break

        return should_yield, yield_kwargs

    def _iterpaths(self, path, basedir, **kwargs):
        """internal method that converts .walk() values to Path instances. This
        is only called by ._iterpath

        :param path: Dirpath, the directory that is currently being iterated
        :param basedir: this is the current base directory of path.walk
        :param **kwargs:
            - filenames: list, we are going to iterate and check all the files
                in this directory
            - dirnames: list, we are going to iterate and check all the
                directories in this directory
        :returns: generator[tuple[bool, dict]], index 0 is whether this path
            should be yielded, index 1 are all the kwargs of the successful
            criteria matches that can be used to fine tune iteration
        """
        if "filenames" in kwargs:
            basenames = kwargs["filenames"]
            should_yield = kwargs.get("_yield_files", self._yield_files) > 0
            path_callback = path.create_file
            path_key = "files"
            traversal = False

        elif "dirnames" in kwargs:
            basenames = kwargs["dirnames"]
            should_yield = kwargs.get("_yield_dirs", self._yield_dirs) > 0
            path_callback = path.create_dir
            path_key = "dirs"
            traversal = kwargs.get("traversal", False)

        else:
            raise ValueError("No filenames or dirnames")

        if should_yield:
            for basename in basenames:
                p = path_callback(basedir, basename)

                should_yield, yield_kwargs = self._should_yield(
                    path_key,
                    p,
                    traversal=traversal
                )

                if should_yield:
                    should_yield, ykw = self._should_yield(
                        "paths",
                        p,
                        traversal=traversal
                    )

                    if should_yield:
                        yield_kwargs.update(ykw)

                        yield p, yield_kwargs

                        if finish := yield_kwargs.get("finish", False):
                            self.finish(p)

    def _iterpath(self, path, depth):
        """internal recursive method that yields path instances and respects
        depth

        :param path: Dirpath, the path to be iterated
        :param depth: int, how far into path should be iterated
        """
        for basedir, dirnames, filenames in path.walk(topdown=True):
            # https://docs.python.org/3/library/itertools.html#itertools.chain
            it = itertools.chain(
                self._iterpaths(path, basedir, dirnames=dirnames),
                self._iterpaths(path, basedir, filenames=filenames),
            )
            for p, yield_kwargs in it:
                yield p

            if depth != 1:
                depth = depth - 1 if depth >= 0 else depth

                it = self._iterpaths(
                    path,
                    basedir,
                    dirnames=dirnames,
                    _yield_dirs=1,
                    traversal=True
                )
                for p, yield_kwargs in it:
                    if p not in self._finished:
                        sp_depth = yield_kwargs.get("depth", depth)
                        for sp in self._iterpath(p, depth=sp_depth):
                            yield sp

            break

    def __iter__(self):
        """list interface compatibility"""
        it = self._iterpath(self.path, depth=self._yield_depth)

        if self._yield_reverse:
            if not self._yield_sort:
                it = [p for p in it]
                it.reverse()

        if self._yield_sort:
            it = [p for p in it]
            args, kwargs = self._yield_sort
            kwargs.setdefault("reverse", self._yield_reverse)
            it.sort(*args, **kwargs)

        for p in it:
            yield p

        self._finished = set()

    def get_index(self, index):
        """Makes subscription possible, unlike real lists though, this is O(n)

        This is a ListIterator method
        """
        for i, p in enumerate(self):
            if i == index:
                return p

        raise IndexError(f"Index {index} out of range")

    def get_slice(self, s):
        """Makes slicing possible, unlike real lists though, this is O(n)

        This is a ListIterator method
        """
        start = s.start
        stop = s.stop
        step = s.step

        if start is None and stop is None:
            if step and step > 1:
                sl = [p for p in self][::step]

            else:
                sl = self.copy()

        elif start and stop is None:
            if step and step > 1:
                sl = [p for p in self][start::step]

            else:
                sl = []
                for _i, p in enumerate(self):
                    if _i >= start:
                        sl.append(p)

        else:
            sl = []
            indexes = set(range(start or 0, stop, step or 1))
            for _i, p in enumerate(self):
                if _i in indexes:
                    sl.append(p)
                    indexes.discard(_i)

                if not indexes:
                    break

        return sl

    def count(self):
        """list interface compatibility, this is O(n)"""
        return len([p for p in self])

    def reverse(self):
        """list interface compatibility, this is O(n*n)"""
        #return reversed([p for p in self])
        self._yield_reverse = True
        return self

    def sort(self, *args, **kwargs):
        """list interface compatibility, this is O(n*n)"""
        #return sorted([p for p in self])
        self._yield_sort = (args, kwargs)
        return self

    def copy(self):
        """Makes a copy of the iterator"""
        ret = type(self)(self.path)

        for name in dir(self):
            if name.startswith("_yield"):
                setattr(ret, name, Deepcopy().copy(getattr(self, name)))

        return ret

    def tolist(self):
        """I don't want to just quack like a list, I want to actually be a list

        :returns: list, converts this iterator into an actual list
        """
        return [p for p in self]


class Imagepath(Filepath):
    """A filepath that represents an image

    This adds some handy helper methods/properties to make working with images
    easier

    Moved here from bang.path on 1-2-2023
    """
    @property
    def width(self):
        """Return the width of the image"""
        width, height = self.dimensions
        return width

    @property
    def height(self):
        """Return the height of the image"""
        width, height = self.dimensions
        return height

    @property
    def dimensions(self):
        """Return the largest dimensions of the image"""
        return self.get_info()["dimensions"][-1]

    def count(self):
        """The size of the image"""
        return len(self.read_bytes())

    def get_info(self):
        info = getattr(self, "_info", None)
        if info:
            return info

        # this makes heavy use of struct: https://docs.python.org/3/library/struct.html
        # based on this great answer on SO: https://stackoverflow.com/a/39778771/5006
        # read/write ico files: https://github.com/grigoryvp/pyico

        info = {"dimensions": [], "what": ""}

        with self.open() as fp:
            head = fp.read(24)
            if len(head) != 24:
                raise ValueError("Could not understand image")

            # https://docs.python.org/2.7/library/imghdr.html
            what = imghdr.what(None, head)
            if what is None:
                what = self.extension

            if what == 'png':
                check = struct.unpack('>i', head[4:8])[0]
                if check != 0x0d0a1a0a:
                    raise ValueError("Could not understand PNG image")

                width, height = struct.unpack('>ii', head[16:24])
                info["dimensions"].append((width, height))

            elif what == 'gif':
                width, height = struct.unpack('<HH', head[6:10])
                info["dimensions"].append((width, height))

            elif what == 'jpeg':
                try:
                    fp.seek(0) # Read 0xff next
                    size = 2
                    ftype = 0
                    while not 0xc0 <= ftype <= 0xcf or ftype in (0xc4, 0xc8, 0xcc):
                        fp.seek(size, 1)
                        byte = fp.read(1)
                        while ord(byte) == 0xff:
                            byte = fp.read(1)
                        ftype = ord(byte)
                        size = struct.unpack('>H', fp.read(2))[0] - 2
                    # We are at a SOFn block
                    fp.seek(1, 1)  # Skip `precision' byte.
                    height, width = struct.unpack('>HH', fp.read(4))
                    info["dimensions"].append((width, height))

                except Exception: #W0703
                    raise

            elif what == "ico":
                # https://en.wikipedia.org/wiki/ICO_(file_format)#Outline
                fp.seek(0)
                reserved, image_type, image_count = struct.unpack('<HHH', fp.read(6))
                for x in range(image_count):
                    width = struct.unpack('<B', fp.read(1))[0] or 256
                    height = struct.unpack('<B', fp.read(1))[0] or 256
                    info["dimensions"].append((width, height))

                    fp.read(6) # we don't care about color or density info
                    size = struct.unpack('<I', fp.read(4))[0]
                    offset = struct.unpack('<I', fp.read(4))[0]

            else:
                raise ValueError(
                    "Unsupported image type {}".format(self.extension)
                )

            info["what"] = what
            self._info = info
            return info

    def is_favicon(self):
        """Return True if the image is an .ico file, which is primarily used as
        an internet favicon"""
        info = self.get_info()
        return info["what"] == "ico"

    def is_animated(self):
        """Return true if image is animated

        :returns: boolean, True if the image is animated
        """
        return self.is_animated_gif()

    def is_animated_gif(self):
        """Return true if image is an animated gif

        primarily used this great deep dive into the structure of an animated
        gif to figure out how to parse it:

            http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp

        Other links that also helped:

            https://en.wikipedia.org/wiki/GIF#Animated_GIF
            https://www.w3.org/Graphics/GIF/spec-gif89a.txt
            https://stackoverflow.com/a/1412644/5006

        :returns: boolean, True if the image is an animated gif
        """
        info = self.get_info()
        if info["what"] != "gif": return False

        ret = False
        image_count = 0

        def skip_color_table(fp, packed_byte):
            """this will fp.seek() completely passed the color table

            http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#global_color_table_block

            :param fp: io, the open image file
            :param packed_byte: the byte that tells if the color table exists
                and how big it is
            """
            if is_py2:
                packed_byte = int(packed_byte.encode("hex"), 16)
            # https://stackoverflow.com/a/13107/5006
            has_gct = (packed_byte & 0b10000000) >> 7
            gct_size = packed_byte & 0b00000111

            if has_gct:
                global_color_table = fp.read(3 * pow(2, gct_size + 1))

        def skip_image_data(fp):
            """skips the image data, which is basically just a series of sub
            blocks with the addition of the lzw minimum code to decompress the
            file data

            http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#image_data_block

            :param fp: io, the open image file
            """
            lzw_minimum_code_size = fp.read(1)
            skip_sub_blocks(fp)

        def skip_sub_blocks(fp):
            """skips over the sub blocks

            the first byte of the sub block tells you how big that sub block
            is, then you read those, then read the next byte, which will tell
            you how big the next sub block is, you keep doing this until you
            get a sub block size of zero

            :param fp: io, the open image file
            """
            num_sub_blocks = ord(fp.read(1))
            while num_sub_blocks != 0x00:
                fp.read(num_sub_blocks)
                num_sub_blocks = ord(fp.read(1))

        with self.open() as fp:
            header = fp.read(6)
            #pout.v(header)
            if header == b"GIF89a": # GIF87a doesn't support animation
                logical_screen_descriptor = fp.read(7)
                skip_color_table(fp, logical_screen_descriptor[4])

                b = ord(fp.read(1))
                while b != 0x3B: # 3B is always the last byte in the gif
                    if b == 0x21: # 21 is the extension block byte
                        b = ord(fp.read(1))
                        if b == 0xF9: # graphic control extension
                            # http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#graphics_control_extension_block
                            block_size = ord(fp.read(1))
                            fp.read(block_size)
                            b = ord(fp.read(1))
                            if b != 0x00:
                                raise ValueError("GCT should end with 0x00")

                        elif b == 0xFF: # application extension
                            # http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#application_extension_block
                            block_size = ord(fp.read(1))
                            fp.read(block_size)
                            skip_sub_blocks(fp)

                        elif b == 0x01: # plain text extension
                            # http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#plain_text_extension_block
                            block_size = ord(fp.read(1))
                            fp.read(block_size)
                            skip_sub_blocks(fp)

                        elif b == 0xFE: # comment extension
                            # http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#comment_extension_block
                            skip_sub_blocks(fp)

                    elif b == 0x2C: # Image descriptor
                        # http://www.matthewflickinger.com/lab/whatsinagif/bits_and_bytes.asp#image_descriptor_block
                        image_count += 1
                        if image_count > 1:
                            # if we've seen more than one image it's animated
                            # so we're done
                            ret = True
                            break

                        # total size is 10 bytes, we already have the first
                        # byte so let's grab the other 9 bytes
                        image_descriptor = fp.read(9)
                        skip_color_table(fp, image_descriptor[-1])
                        skip_image_data(fp)

                    b = ord(fp.read(1))

        return ret

    def open_text(self, *args, **kwargs):
        raise NotImplementedError()
    def read_text(self, *args, **kwargs):
        raise NotImplementedError()
    def write_text(self, *args, **kwargs):
        raise NotImplementedError()
    def append_text(self, *args, **kwargs):
        raise NotImplementedError()
ImagePath = Imagepath


class TempPath(object):
    basedir = None

    @property
    def relpath(self):
        return self.relative_to(self.basedir)

    @property
    def relparts(self):
        parts = self.splitparts(self.relpath)
        return parts

    @classmethod
    def gettempdir(cls):
        """return the system temp directory"""
        # compensate for macOS setting it's temporary dictory to a symlink for
        # some reason by expanding symlinks
        return os.path.realpath(tempfile.gettempdir())

    @classmethod
    def normparts(cls, *parts, **kwargs):
        # Path sets a "" part to "/" by default but temp paths have to be more
        # explicit, empty parts are ignored
        parts = list(filter(None, parts))
        return super().normparts(*parts, **kwargs)

    @classmethod
    def mktempdir(cls, **kwargs):
        """pass through for tempfile.mkdtemp, this is here so it can be
        overridden in child classes and customized

        https://docs.python.org/3/library/tempfile.html#tempfile.mkdtemp

        :param **kwargs:
            - prefix
            - suffix
            - dir
        :returns: str, the directory path
        """
        if "dir" not in kwargs:
            kwargs["dir"] = cls.gettempdir()

        return tempfile.mkdtemp(**kwargs)

    @classmethod
    def get_basename(cls, ext="", prefix="", name="", suffix="", **kwargs):
        """return just a valid file name

        :param ext: string, the extension you want the file to have
        :param prefix: string, this will be the first part of the file's name
        :param suffix: string, if you want the last bit to be posfixed with
            something
        :param name: string, the name you want to use (prefix will be added to
            the front of the name and ext will be added to the end of the name)
        :returns: string, the random filename
        """
        # compensate for .stripparts() returing "/" for ""
        name = name.strip("/")

        if not name and kwargs.get("autogen_name", True):
            name = "".join(random.sample(
                String.ASCII_LETTERS,
                random.randint(
                    kwargs.get("min_name_size", 3),
                    kwargs.get("max_name_size", 11)
                )
            )).lower()

        return super().get_basename(
            ext=ext,
            prefix=prefix,
            name=name,
            suffix=suffix,
            **kwargs
        )

    @classmethod
    def tempdir_class(cls):
        return TempDirpath

    @classmethod
    def tempfile_class(cls):
        return TempFilepath

    @classmethod
    def create_tempfile(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.tempfile_class()
        return cls.create(*parts, **kwargs)

    @classmethod
    def create_tempdir(cls, *parts, **kwargs):
        kwargs["path_class"] = cls.tempdir_class()
        return cls.create(*parts, **kwargs)


# !!! Ripped from herd.path
class TempDirpath(TempPath, Dirpath):
    """Create a temporary directory

    https://docs.python.org/3/library/tempfile.html

    :Example:
        d = TempDirpath("foo", "bar")
        print(d) # $TMPDIR/foo/bar
    """
    @classmethod
    def normparts(cls, *parts, **kwargs):
        suffix = kwargs.pop("suffix", kwargs.pop("postfix", ""))
        prefix = kwargs.pop("prefix", "")
        basedir = kwargs.pop("dir", "")

        # because .mktempdir() creates a subfolder already, we don't want to
        # auto-generate a basename while normalizing the parts
        parts = super().normparts(*parts, autogen_name=False, **kwargs)

        if basedir:
            parts = [basedir] + parts

        else:
            create_dir = True
            if parts:
                path = cls.joinparts(*parts)
                if os.path.isdir(path) or cls.is_absolute_path(path):
                    create_dir = False

            if create_dir:
                basedir = cls.mktempdir(
                    suffix=suffix,
                    prefix=prefix,
                )
                parts = [basedir] + parts

        return parts

    @classmethod
    def create_as(cls, instance, **kwargs):
        kwargs.setdefault("touch", True)
        instance.basedir = kwargs["parts"][0]
        instance = super().create_as(instance, **kwargs)
        return instance
Dirtemp = TempDirpath
Tempdir = TempDirpath
TempDirPath = TempDirpath


class TempFilepath(TempPath, Filepath):
    """Create a temporary file

    :Example:
        f = TempFilepath("foo", "bar.ext")
        print(f) # $TMPDIR/foo/bar.ext
    """
    @classmethod
    def normparts(cls, *parts, **kwargs):
        basedir = kwargs.pop("dir", "")
        parts = super().normparts(*parts, **kwargs)
        if basedir:
            parts = [cls.create_tempdir(dir=basedir)] + parts

        else:
            # check to see if parts is a complete path
            path = cls.joinparts(*parts)
            if not os.path.isfile(path) and not cls.is_absolute_path(path):
                parts = [cls.create_tempdir()] + parts

        return parts

    @classmethod
    def create_as(cls, instance, **kwargs):
        kwargs.setdefault("touch", True)
        instance.basedir = kwargs["parts"][0]
        instance = super().create_as(instance, **kwargs)

        data = kwargs.pop("data", kwargs.pop("contents", None))
        if data:
            instance.write(data, **kwargs)

        return instance

    def prepare_text(self, data, **kwargs):
        """Wraps parent's .prepare_text to allow the addition of a header and
        footer to data

        There have been many times where I want to add standard headers and
        footers and this just standardizes that behavior instead of it being
        bespoke each time

        :param data: str, the text that will be written
        :param **kwargs: keywords, you can pass in encoding here
            * header: str, this will be added to the beginning of data,
              separated by a newline
            * footer: str, this will be added to the end of data, separated by
              a newline
        :returns: tuple[str, str, str], (data, encoding, errors)
        """
        header = kwargs.pop("header", "")
        if header:
            data = header + "\n" + data

        footer = kwargs.pop("footer", "")
        if footer:
            data = data + "\n" + footer

        return super().prepare_text(data, **kwargs)
Filetemp = TempFilepath
Tempfile = TempFilepath
TempFilePath = TempFilepath


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
        :returns: boolean, True if file has been modified after the seconds
            back
        """
        now = Datetime()
        then = self.modified()
        timedelta_kwargs["seconds"] = seconds
        td_check = datetime.timedelta(**timedelta_kwargs)
        #pout.v(now, td_check, now - td_check, then)
        return (now - td_check) < then
CachePath = Cachepath


class Sentinel(Cachepath):
    """Creates a file after the first failed boolean check, handy when you only
    want to check things at certain intervals

    :Example:
        s = Sentinel("foo")
        if not s:
            # do something you don't want to do all the time
        if not s:
            # this won't ever be ran because the last `if not s` check will
            # have created the sentinel file
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


class UrlFilepath(Cachepath):
    """Retrieve a file from a url and save it as a local file

    :Example:
        p = UrlFilepath("https://example.com/foo.txt")
        print(p) # CACHE_DIR/foo.txt

        p = UrlFilepath("https://example.com/bar/foo/che.txt", "foo.txt")
        print(p) # ./foo.txt

    this was moved here from Glyph's codebase on March 7, 2022
    """
    http_client = HTTPClient
    """The http client this will use to retrieve the file. If you want to
    completely ignore this property just override the .fetch method"""

    def __new__(cls, url, path="", **kwargs):
        url = Url(url)

        if path:
            p = cls.create_file(path)
            # the path directory takes precedence over a passed in dir
            kwargs["dir"] = p.directory
            kwargs["prefix"] = ""
            keys = cls.splitparts(p.basename)

        else:
            keys = url.parts

        instance = super().__new__(cls, *keys, **kwargs)
        instance.url = url
        instance.fetched = False

        if not instance:
            instance.fetch()

        return instance

    def fetch(self):
        """Fetch the file from a url and save it in a local path, you can call
        this method anytime to refresh the file

        this method will set self.fetched to True
        """
        # we need to fetch the file using url and save it to filepath
        logger.debug("Fetching {} to {}".format(self.url, self))

        c = self.http_client(stream=True)
        r = c.get(self.url)
        if r.status_code >= 400:
            raise IOError(r.status_code)

        try:
            fp = None
            # we use the encoding the server returned to decide if we should
            # treat this file as binary or text. Text should get decoded to
            # unicode in the response object so then we will write it to the
            # file using self.encoding
            encoding = r.encoding
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: # filter out keep-alive new chunks
                    if encoding:
                        data, data_encoding, errors = self.prepare_text(chunk)

                    else:
                        data, data_encoding, errors = self.prepare_bytes(chunk)

                    if not fp:
                        if encoding:
                            fp = self.open(
                                mode="w+",
                                encoding=data_encoding,
                                errors=errors
                            )
                        else:
                            fp = self.open("wb+")

                    fp.write(chunk)

        finally:
            if fp:
                fp.close()


        self.fetched = True

    def write(self, data):
        """Restore Cachepath parent class functionality"""
        return self.as_file().write(data)

    def read(self):
        raise NotImplementedError()
UrlFilePath = UrlFilepath
Urlpath = UrlFilepath
UrlPath = UrlFilepath


class SitePackagesDirpath(Dirpath):
    """Finds the site-packages directory and sets the value of this string to
    that path

    !!! Ripped from pyt.path which was ripped from pout.path
    """
    def __new__(cls):
        basepath = cls._basepath
        if not basepath:
            try:
                paths = site.getsitepackages()
                basepath = paths[0] 
                logger.debug(
                    f"Found site-packages directory {basepath}"
                    " using site.getsitepackages"
                )

            except AttributeError:
                # we are probably running this in a virtualenv, so let's try a
                # different approach: try and brute-force discover it since
                # it's not defined where it should be defined
                sitepath = os.path.join(
                    os.path.dirname(site.__file__),
                    "site-packages"
                )
                if os.path.isdir(sitepath):
                    basepath = sitepath
                    logger.debug(
                        f"Found site-packages directory {basepath}"
                        " using site.__file__"
                    )

                else:
                    for path in sys.path:
                        if path.endswith("site-packages"):
                            basepath = path
                            logger.debug(
                                "Found site-packages directory {basepath}"
                                " using sys.path"
                            )
                            break

                    if not basepath:
                        for path in sys.path:
                            if path.endswith("dist-packages"):
                                basepath = path
                                logger.debug(
                                    f"Found dist-packages directory {basepath}"
                                    " using sys.path"
                                )
                                break

        if not basepath:
            raise IOError("Could not find site-packages directory")

        return super(SitePackagesDirpath, cls).__new__(cls, basepath)


class DataDirpath(Dirpath):
    """Wrapper class to make working with the module's data directory easier to
    work with

    * https://stackoverflow.com/questions/6028000/how-to-read-a-static-file-from-inside-a-python-package/58941536#58941536
    * https://setuptools.pypa.io/en/latest/userguide/datafiles.html
    * https://stackoverflow.com/questions/779495/access-data-in-package-subdirectory
    """
    def __new__(cls, modpath=""):
        if not modpath:
            modpath = __name__.split(".")[0]
        base_dir = os.path.dirname(sys.modules[modpath].__file__)
        return super().__new__(cls, base_dir, "data")

