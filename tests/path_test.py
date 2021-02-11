# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import time

from datatypes.compat import *
from datatypes.path import (
    Path,
    Dirpath,
    Filepath,
    Archivepath,
    TempDirpath,
    TempFilepath,
    Cachepath,
    Sentinel,
)

from . import TestCase, testdata


class PathTest(TestCase):
    path_class = Path

    def create(self, *parts, **kwargs):
        kwargs.setdefault("path_class", self.path_class)

        path = os.path.join(*parts) if parts else ""

        contents = kwargs.pop("contents", {})
        exists = kwargs.pop("exists", True if contents else False if path else True)
        if issubclass(kwargs["path_class"], Dirpath):
            if contents:
                if isinstance(contents, Mapping):
                    parts = [testdata.create_files(contents, tmpdir=path)]

                elif isinstance(contents, Iterable):
                    parts = [testdata.create_dirs(contents, tmpdir=path)]

                else:
                    raise ValueError("Unknown contents for directory")

            else:
                if path.startswith("/"):
                    parts = [path]
                else:
                    parts = [testdata.get_dir(path if path else testdata.get_filename())]

        else:
            if contents:
                parts = [testdata.create_file(path, contents=contents)]

            else:
                if path.startswith("/"):
                    parts = [path]
                else:
                    parts = [testdata.get_file(path)]

        p = Path.create(*parts, **kwargs)
        if exists and not p.exists():
            p.touch()

        return p

    def create_path(self, *parts, **kwargs):
        kwargs.setdefault("path_class", Path)
        return self.create(*parts, **kwargs)

    def create_dir(self, *parts, **kwargs):
        kwargs.setdefault("path_class", Dirpath)
        return self.create(*parts, **kwargs)

    def create_file(self, *parts, **kwargs):
        kwargs.setdefault("path_class", Filepath)
        return self.create(*parts, **kwargs)

    def test_inferrence(self):
        dp = TempDirpath()
        p = Path(dp.path)
        self.assertTrue(isinstance(p, p.dir_class()))

        fp = TempFilepath()
        p = Path(fp)
        self.assertTrue(isinstance(p, p.file_class()))

        fp = "/some/non/existant/random/path.ext"
        p = Path(fp)
        self.assertTrue(isinstance(p, p.file_class()))

        pp = "/some/non/existant/path"
        p = Path(pp)
        self.assertTrue(isinstance(p, p.path_class()))

        fp = "/some/non/existant/random/path.ext"
        p = Path(fp, path_class=p.path_class())
        self.assertTrue(isinstance(p, p.path_class()))

    def test_root(self):
        p = self.create("/foo/bar")
        self.assertEqual("/", p.root)

    def test_parent(self):
        p = self.create("/foo/bar/che")
        parent = p.parent
        self.assertEqual("/foo/bar", parent)
        self.assertEqual("/foo", parent.parent)
        self.assertEqual("/", parent.parent.parent)
        self.assertEqual("/", parent.parent.parent.parent)

    def test_parents(self):
        p = self.create("/foo/bar/che")
        parents = p.parents
        self.assertEqual(3, len(parents))
        self.assertEqual("/foo/bar", parents[0])
        self.assertEqual("/foo", parents[1])
        self.assertEqual("/", parents[2])

    def test_name(self):
        p = self.create("/dir/fileroot.ext")
        self.assertEqual("fileroot.ext", p.name)
        self.assertEqual("fileroot.ext", p.basename)

        p = self.create("/dir/fileroot.ext1.ext2")
        self.assertEqual("fileroot.ext1.ext2", p.name)

    def test_fileroot(self):
        p = self.create("/dir/fileroot.ext")
        self.assertEqual("fileroot", p.fileroot)
        self.assertEqual("fileroot", p.stem)

        p = self.create("/dir/fileroot.ext1.ext2")
        self.assertEqual("fileroot.ext1", p.fileroot)

    def test_ext_and_suffix(self):
        p = self.create("fileroot.ext")

        self.assertEqual("ext", p.ext)
        self.assertEqual("ext", p.extension)
        self.assertEqual(".ext", p.suffix)

        p = self.create("fileroot")
        self.assertEqual("", p.ext)
        self.assertEqual("", p.suffix)

    def test_suffixes(self):
        p = self.create("fileroot.ext1.ext2")
        self.assertEqual([".ext1", ".ext2"], p.suffixes)

        p = self.create("fileroot")
        self.assertEqual([], p.suffixes)

    def test_match(self):
        self.assertTrue(self.create('/a.py').match('/*.py'))

        self.assertTrue(self.create('/a/b/c.py').match('b/*.py'))

        self.assertFalse(self.create('/a/b/c.py').match('/a/*.py'))
        self.assertFalse(self.create('/a/b/c.py').match('a/*.py'))

        self.assertFalse(self.create('foob/c.py').match('b/*.py'))

        self.assertTrue(self.create('a/b.py').match('*.py'))

        self.assertFalse(self.create('a/b.py').match('/*.py'))

    def test_is_root(self):
        p = self.create("/")
        self.assertTrue(p.is_root())

        p = self.create("/foo")
        self.assertFalse(p.is_root())

    def test_relative_to(self):
        p = self.create("/etc/passwd")

        self.assertEqual("etc/passwd", p.relative_to("/"))
        self.assertEqual("passwd", p.relative_to("/etc"))

        with self.assertRaises(ValueError):
            p.relative_to("/usr")

    def test_with_name(self):
        p = self.create("/foo/bar/fileroot.ext")

        self.assertEqual("/foo/bar/che.baz", p.with_name("che.baz"))

        p = self.create("/")
        with self.assertRaises(ValueError):
            p.with_name("foo.bar")

    def test_with_suffix(self):
        p = self.create("/foo/bar.ext")
        self.assertEqual("/foo/bar.che", p.with_suffix("che"))

        p = self.create("/foo/bar")
        self.assertEqual("/foo/bar.che", p.with_suffix(".che"))

        p = self.create("/foo/bar.ext")
        self.assertEqual("/foo/bar", p.with_suffix(""))

    def test_parts(self):
        path = "/foo/bar/che"
        p = self.create(path)
        parts = p.parts
        self.assertEqual("/", parts[0])
        self.assertEqual("che", parts[-1])
        self.assertEqual("bar", parts[-2])
        self.assertEqual("foo", parts[-3])

    def test_join(self):
        r = Path.join("", "foo", "bar")
        self.assertEqual('/foo/bar', r)

        r = Path.join(["foo", "bar"])
        self.assertEqual('foo/bar', r)

        r = Path.join("/foo", "/bar/", "/che")
        self.assertEqual('/foo/bar/che', r)

        r = Path.join(["foo", "bar"], "che")
        self.assertEqual('foo/bar/che', r)

    def test_split(self):
        ps = Path.split("\\foo\\bar", "\\che\\")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.split("foo", None)
        self.assertEqual(["foo", "None"], ps)

        ps = Path.split(["/foo", "bar"], "che", ["/baz", "boom"])
        self.assertEqual(["/", "foo", "bar", "che", "baz", "boom"], ps)

        ps = Path.split("/foo", "/bar/", "/che")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.split("", "foo", "bar")
        self.assertEqual(["/", "foo", "bar"], ps)

        ps = Path.split("/che/baz", "foo", "bar")
        self.assertEqual(["/", "che", "baz", "foo", "bar"], ps)

        ps = Path.split("foo", self.create_file("/", "bar", "che"), "baz")
        self.assertEqual(["foo", "bar", "che", "baz"], ps)

        ps = Path.split(["foo/bar", "che"], "baz")
        self.assertEqual(["foo", "bar", "che", "baz"], ps)

        ps = Path.split("/foo/bar", "che")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.split("/")
        self.assertEqual(["/"], ps)

        ps = Path.split("")
        self.assertEqual(["/"], ps)

        ps = Path.split()
        self.assertEqual([], ps)

        ps = Path.split([])
        self.assertEqual([], ps)


