# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.path import (
    Path,
    Dirpath,
    Filepath,
)

from . import TestCase as BaseTestCase, testdata

class TestCase(BaseTestCase):
    path_class = Path

    def create_path(self, *parts, **kwargs):
        kwargs.setdefault("path_class", self.path_class)
        if not parts:
            exists = kwargs.pop("exists", True)
            if isinstance(self.path_class, Dirpath):
                contents = kwargs.pop("contents", {})
                if exists:
                    if contents:
                        parts = [testdata.create_dirs(contents)]
                    else:
                        parts = [testdata.create_dir()]

                else:
                    parts = [testdata.get_dir(testdata.get_ascii())]
            else:
                if exists:
                    parts = [testdata.create_file(contents=kwargs.pop("contents", ""))]

                else:
                    parts = [testdata.get_file()]

        return Path.create(*parts, **kwargs)


class PathTest(TestCase):
    def test_join(self):
        r = Path.join("", "foo", "bar")
        self.assertEqual('/foo/bar', r)

        r = Path.join(["foo", "bar"])
        self.assertEqual('foo/bar', r)

        r = Path.join("/foo", "/bar/", "/che")
        self.assertEqual('/foo/bar/che', r)

        r = Path.join(["foo", "bar"], "che")
        self.assertEqual('foo/bar/che', r)

    def test_root(self):
        p = self.create_path("/foo/bar")
        self.assertEqual("/", p.root)

    def test_parent(self):
        p = self.create_path("/foo/bar/che")
        parent = p.parent
        self.assertEqual("/foo/bar", parent)
        self.assertEqual("/foo", parent.parent)
        self.assertEqual("/", parent.parent.parent)
        self.assertEqual("/", parent.parent.parent.parent)

    def test_parents(self):
        p = self.create_path("/foo/bar/che")
        parents = p.parents
        self.assertEqual(3, len(parents))
        self.assertEqual("/foo/bar", parents[0])
        self.assertEqual("/foo", parents[1])
        self.assertEqual("/", parents[2])

    def test_name(self):
        p = self.create_path("/dir/fileroot.ext")
        self.assertEqual("fileroot.ext", p.name)
        self.assertEqual("fileroot.ext", p.basename)

        p = self.create_path("/dir/fileroot.ext1.ext2")
        self.assertEqual("fileroot.ext1.ext2", p.name)

    def test_fileroot(self):
        p = self.create_path("/dir/fileroot.ext")
        self.assertEqual("fileroot", p.fileroot)
        self.assertEqual("fileroot", p.stem)

        p = self.create_path("/dir/fileroot.ext1.ext2")
        self.assertEqual("fileroot.ext1", p.fileroot)

    def test_ext_and_suffix(self):
        p = self.create_path("fileroot.ext")

        self.assertEqual("ext", p.ext)
        self.assertEqual("ext", p.extension)
        self.assertEqual(".ext", p.suffix)

        p = self.create_path("fileroot")
        self.assertEqual("", p.ext)
        self.assertEqual("", p.suffix)

    def test_suffixes(self):
        p = self.create_path("fileroot.ext1.ext2")
        self.assertEqual([".ext1", ".ext2"], p.suffixes)

        p = self.create_path("fileroot")
        self.assertEqual([], p.suffixes)

    def test_joinpath(self):
        p = self.create_path("/foo/bar")

        p2 = p.joinpath("che", "baz")
        self.assertEqual("/foo/bar/che/baz", p2)

    def test_match(self):
        self.assertTrue(self.create_path('/a.py').match('/*.py'))

        self.assertTrue(self.create_path('/a/b/c.py').match('b/*.py'))

        self.assertFalse(self.create_path('/a/b/c.py').match('/a/*.py'))
        self.assertFalse(self.create_path('/a/b/c.py').match('a/*.py'))

        self.assertFalse(self.create_path('foob/c.py').match('b/*.py'))

        self.assertTrue(self.create_path('a/b.py').match('*.py'))

        self.assertFalse(self.create_path('a/b.py').match('/*.py'))

    def test_is_root(self):
        p = self.create_path("/")
        self.assertTrue(p.is_root())

        p = self.create_path("/foo")
        self.assertFalse(p.is_root())

    def test_relative_to(self):
        p = self.create_path("/etc/passwd")

        self.assertEqual("etc/passwd", p.relative_to("/"))
        self.assertEqual("passwd", p.relative_to("/etc"))

        with self.assertRaises(ValueError):
            p.relative_to("/usr")

    def test_with_name(self):
        p = self.create_path("/foo/bar/fileroot.ext")

        self.assertEqual("/foo/bar/che.baz", p.with_name("che.baz"))

        p = self.create_path("/")
        with self.assertRaises(ValueError):
            p.with_name("foo.bar")

    def test_with_suffix(self):
        p = self.create_path("/foo/bar.ext")
        self.assertEqual("/foo/bar.che", p.with_suffix("che"))

        p = self.create_path("/foo/bar")
        self.assertEqual("/foo/bar.che", p.with_suffix(".che"))

        p = self.create_path("/foo/bar.ext")
        self.assertEqual("/foo/bar", p.with_suffix(""))


class DirpathTest(TestCase):
    path_class = Dirpath

    def test_parts(self):
        path = "/foo/bar/che"
        p = self.create_path(path)
        parents = p.parents
        pout.v(parents)

        return



        path = testdata.create_dir()

        pout.v(path)

        p = self.create_path(path)
        pout.v(p, type(p))


class FilepathTest(TestCase):
    path_class = Filepath

    def test_stat(self):
        p = self.create_path()
        r = p.stat()
        self.assertLess(0, r.st_atime)
        self.assertLess(0, r.st_mtime)

    def test_group(self):
        p = self.create_path()
        r = p.group()
        self.assertNotEqual("", r)

    def test_exists(self):
        p = self.create_path()
        self.assertTrue(p.exists())
        self.assertTrue(p.is_file())

        p = self.create_path("/foo/bar")
        self.assertFalse(p.exists())
        self.assertFalse(p.is_file())

    def test_mv_file_to_file(self):

        contents = "this is the content"
        p = self.create_path(contents=contents)
        p2 = self.create_path(exists=False)

        self.assertTrue(p.exists())
        self.assertFalse(p2.exists())

        p3 = p.mv(p2)
        self.assertTrue(p3.exists())
        self.assertFalse(p.exists())
        self.assertEqual(contents, p3.read_text())