class _PathTestCase(PathTest):
    def test_stat(self):
        p = self.create()
        r = p.stat()
        self.assertLess(0, r.st_atime)
        self.assertLess(0, r.st_mtime)

    def test_group(self):
        p = self.create()
        r = p.group()
        self.assertNotEqual("", r)

    def test_exists(self):
        p = self.create()
        self.assertTrue(p.exists())

    def test_touch(self):
        p = self.create()
        self.assertTrue(p.exists())
        p.touch()
        with self.assertRaises(OSError):
            p.touch(exist_ok=False)

        p = self.create(exists=False)
        self.assertFalse(p.exists())
        p.touch()
        self.assertTrue(p.exists())


class DirpathTest(_PathTestCase):
    path_class = Dirpath

    def test__normalize_add_paths(self):
        ds = self.path_class._normalize_add_paths({"foo": ["bar", "che"]}, parts=["prefix"])
        self.assertEqual(2, len(ds))
        self.assertEqual(["prefix", "foo", "bar"], ds[0][0])
        self.assertEqual(None, ds[1][1])

        ds = self.path_class._normalize_add_paths(["foo", "bar"], parts=["prefix"])
        self.assertEqual(2, len(ds))
        self.assertEqual(["prefix", "foo"], ds[0][0])
        self.assertEqual(None, ds[1][1])

        ds = self.path_class._normalize_add_paths({"foo": None}, parts=["prefix"])
        self.assertEqual(["prefix", "foo"], ds[0][0])
        self.assertEqual(None, ds[0][1])

        ds = self.path_class._normalize_add_paths({
            "foo": {
                "bar": {}
            }
        }, parts=["prefix"])
        s = set(["prefix.foo.bar"])
        for parts, contents in ds:
            self.assertTrue(".".join(parts) in s)
            self.assertIsNone(contents)

        ds = self.path_class._normalize_add_paths({
            "foo": {
                "bar": "def ident(): return 'foo.bar'",
                "che": {
                    "baz": "def ident(): return 'foo.che'",
                }
            }
        }, parts=["prefix"])
        s = set(["prefix.foo.bar", "prefix.foo.che.baz"])
        for parts, contents in ds:
            self.assertTrue(".".join(parts) in s)

    def test_joinpath(self):
        p = self.create("/foo/bar")

        p2 = p.joinpath("che", "baz")
        self.assertTrue(p2.endswith("/foo/bar/che/baz"))

    def test_iterdir(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.iterdir():
            count += 1
        self.assertEqual(4, count)

    def test_iterdirs(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for dp in p.iterdirs():
            count += 1
        self.assertEqual(3, count)

    def test_iterfiles(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.iterfiles():
            count += 1
        self.assertEqual(4, count)

    def test_glob(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "goo/gap.py": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.glob("*.txt"):
            self.assertTrue(fp.endswith(".txt"))
            count += 1
        self.assertEqual(2, count)

    def test_rglob(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "goo/gap.py": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.rglob("*.txt"):
            self.assertTrue(fp.endswith(".txt"))
            count += 1
        self.assertEqual(4, count)

    def test_reglob(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "goo/gap.py": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.reglob(r"\.txt$"):
            self.assertTrue(fp.endswith(".txt"))
            count += 1
        self.assertEqual(4, count)

    def test_rm(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })

        self.assertTrue(p.exists())
        self.assertLess(0, p.count())

        p.rm()
        self.assertFalse(p.exists())

        p.rm() # no error raised means it worked

    def test_clear(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })

        self.assertTrue(p.exists())
        self.assertLess(0, p.count())

        p.clear()
        self.assertTrue(p.exists())
        self.assertEqual(0, p.count())

    def test_dirpath_clear(self):
        d = testdata.create_dir()
        foo_f = d.create_file("foo.txt", "foo")
        bar_f = d.create_file("bar/bar.txt", "bar")
        che_d = d.create_dir("che")

        self.assertTrue(foo_f.exists())
        self.assertTrue(bar_f.exists())
        self.assertTrue(che_d.exists())

        d.clear()
        self.assertFalse(foo_f.exists())
        self.assertFalse(bar_f.exists())
        self.assertFalse(che_d.exists())
        self.assertEqual(0, len(list(d.files())))

    def test_rmdir(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })

        self.assertTrue(p.exists())
        self.assertLess(0, p.count())

        with self.assertRaises(OSError):
            p.rmdir()

        p.clear()
        self.assertTrue(p.exists())
        self.assertEqual(0, p.count())

        p.rmdir()
        self.assertFalse(p.exists())

    def test_mv_noexist(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertLess(0, p.count())

        target = self.create_dir("mv_no", "mv_noexist", exists=False)
        self.assertFalse(target.exists())

        target = p.mv(target)
        self.assertFalse(p.exists())
        self.assertTrue(target.exists())
        self.assertLess(0, target.count())

    def test_mv_exist(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertLess(0, p.count())

        target = self.create_dir()
        self.assertTrue(target.exists())

        dest = p.mv(target)
        self.assertFalse(p.exists())
        self.assertTrue(dest.exists())
        self.assertNotEqual(target, dest)
        self.assertLess(0, target.count())

    def test_mv_notempty(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertLess(0, p.count())

        target = self.create_dir()
        dest = self.create_dir(target, p.basename, contents={"bar.txt": testdata.get_lines()})

        self.assertTrue(target.exists())
        self.assertTrue(dest.exists())

        with self.assertRaises(OSError):
            p.mv(target)

    def test_mv_empty(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertLess(0, p.count())

        target = self.create_dir()
        dest = self.create_dir(target, p.basename, exists=True)
        self.assertEqual(0, dest.count())

        self.assertTrue(target.exists())
        self.assertTrue(dest.exists())

        dest = p.mv(target)
        self.assertLess(0, dest.count())
        self.assertFalse(p.exists())

    def test_cp_noexist(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertLess(0, p.count())

        target = self.create_dir(exists=False)
        self.assertFalse(target.exists())

        dest = p.cp(target)

        self.assertTrue(p.exists())
        self.assertTrue(dest.exists())
        self.assertLess(0, p.count())
        self.assertLess(0, dest.count())

    def test_cp_exist(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines()
        })
        self.assertFalse(p.empty())

        target = self.create_dir()
        self.assertTrue(target.exists())

        dest = p.cp(target)
        self.assertTrue(p.exists())
        self.assertTrue(dest.exists())
        self.assertNotEqual(target, dest)
        self.assertLess(0, p.count())
        self.assertLess(0, target.count())

    def test_cp_notempty(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
        })
        self.assertLess(0, p.count())

        target = self.create_dir()
        dest = self.create_dir(target, p.basename, contents={"bar.txt": testdata.get_lines()})

        self.assertTrue(target.exists())
        self.assertTrue(dest.exists())

        p.cp(target)
        self.assertEqual(1, p.count(recursive=True))
        self.assertEqual(2, dest.count(recursive=True))

    def test_copy_to(self):
        """https://github.com/Jaymon/testdata/issues/30"""
        source_d = testdata.create_files({
            "foo.txt": testdata.get_words(),
            "bar/che.txt": testdata.get_words(),
        })
        dest_d = testdata.create_dir()

        source_d.copy_to(dest_d)
        self.assertTrue("foo.txt" in dest_d)
        self.assertTrue("bar/che.txt" in dest_d)

        source_f = testdata.create_file("foo.txt", testdata.get_words())
        dest_f = testdata.get_file()
        self.assertFalse(dest_f.exists())
        source_f.copy_to(dest_f)
        self.assertEqual(source_f.contents(), dest_f.contents())


class FilepathTest(_PathTestCase):
    path_class = Filepath

    def test_permissions(self):
        f = testdata.create_file("permissions.txt")
        if is_py2:
            self.assertRegexpMatches(f.permissions, r"0[0-7]{3}")
        else:
            self.assertRegex(f.permissions, r"0[0-7]{3}")

        f.chmod("0755")
        self.assertEqual("0755", f.permissions)

        f.chmod(644)
        self.assertEqual("0644", f.permissions)

        f.chmod("655")
        self.assertEqual("0655", f.permissions)

        f.chmod(655)
        self.assertEqual("0655", f.permissions)

        f.chmod(500)
        self.assertEqual("0500", f.permissions)

    def test_unlink(self):

        p = self.create()
        self.assertTrue(p.exists())

        p.unlink(missing_ok=False)
        self.assertFalse(p.exists())

        with self.assertRaises(OSError):
            p.unlink(missing_ok=False)

        p.unlink(missing_ok=True)
        p.rm()
        p.delete()
        p.remove()

    def test_cp_file_to_file(self):
        contents = "this is the content"
        p = self.create(contents=contents)
        p2 = self.create(exists=False)

        self.assertTrue(p.exists())
        self.assertFalse(p2.exists())

        p3 = p.cp(p2)
        self.assertTrue(p3.exists())
        self.assertTrue(p.exists())
        self.assertEqual(contents, p3.read_text())

    def test_cp_file_to_dir(self):
        contents = "this is the content"
        fp = self.create(contents=contents)
        dp = testdata.create_dir()

        self.assertTrue(fp.exists())
        self.assertTrue(dp.exists())

        fp2 = fp.cp(dp)
        self.assertTrue(fp2.exists())
        self.assertTrue(fp.exists())
        self.assertTrue(fp.basename, fp2.basename)
        self.assertEqual(contents, fp2.read_text())

    def test_mv_file_to_file(self):
        contents = "this is the content"
        p = self.create(contents=contents)
        p2 = self.create(exists=False)

        self.assertTrue(p.exists())
        self.assertFalse(p2.exists())

        p3 = p.mv(p2)
        self.assertTrue(p3.exists())
        self.assertFalse(p.exists())
        self.assertEqual(contents, p3.read_text())

    def test_mv_file_to_dir(self):
        contents = "this is the content"
        fp = self.create(contents=contents)
        dp = testdata.create_dir()

        self.assertTrue(fp.exists())
        self.assertTrue(dp.exists())

        p3 = fp.mv(dp)
        self.assertTrue(p3.exists())
        self.assertFalse(fp.exists())
        self.assertTrue(fp.basename, p3.basename)
        self.assertEqual(contents, p3.read_text())

    def test_head_tail(self):
        count = 10
        p = self.create(contents=testdata.get_lines(21))
        hlines = p.head(count)
        self.assertEqual(count, len(hlines))

        tlines = p.tail(count)
        self.assertEqual(count, len(tlines))
        self.assertNotEqual("\n".join(hlines), "\n".join(tlines))

    def test_checksum(self):
        contents = "foo bar che"
        path1 = self.create(contents=contents)
        h1 = path1.checksum()
        self.assertNotEqual("", h1)

        path2 = self.create(contents=contents)
        h2 = path2.checksum()
        self.assertNotEqual("", h2)

        self.assertEqual(h1, h2)

    def test_clear(self):
        contents = "foo bar che"
        p = self.create(contents=contents)
        self.assertLess(0, p.count())

        p.clear()
        self.assertEqual(0, p.count())

    def test_contextmanager(self):
        p = self.create()

        contents = testdata.get_lines()
        with p as fp:
            fp.write(contents)
        self.assertEqual(contents, p.read_text())

        contents = testdata.get_lines()
        with p("w+") as fp:
            fp.write(contents)
        self.assertEqual(contents, p.read_text())

    def test_empty(self):
        p = self.create()

        self.assertTrue(p.exists())
        self.assertTrue(p.empty())

        p.write_text(testdata.get_words())
        self.assertFalse(p.empty())

        p.delete()
        self.assertFalse(p.exists())
        self.assertTrue(p.empty())


class ArchivepathTest(TestCase):
    path_class = Archivepath

    def test_add_zip(self):
        self.skip_test("API is not finalized")
        zp = self.create("foo.zip")
        fp = self.create_file(contents=testdata.get_lines())
        dp = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
        })

        zp.add(fp)

        zp.add(dp)

        for n in zp:
            pout.v(n)

        pout.v(fp, zp, dp)

    # TODO: test other formats like .tar.gz



class TempDirpathTest(TestCase):
    def test_children(self):
        d = TempDirpath()
        ds = d.add({
            "bar/che.txt": "che.txt data",
            "foo.txt": "foo.txt data",
        })
        self.assertEqual(3, len(list(d.children())))
        self.assertEqual(2, len(list(d.children("*.txt"))))
        self.assertEqual(1, len(list(d.children("che.txt"))))
        self.assertEqual(1, len(list(d.children("bar/che.txt"))))
        self.assertEqual(1, len(list(d.children("bar"))))

    def test_has(self):
        d = TempDirpath()
        self.assertFalse(d.has())

        ds = d.add({
            "bar/che.txt": "che.txt data",
            "foo.txt": "foo.txt data",
        })
        self.assertTrue(d.has("che.txt"))
        self.assertTrue(d.has("bar"))
        self.assertTrue(d.has("bar/che.txt"))
        self.assertFalse(d.has("bar/che"))
        self.assertTrue(d.has("che.*"))
        self.assertTrue(d.has(lambda p: p.endswith(".txt")))
        self.assertTrue(d.has())

    def test_division(self):
        d = TempDirpath()
        d2 = d.child("foo/bar")
        d3 = d / "foo/bar"
        self.assertEqual(d2, d3)

    def test_child_1(self):
        d = TempDirpath()
        d2 = d.child("foo", "bar")
        self.assertTrue(isinstance(d2, Path))

        d.add_dir(["foo", "bar"])
        d2 = d.child("foo", "bar")
        self.assertTrue(isinstance(d2, Dirpath))

        f = d.add_file("foo/bar.txt")
        f2 = d.child("foo/bar.txt")
        self.assertTrue(isinstance(f2, Filepath))

        f2 = d.child("foobar.txt")
        self.assertTrue(isinstance(f2, Path))

        d2 = d.child("barfoo.txt/")
        self.assertTrue(isinstance(d2, Path))

    def test_add_1(self):
        """Test the add directories functionality"""
        d = TempDirpath()
        ts = [
            "\\foo\\bar",
            "/foo1/bar1",
            "/foo2/bar2/",
            "foo3/bar3",
            "foo4/bar4/",
            "",
            "~",
            None
        ]
        ds = d.add(ts)
        for path in ds:
            self.assertTrue(os.path.isdir(path))

    def test_add_2(self):
        """Test the add files functionality"""
        d = TempDirpath()
        ts = {
            "foo/1.txt": testdata.get_words(),
            "foo/2.txt": testdata.get_words(),
            "/bar/3.txt": testdata.get_words(),
            "/bar/che/4.txt": testdata.get_words(),
        }
        ds = d.add(ts)
        count = 0
        for path in ds:
            self.assertTrue(os.path.isfile(path))
            self.assertTrue(path.read_text())
            count += 1
        self.assertLess(0, count)

    def test_add_file(self):
        d = TempDirpath()

        f = d.add_file("foo.txt")
        self.assertTrue(f.exists())
        self.assertFalse(f.read_text())

        f = d.add_file("bar.txt", "foobar")
        self.assertTrue(f.exists())
        self.assertTrue(f.read_text())

    def test_add_dir(self):
        d = TempDirpath()
        f = d.add_dir("foo")
        self.assertTrue(f.isdir())

    def test_add_child(self):
        d = TempDirpath()

        f = d.add_child("foo.txt", "foobar")
        self.assertTrue(f.exists())
        self.assertTrue(f.read_text())

        f = d.add_child("bar.txt", "")
        self.assertTrue(f.isfile())

        f = d.add_child("che")
        self.assertTrue(f.isdir())

    def test_new(self):
        d = TempDirpath()
        self.assertTrue(d.exists())
        self.assertTrue(d.is_dir())

        d = TempDirpath("foo", "bar")
        self.assertTrue(d.exists())
        self.assertTrue(d.is_dir())
        self.assertTrue("/foo/bar" in d)


class TempFilepathTest(TestCase):
    def test_relpath(self):
        f = TempFilepath("foo", "bar", "che.txt")
        self.assertEqual("foo/bar/che.txt", f.relpath)

    def test_relparts(self):
        f = TempFilepath("foo", "bar", "che.txt")
        self.assertEqual(["foo", "bar", "che.txt"], f.relparts)

    def test_has(self):
        f = TempFilepath(data="foo bar che")
        self.assertTrue(f.has())
        self.assertTrue(f.has("bar"))
        self.assertTrue(lambda line: "bar" in line)

        f = TempFilepath()
        self.assertFalse(f.has())

    def test_get_basename(self):
        n = TempFilepath.get_basename(ext="csv", prefix="bar", postfix="che")
        self.assertRegex(n, r"bar\w+che\.csv")

        n = TempFilepath.get_basename(ext="csv", prefix="bar", name="")
        self.assertRegex(n, r"bar\w+\.csv")

        n = TempFilepath.get_basename(ext="csv", name="")
        self.assertRegex(n, r"\w+\.csv")

        n = TempFilepath.get_basename(ext="py", name="foo")
        self.assertEqual("foo.py", n)

        n = TempFilepath.get_basename(ext="py", name="foo.py")
        self.assertEqual("foo.py", n)

        n = TempFilepath.get_basename(ext="py", prefix="bar", name="foo.py")
        self.assertEqual("barfoo.py", n)

        n = TempFilepath.get_basename()
        self.assertTrue(n)

        n = TempFilepath.get_basename(ext="ext")
        self.assertRegex(n, r"\w+\.ext")

    def test_new(self):
        f = TempFilepath([""], ext="csv")
        self.assertFalse(f.endswith("/.csv"))

        f = TempFilepath(["/"], ext="csv")
        self.assertFalse(f.endswith("/.csv"))

        f = TempFilepath([], ext="csv")
        self.assertFalse(f.endswith("/.csv"))

        f = TempFilepath("/", ext="csv")
        self.assertFalse(f.endswith("/.csv"))

        f = TempFilepath("", ext="csv")
        self.assertFalse(f.endswith("/.csv"))

        f = TempFilepath()
        self.assertTrue(f.exists())
        self.assertTrue(f.is_file())

        f = TempFilepath("foo", "bar")
        self.assertTrue(f.exists())
        self.assertTrue(f.is_file())
        self.assertTrue("/foo/bar" in f)


class CachepathTest(TestCase):
    def test_create_key(self):
        k = Cachepath.create_key("foo", "ba%$?/r")
        self.assertEqual("foo.bar", k)

        k = Cachepath.create_key("foo", "ba%$?/r", prefix="che")
        self.assertEqual("che.foo.bar", k)

    def test_cache(self):
        data = {
            "foo": testdata.get_words(),
            "bar": testdata.get_words(),
        }
        c = Cachepath("foo", "ba%$?/r", ttl=1)

        cache_hit = False
        if c:
            cache_hit = True
        else:
            c.write(data)
        self.assertFalse(cache_hit)

        if c:
            cache_data = c.read()
        else:
            c.write(data)
        self.assertEqual(cache_data, data)

        time.sleep(1)
        self.assertFalse(bool(c))


class SentinelTest(TestCase):
    def test_fail_pass(self):
        s = Sentinel(testdata.get_modulename(), testdata.get_filename(), monthly=True)

        count = 0
        if s:
            count += 1
        if s:
            count += 1
        self.assertEqual(1, count)

