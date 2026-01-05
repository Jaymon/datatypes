# -*- coding: utf-8 -*-
import os
import time
import re

from datatypes.compat import *
from datatypes.path import (
    Path,
    Dirpath,
    Filepath,
    Imagepath,
    TempDirpath,
    TempFilepath,
    Cachepath,
    Sentinel,
    UrlFilepath,
    PathIterator,
    DataDirpath,
)

from . import TestCase, testdata


class PathTest(TestCase):
    path_class = Path

    def create(self, *parts, **kwargs):
        kwargs.setdefault("path_class", self.path_class)

        path = Path.joinparts(*parts) if parts else ""

        contents = kwargs.pop("contents", kwargs.pop("data", {}))
        exists = kwargs.pop(
            "exists",
            True if contents else False if path else True
        )
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
                    parts = [
                        testdata.get_dir(
                            path if path else testdata.get_filename()
                        )
                    ]

        else:
            if contents:
                parts = [testdata.create_file(contents, path)]

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

    def test_relative_to_1(self):
        p = self.create("/etc/passwd")

        self.assertEqual("etc/passwd", p.relative_to("/"))
        self.assertEqual("passwd", p.relative_to("/etc"))

        with self.assertRaises(ValueError):
            p.relative_to("/usr")

    def test_relative_to_2(self):
        p = self.create("foo")
        self.assertEqual(".", p.relative_to(p))
        self.assertEqual(".", os.path.relpath(p, p))
        self.assertEqual("", p.relative_to(p, empty_same=True))

    def test_relative_parts(self):
        """Similar test to:

            bang.tests.path_test.DirectoryTest.test_relative_parts

        moved to here on 1-4-2023
        """
        d = Dirpath("/foo/bar/che/bam/boo")
        p = d.relative_parts("/")
        self.assertEqual(["foo", "bar", "che", "bam", "boo"], p)

        p = d.relative_parts("/foo/bar/")
        self.assertEqual(["che", "bam", "boo"], p)

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

    def test_joinparts(self):
        r = Path.joinparts("", "foo", "bar")
        self.assertEqual('/foo/bar', r)

        r = Path.joinparts(["foo", "bar"])
        self.assertEqual('foo/bar', r)

        r = Path.joinparts("/foo", "/bar/", "/che")
        self.assertEqual('/foo/bar/che', r)

        r = Path.joinparts(["foo", "bar"], "che")
        self.assertEqual('foo/bar/che', r)

    def test_splitparts_1(self):
        ps = Path.splitparts("\\foo\\bar", "\\che\\")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.splitparts("foo", None)
        self.assertEqual(["foo", "None"], ps)

        ps = Path.splitparts(["/foo", "bar"], "che", ["/baz", "boom"])
        self.assertEqual(["/", "foo", "bar", "che", "baz", "boom"], ps)

        ps = Path.splitparts("/foo", "/bar/", "/che")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.splitparts("", "foo", "bar")
        self.assertEqual(["/", "foo", "bar"], ps)

        ps = Path.splitparts("/che/baz", "foo", "bar")
        self.assertEqual(["/", "che", "baz", "foo", "bar"], ps)

        ps = Path.splitparts("foo", self.create_file("/", "bar", "che"), "baz")
        self.assertEqual(["foo", "bar", "che", "baz"], ps)

        ps = Path.splitparts(["foo/bar", "che"], "baz")
        self.assertEqual(["foo", "bar", "che", "baz"], ps)

        ps = Path.splitparts("/foo/bar", "che")
        self.assertEqual(["/", "foo", "bar", "che"], ps)

        ps = Path.splitparts("/")
        self.assertEqual(["/"], ps)

        ps = Path.splitparts("")
        self.assertEqual(["/"], ps)

        ps = Path.splitparts()
        self.assertEqual([], ps)

        ps = Path.splitparts([])
        self.assertEqual([], ps)

    def test_splitparts_2(self):
        regex = r"\.+"
        root = ""

        ps = Path.splitparts(
            "foo.bar", "che.baz.bar", "bam/boom",
            regex=regex,
            root=root
        )
        self.assertEqual(6, len(ps))

        ps = Path.splitparts("", root="")
        self.assertEqual([], ps)

    def test_sanitize_chars(self):
        r = Path("/", "foo?^", "bar*", "che:baz", "<bam>.ext")
        r2 = r.sanitize()
        self.assertEqual("/foo/bar/chebaz/bam.ext", r2)

        r3 = Filepath("/hi?.ext").sanitize()
        self.assertEqual("/hi.ext", r3)
        self.assertTrue(isinstance(r3, Filepath))

        r3 = Dirpath("/hi?*^").sanitize()
        self.assertEqual("/hi", r3)
        self.assertTrue(isinstance(r3, Dirpath))

    def test_sanitize_len(self):
        basedir = TempDirpath()
        maxpath = 100
        p = Path(
            basedir,
            testdata.get_words(20),
            f"{testdata.get_words(20)}.ext"
        )
        sp = p.sanitize(maxpart=20, maxpath=maxpath)
        self.assertGreaterEqual(maxpath, len(sp))
        self.assertTrue(sp.endswith(".ext"))

        with self.assertRaises(ValueError):
            p = Path(
                basedir,
                testdata.get_words(20),
                f"{testdata.get_words(20)}.ext"
            )
            sp = p.sanitize(maxpart=20, maxpath=40)

        for x in range(10):
            r = Path(
                testdata.get_words(20),
                testdata.get_words(20),
                testdata.get_words(20),
                "basename.ext"
            )
            r2 = r.sanitize()
            self.assertGreaterEqual(260, len(r2))
            self.assertEqual(len(r.parts), len(r2.parts))
            self.assertTrue(r2.endswith(".ext"))

    def test_sanitize_emoji_1(self):
        r = Path("foo \U0001F441\u200D\U0001F5E8.ext")
        rr = r.sanitize()
        self.assertEqual("foo.ext", rr.basename)

        r = Path("foo \U0001F441\u200D\U0001F5E8")
        rr = r.sanitize()
        self.assertEqual("foo", rr.basename)

        r = Path("2021-09-09 2221 - \U0001F3A5")
        rr = r.sanitize()
        self.assertEqual("2021-09-09 2221 -", rr.basename)

    def test_sanitize_emoji_2(self):
        r = Path("You're #1 - Come check these drops out...\U0001F440")
        r2 = r.sanitize()
        self.assertTrue(
            r2.endswith("You're #1 - Come check these drops out...")
        )

    def test_sanitize_newlines(self):
        r = Path("foo\nbar")
        self.assertTrue("\n" in r)
        r2 = r.sanitize()
        self.assertFalse("\n" in r2)

    def test_sanitize_callback(self):
        r = Path(".foo.", ".bar.")
        self.assertTrue(r.endswith(".foo./.bar."))
        r2 = r.sanitize(lambda s, ext: (s.replace(".", ""), ext))
        self.assertTrue(r2.endswith("foo/bar"))

    def test_sanitize_inconsistent(self):
        p = Path(
            "/",
            "12345",
            "123456",
            "1234567",
            "1234567",
            "123456",
            "1234567890123456789012",
            "1234567",
            "12345678",
            "1234567890123456789",
            " ".join([
                "2020-03-04 220059 -",
                "123456789",
                "1234567890",
                "123",
                "&",
                "X.509",
                "12345678901",
                "12345678\n",
                "123456789012345",
                "1234",
                "12345678",
                "12345678901",
                "123456789",
                "1234567890",
                "1234567890",
            ])
        )

        r = p.sanitize(maxpath=220)
        self.assertEqual(212, len(r))

    def test_splitpart(self):
        tests = [
            ("base.", "base.", ""),
            (".base", ".base", ""),
            (".base.", ".base.", ""),
            ("base.ext", "base", ".ext"),
            ("base.ext ension", "base.ext ension", ""),
            (
                "base.123456789012345678901234567",
                "base.123456789012345678901234567",
                ""
            ),
            ("base.not.ext", "base.not", ".ext"),
            ("base", "base", ""),
        ]

        for tinput, rbase, rext in tests:
            base, ext = Path.splitpart(tinput)
            self.assertEqual(rbase, base)
            self.assertEqual(rext, ext)


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

    def test_normpaths_1(self):
        ds = self.path_class.normpaths(
            {"foo": ["bar", "che"]},
            baseparts=["prefix"]
        )
        self.assertEqual(1, len(ds))
        self.assertEqual(["prefix", "foo"], ds[0][0])
        self.assertEqual(["bar", "che"], ds[0][1])

        ds = self.path_class.normpaths(["foo", "bar"], baseparts=["prefix"])
        self.assertEqual(2, len(ds))
        self.assertEqual(["prefix", "foo"], ds[0][0])
        self.assertEqual(None, ds[1][1])

        ds = self.path_class.normpaths({"foo": None}, baseparts=["prefix"])
        self.assertEqual(["prefix", "foo"], ds[0][0])
        self.assertEqual(None, ds[0][1])

        ds = self.path_class.normpaths({
            "foo": {
                "bar": {}
            }
        }, baseparts=["prefix"])
        s = set(["prefix.foo.bar"])
        for parts, contents in ds:
            self.assertTrue(".".join(parts) in s)
            self.assertIsNone(contents)

        ds = self.path_class.normpaths({
            "foo": {
                "bar": "def ident(): return 'foo.bar'",
                "che": {
                    "baz": "def ident(): return 'foo.che'",
                }
            }
        }, baseparts=["prefix"])
        s = set(["prefix.foo.bar", "prefix.foo.che.baz"])
        for parts, contents in ds:
            self.assertTrue(".".join(parts) in s)

    def test_normpaths_2(self):
        d = {
            "prefix": {
                "": [
                    "class Default(object):",
                    "    def GET(*args, **kwargs): pass",
                ],
                "default": [
                    "class Default(object):",
                    "    def GET(*args, **kwargs): pass",
                ],
                "foo": [
                    "class Default(object):",
                    "    def GET(*args, **kwargs): pass",
                    "",
                    "class Bar(object):",
                    "    def GET(*args, **kwargs): pass",
                    "    def POST(*args, **kwargs): pass",
                ],
                "foo.baz": [
                    "class Default(object):",
                    "    def GET(*args, **kwargs): pass",
                    "",
                    "class Che(object):",
                    "    def GET(*args, **kwargs): pass",
                ],
            }
        }
        ds = self.path_class.normpaths(d, regex=r"[\.\\/]+", root="")
        self.assertEqual(3, len(ds[3][0]))
        self.assertEqual(1, len(ds[0][0]))

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
        self.assertEqual(2, count)

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
        self.assertEqual(2, count)

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

    def test_children_regex(self):
        p = self.create_dir(contents={
            "foo.txt": testdata.get_lines(),
            "bar/che.txt": testdata.get_lines(),
            "goo/gap.py": testdata.get_lines(),
            "baz.txt": testdata.get_lines(),
            "boom/pow/bam.txt": testdata.get_lines(),
        })

        count = 0
        for fp in p.children(regex=r"\.txt$"):
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
        foo_f = d.add_file("foo.txt", "foo")
        bar_f = d.add_file("bar/bar.txt", "bar")
        che_d = d.add_dir("che")

        self.assertTrue(foo_f.exists())
        self.assertTrue(bar_f.exists())
        self.assertTrue(che_d.exists())

        d.clear()
        self.assertFalse(foo_f.exists())
        self.assertFalse(bar_f.exists())
        self.assertFalse(che_d.exists())
        self.assertEqual(0, len(list(d.iterfiles())))

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
        dest = self.create_dir(
            target,
            p.basename,
            contents={"bar.txt": testdata.get_lines()}
        )

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

        dest = p.cp(target, into=False)
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
        dest = self.create_dir(
            target,
            p.basename,
            contents={"bar.txt": testdata.get_lines()}
        )

        self.assertTrue(target.exists())
        self.assertTrue(dest.exists())

        p.cp(target, into=False)
        self.assertEqual(1, p.count(recursive=True))
        self.assertEqual(2, dest.count(recursive=True))

    def test_copy_to_1(self):
        """https://github.com/Jaymon/testdata/issues/30"""
        source_d = testdata.create_files({
            "foo.txt": testdata.get_words(),
            "bar/che.txt": testdata.get_words(),
        })
        dest_d = testdata.create_dir()

        source_d.copy_to(dest_d)
        self.assertTrue(dest_d.has(pattern="foo.txt"))
        self.assertTrue(dest_d.has(pattern="*/bar/che.txt"))

        source_f = testdata.create_file("foo.txt", testdata.get_words())
        dest_f = testdata.get_file()
        self.assertFalse(dest_f.exists())
        source_f.copy_to(dest_f)
        self.assertEqual(source_f.read_text(), dest_f.read_text())

    def test_add_file_from_bang(self):
        """Similar test to bang.tests.path_test.FileTest.test_create

        moved to here on 1-4-2023
        """
        data = "contents"
        d = testdata.create_dir()
        d.add_file("foo/test.txt", data=data)
        f = Filepath(d.path, "foo", "test.txt")
        self.assertTrue(f.exists())

        s = f.read_text()
        self.assertEqual(data, s)

    def test_has_file(self):
        """Similar test to bang.tests.path_test.DirectoryTest.test_has_file

        moved to here on 1-4-2023
        """
        f = testdata.create_file(path="foo/bar/che/index.html")

        d = Dirpath(f.parent)
        self.assertTrue(d.has_file("index.html"))

        d = Dirpath(f.parent.parent)
        self.assertTrue(d.has_file("che", "index.html"))

        d = Dirpath(f.parent.parent.parent)
        self.assertTrue(d.has_file("bar", "che", "index.html"))

    def test_files_1_from_bang(self):
        """Similar test to bang.tests.path_test.DirectoryTest.test_files_1

        moved to here on 1-4-2023
        """
        d = testdata.create_files({
            "foo.txt": "",
            "bar/che.txt": "",
            "boo/baz/bah.txt": ""
        })

        fs = list(d.files())
        self.assertEqual(3, len(fs))

        fs = list(d.files(recursive=False))
        self.assertEqual(1, len(fs))

    def test_files_regex(self):
        """Similar test to bang.tests.path_test.DirectoryTest.test_files_2

        moved to here on 1-4-2023
        """
        d = testdata.create_files({
            "foo.txt": "",
            "che.txt": "",
            "bah.txt": ""
        })

        fs = list(d.children())
        self.assertEqual(3, len(fs))

        fs2 = list(d.files(regex=r"/che"))
        self.assertEqual(1, len(fs2))
        self.assertTrue(fs2[0].endswith("che.txt"))

        fs2 = list(d.files(ne_regex=r"/che"))
        self.assertEqual(2, len(fs2))
        for f in fs2:
            self.assertFalse(f.endswith("che.txt"))

    def test_dirs(self):
        """Similar test to bang.tests.path_test.DirectoryTest.test_directories

        moved to here on 1-4-2023
        """
        d = testdata.create_files({
            "foo.txt": "",
            "bar/che.txt": "",
            "boo/baz/bah.txt": ""
        })

        ds = [v.path for v in d.dirs()]
        self.assertEqual(3, len(ds))

        ds = [v.path for v in d.dirs(recursive=False)]
        self.assertEqual(2, len(ds))

    def test_copy_to_from_bang_1(self):
        """Similar test to bang.tests.path_test.DirectoryTest.test_copy_to

        moved to here on 1-4-2023
        """
        output_dir = testdata.create_dir()
        input_dir = testdata.create_files({
            "foo.txt": "",
            "bar/che.txt": "",
            "boo/baz/bah.txt": ""
        })

        ifs = list(input_dir.files())
        ofs = list(output_dir.files())
        self.assertNotEqual(len(ifs), len(ofs))

        input_dir.copy_to(output_dir)
        ifs = list(input_dir.files())
        ofs = list(output_dir.files())
        self.assertEqual(len(ifs), len(ofs))

    def test_copy_to_from_bang_2(self):
        """Similar test to

            bang.tests.path_test.DirectoryTest.test_copy_paths_depth

        moved to here on 1-4-2023
        """
        src_dir = testdata.create_files({
            "foo.txt": "",
            "bar/che.txt": "",
            "boo/baz/bah.txt": ""
        })

        target_dir = testdata.create_dir()
        rd = src_dir.copy_to(target_dir)
        self.assertEqual(3, len(list(rd.files())))

        target_dir = testdata.create_dir()
        rd = src_dir.copy_to(target_dir, recursive=False)
        self.assertEqual(1, len(list(rd.iterfiles())))

    def test_has(self):
        d = testdata.create_files({
            "foo.txt": "",
            "bar/che.txt": "",
        })

        self.assertTrue(d.has(pattern="*/che.txt"))
        self.assertTrue(d.has_file(pattern="*/che.txt"))

        self.assertTrue(d.has("bar"))
        self.assertTrue(d.has_dir("bar"))

        self.assertTrue(d.has("bar/che.txt"))
        self.assertTrue(d.has_file("bar/che.txt"))
        self.assertFalse(d.has_dir("bar/che.txt"))
        self.assertFalse(d.has("bar/che"))
        self.assertTrue(d.has(pattern="*/bar/che.*"))
        self.assertTrue(d.has_file(pattern="*/bar/che.*"))
        self.assertFalse(d.has_dir(pattern="*/bar/che.*"))

        self.assertTrue(d.has_file("foo.txt"))
        self.assertFalse(d.has_dir("foo.txt"))



class FilepathTest(_PathTestCase):
    path_class = Filepath

    def test_dir_init(self):
        dp = TempDirpath()
        fp = Filepath("foobar.ext", dir=dp)
        self.assertEqual(dp.path, fp.directory.path)

        fp2 = Filepath(dp, "foobar.ext")
        self.assertEqual(fp.path, fp2.path)

    def test_file(self):
        f = testdata.create_file("this is the text", "foo.txt")
        self.assertEqual("foo", f.fileroot)
        self.assertEqual("txt", f.ext)
        self.assertEqual("foo.txt", f.name)
        self.assertEqual(f.directory, f.parent)

    def test_permissions(self):
        f = testdata.create_file("permissions.txt")
        self.assertRegex(f.permissions, r"0[0-7]{3}")

        # TODO -- this should work!
        #f.chmod(0o755)
        #self.assertEqual("0755", f.permissions)

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
        with p("w+") as fp:
            fp.write(contents)
        self.assertEqual(contents, p.read_text())

        # open the file without passing in mode and make sure it works as
        # expected
        with p as fp:
            self.assertEqual(contents, fp.read())
            with self.assertRaises(Exception):
                fp.write("foo")

    def test_empty(self):
        p = self.create()

        self.assertTrue(p.exists())
        self.assertTrue(p.empty())

        p.write_text(testdata.get_words())
        self.assertFalse(p.empty())

        p.delete()
        self.assertFalse(p.exists())
        self.assertTrue(p.empty())

    def test_cp_create_recursive(self):
        """Tests cp works when the directory doesn't exist"""
        basedir = TempDirpath()
        src = TempFilepath("foo", "bar", "che.txt", dir=basedir)
        self.assertTrue(src.isfile())

        target = Dirpath("foo2", "bar2", dir=basedir)
        self.assertFalse(target.isdir())

        with self.assertRaises(FileNotFoundError):
            src.cp(target, recursive=False)

        r = src.cp(target, recursive=True)
        self.assertEqual(src.basename, r.basename)

        target = Filepath("foo3", "bar3", "che.md", dir=basedir)
        self.assertFalse(target.exists())
        r = src.cp(target, recursive=True)
        self.assertEqual("che.md", r.basename)

        target = Filepath("foo4", "bar4", "che", dir=basedir)
        self.assertFalse(target.exists())
        r = src.cp(target, recursive=True)
        self.assertEqual("che", r.basename)

    def test_flock(self):
        one = TempFilepath()
        two = Filepath(one)

        with one.flock("r+") as fp:
            self.assertTrue(fp)
            with two.flock("r+") as fp2:
                self.assertIsNone(fp2)

        with two.flock_text("r+") as fp2:
            self.assertTrue(fp2)
            with one.flock_text("r+") as fp:
                self.assertIsNone(fp)


class ImagepathTest(TestCase):
    def test_dimensions(self):
        ts = [
            ("agif", (11, 29)),
            ("gif", (190, 190)),
            ("jpg", (190, 190)),
            ("png", (190, 190)),
            ("ico", (64, 64)),
        ]

        for t in ts:
            im = Imagepath(testdata.create_image(t[0]))
            self.assertEqual(t[1], im.dimensions)

    def test_is_animated(self):
        im = Imagepath(testdata.create_animated_gif())
        self.assertTrue(im.is_animated())

        im = Imagepath(testdata.create_gif())
        self.assertFalse(im.is_animated())

        im = Imagepath(testdata.create_jpg())
        self.assertFalse(im.is_animated())


class TempDirpathTest(TestCase):
    def test_dir_param(self):
        d = TempDirpath()
        d2 = TempDirpath(dir=d)
        self.assertEqual(d, d2)

    def test_empty_string(self):
        d = TempDirpath("")
        d2 = d.relative_to(d.gettempdir())
        d3 = TempDirpath()
        d4 = d3.relative_to(d.gettempdir())
        self.assertEqual(len(d.splitparts(d2)), len(d.splitparts(d4)))

    def test_children(self):
        d = TempDirpath()
        ds = d.add({
            "bar/che.txt": "che.txt data",
            "foo.txt": "foo.txt data",
        })
        self.assertEqual(3, len(list(d.children())))
        self.assertEqual(2, len(list(d.children(pattern="*.txt"))))
        self.assertEqual(1, len(list(d.children(pattern="che.txt"))))
        self.assertEqual(1, len(list(d.children(pattern="*/bar/che.txt"))))
        self.assertEqual(1, len(list(d.children(pattern="bar"))))

    def test_has(self):
        d = TempDirpath()
        self.assertFalse(d.has())

        ds = d.add({
            "bar/che.txt": "che.txt data",
            "foo.txt": "foo.txt data",
        })
        self.assertTrue(d.has(pattern="*/che.txt"))
        self.assertTrue(d.has("bar"))
        self.assertTrue(d.has("bar/che.txt"))
        self.assertFalse(d.has("bar/che"))
        self.assertTrue(d.has(pattern="*/che.*"))
        self.assertTrue(d.has(callback=lambda p: p.endswith(".txt")))
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

        _d = d.add_dir(["foo", "bar"])
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
            self.assertTrue(
                os.path.isfile(path),
                "{} does not exist".format(path)
            )
            self.assertTrue(path.read_text())
            count += 1
        self.assertLess(0, count)

    def test_add_paths(self):
        d = TempDirpath()
        ps = d.add_paths({
            "foo.txt": "foo.txt data",
            "bar": None,
            "che/baz.txt": "che/baz.txt data",
        })

        for p in ps:
            self.assertTrue(p.startswith(TempDirpath.gettempdir()))

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

    def test_existing_init(self):
        path = TempDirpath()
        d2 = TempDirpath(path)
        self.assertEqual(path, d2)

    def test_normparts(self):
        p = TempDirpath()
        p2 = TempDirpath(p, "foo")
        self.assertEqual("foo", p2.relative_to(p))

        p = TempDirpath()
        p2 = TempDirpath(p)
        self.assertEqual(p, p2)

        p = TempDirpath()
        p2 = TempDirpath(dir=p)
        self.assertEqual(p, p2)

        p = TempDirpath("foo")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(2, len(p.splitparts(relpath)))

        p = TempDirpath()
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(1, len(p.splitparts(relpath)))

        p = TempDirpath("")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(1, len(p.splitparts(relpath)))

        p = TempDirpath("/")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(1, len(p.splitparts(relpath)))


class TempFilepathTest(TestCase):
    def test_existing_init(self):
        relpath = "foo1/bar1/test.txt"
        f = TempFilepath(relpath, data="happy")
        f2 = TempFilepath(f)
        self.assertEqual(f, f2)

    def test_dir_param(self):
        f = TempFilepath()
        f2 = TempFilepath(dir=f.directory)
        self.assertEqual(f.directory, f2.directory)

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
        n = TempFilepath.get_basename(ext="csv", prefix="bar", suffix="che")
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
        self.assertTrue(f.startswith(TempFilepath.gettempdir()))

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

    def test_existing(self):
        f = TempFilepath(ext="txt")
        f2 = TempFilepath(f.basename, dir=f.basedir)
        self.assertEqual(f, f2)

        f3 = TempFilepath(f.basename, dir=f.directory)
        self.assertEqual(f, f3)

    def test_absolute_init(self):
        f = TempFilepath(ext="txt")
        f.rm()

        f2 = TempFilepath(f)
        self.assertEqual(f, f2)

    def test_normparts_1(self):
        p = TempDirpath()
        p2 = TempFilepath(p, "foo")
        self.assertEqual("foo", p2.relative_to(p))

        p = TempFilepath()
        p2 = TempFilepath(p)
        self.assertEqual(p, p2)

        p = TempDirpath()
        p2 = TempFilepath(dir=p)
        self.assertEqual(p, p2.parent)

        p = TempFilepath("foo")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(2, len(p.splitparts(relpath)))

        p = TempFilepath()
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(2, len(p.splitparts(relpath)))

        p = TempFilepath("")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(2, len(p.splitparts(relpath)))

        p = TempFilepath("/")
        relpath = p.relative_to(p.gettempdir())
        self.assertTrue(2, len(p.splitparts(relpath)))

    def test_normparts_2(self):
        parts = TempFilepath.normparts()
        self.assertEqual(2, len(parts))

        # A passed in parts with count should end with parts at the end
        parts = TempFilepath.normparts("foo/bar", count=4)
        self.assertEqual("foo", parts[-2])
        self.assertEqual("bar", parts[-1])
        self.assertTrue(len(parts) > 2)

    def test_normparts_name(self):
        parts = TempFilepath.normparts("")
        self.assertEqual(2, len(parts))

        parts = TempFilepath.normparts("", name="foo")
        self.assertEqual(2, len(parts))
        self.assertNotEqual("/", parts[0])
        self.assertEqual("foo", parts[-1])


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
        s = Sentinel(
            testdata.get_modulename(),
            testdata.get_filename(),
            monthly=True
        )

        count = 0
        if s:
            count += 1
        if s:
            count += 1
        self.assertEqual(1, count)


class UrlFilepathTest(TestCase):
    def test_url_only(self):
        dirpath = testdata.create_files({
            "foo.txt": "this is foo.txt",
            "bar/che.txt": "this is che.txt",
            "baz.jpg": testdata.create_jpg,
        })
        # needed so file isn't cached to same place every run
        prefix = testdata.get_ascii(6)

        server = testdata.create_fileserver({}, dirpath)
        with server:
            p = UrlFilepath(server.url("bar/che.txt"), prefix=prefix)
            self.assertEqual("this is che.txt", p.read_text())

            p = UrlFilepath(server.url("baz.jpg"), prefix=prefix)
            self.assertEqual(
                p.checksum(),
                dirpath.child_file("baz.jpg").checksum()
            )

    def test_url_path(self):
        server = testdata.create_fileserver({
            "foo.txt": "this is foo.txt",
        })
        filepath = testdata.get_file("foo2.txt")

        with server:
            p = UrlFilepath(server.url("foo.txt"), filepath)
            self.assertEqual(filepath.path, p.path)
            self.assertEqual("this is foo.txt", p.read_text())


class PathIteratorTest(TestCase):
    def test_simple(self):
        """Makes sure it can iterate through a directory"""
        dirpath = testdata.create_files({
            "foo.txt": "this is foo.txt",
            "bar/che.txt": "this is che.txt",
        })

        r_count = 0
        r = set(["foo.txt", "bar", "bar/che.txt"])
        pi = PathIterator(dirpath)
        for p in pi:
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(3, r_count)

    def test_files_dirs(self):
        dirpath = testdata.create_files({
            "foo.txt": "this is foo.txt",
            "bar/che.txt": "this is che.txt",
            "boo/baz": None,
        })

        r_count = 0
        r = set(["foo.txt", "bar/che.txt"])
        for p in PathIterator(dirpath).files():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(2, r_count)

        r_count = 0
        r = set(["bar", "boo", "boo/baz"])
        for p in PathIterator(dirpath).dirs():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(3, r_count)

    def test_depth_1(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
        })

        r_count = 0
        r = set([
            "1.txt",
            "bar",
            "boo",
            "che",
        ])
        for p in PathIterator(dirpath).depth(1):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar",
            "boo",
            "che",
        ])
        for p in PathIterator(dirpath).recursive(False):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar", "bar/2.txt",
            "boo", "boo/3.txt",
            "boo/baz",
            "che",
        ])
        for p in PathIterator(dirpath).depth(2):
            self.assertTrue(p.relative_to(dirpath) in r, p)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar", "bar/2.txt",
            "boo", "boo/3.txt",
            "boo/baz", "boo/baz/4.txt",
            "che",
        ])
        for p in PathIterator(dirpath).recursive(True):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
        ])
        for p in PathIterator(dirpath).recursive(False).files():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).recursive(True).files():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar",
            "boo",
            "boo/baz",
            "che",
        ])
        for p in PathIterator(dirpath).recursive(True).dirs():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar",
            "boo",
            "che",
        ])
        for p in PathIterator(dirpath).recursive(False).dirs():
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

    def test_pattern(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
        })

        r_count = 0
        r = set([
            "1.txt",
        ])
        for p in PathIterator(dirpath).glob("*.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).pattern("*.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).pattern("**/*.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
        ])
        for p in PathIterator(dirpath).pattern("*/bar/*.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
        ])
        for p in PathIterator(dirpath).pattern("**/bar/*.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

    def test_regex(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
        })

        r_count = 0
        r = set([
            "1.txt",
        ])
        for p in PathIterator(dirpath).regex(r"[1]\.TXT", flags=re.I):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).regex(r"[^/]+\.txt$"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
        ])
        for p in PathIterator(dirpath).regex(r"/bar/.+\.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

    def test_callback_1(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
        })

        r_count = 0
        r = set([
            "1.txt",
        ])
        for p in PathIterator(dirpath).callback(lambda p: p.endswith("1.txt")):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "1.txt",
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).callback(lambda p: p.endswith(".txt")):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
        ])
        cb = lambda p: p.endswith("bar/2.txt")
        for p in PathIterator(dirpath).callback(cb):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

    def test_callback_files(self):
        dirpath = testdata.create_files({
            "foo/page.md": "1",
            "bar/_page.md": "2",
            "bar/_baz/NOTES.txt": "3",
            "_NOTES_2.txt": "4",
            "boo/_che/bam/page.md": "5",
            "boo/page.md": "6",
            "boo/NOTES_3.txt": "7",
        })

        def cb(basename):
            return basename.startswith("_") or basename.startswith(".")

        files = dirpath.files()
        files.ne_basename(callback=cb) # ignore files matching cb
        files.nin_basename(callback=cb) # ignore directories matching cb
        self.assertEqual(3, len(files))

    def test_inverse(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
        })

        r_count = 0
        r = set([
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        it = PathIterator(dirpath).files()
        it.ne_callback(lambda p: p.endswith("1.txt"))
        for p in it:
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).files().ne_pattern("1.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

        r_count = 0
        r = set([
            "bar/2.txt",
            "boo/3.txt",
            "boo/baz/4.txt",
        ])
        for p in PathIterator(dirpath).files().ne_regex("1.txt"):
            self.assertTrue(p.relative_to(dirpath) in r)
            r_count += 1
        self.assertEqual(len(r), r_count)

    def test_count(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
            "che": None,
            "bam": None
        })

        self.assertEqual(4, len(PathIterator(dirpath).files()))
        self.assertEqual(9, len(PathIterator(dirpath)))
        self.assertEqual(5, len(PathIterator(dirpath).dirs()))

    def test_get_index(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
        })

        it = PathIterator(dirpath)

        it[0] # no error means it's good

        with self.assertRaises(IndexError):
            it[100000]

    def test_get_slice(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/baz/4.txt": "body 4",
        })

        it = PathIterator(dirpath)
        self.assertEqual(7, len(it[:]))

        it = PathIterator(dirpath)
        self.assertEqual(3, len(it[1:4]))

        it = PathIterator(dirpath)
        self.assertEqual(3, len(it[:3]))

        it = PathIterator(dirpath)
        self.assertEqual(3, len(it[1::2]))

        it = PathIterator(dirpath)
        self.assertEqual(4, len(it[::2]))

    def test_basenames(self):
        """Make sure directories get filtered correctly when recursing"""
        dirpath = testdata.create_files({
            "1.txt": "",
            "bar/2.txt": "",
            "_boo/3.txt": "",
        })

        def cb(p):
            return p.basename.startswith("_")


        it = PathIterator(dirpath).files()
        it.nin_dir(callback=cb)

        for count, p in enumerate(it, 1):
            pass
        self.assertEqual(2, count)

        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/_2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/_baz/4.txt": "body 4",
        })

        r_count = 0
        it = PathIterator(dirpath).files()
        it.ne_callback(cb)
        it.nin_dir(callback=cb)
        nr = set(["4.txt", "_2.txt"])
        for basename in (p.basename for p in it):
            self.assertFalse(basename in nr)
            r_count += 1
        self.assertEqual(2, r_count)

        it = PathIterator(dirpath).files().ne_callback(cb)
        r_count = 0
        for basename in (p.basename for p in it):
            r_count += 1
        self.assertEqual(3, r_count)

    def test_passthrough(self):
        dirpath = testdata.create_files({
            "1.txt": "body 1",
            "bar/data/_2.txt": "body 2",
            "boo/3.txt": "body 3",
            "boo/_baz/data/4.txt": "body 4",
        })

        # return all files and any directories named data
        it = PathIterator(dirpath)
        for count, fp in enumerate(it.dirs(regex=r"data$").files(), 1):
            pass
        self.assertEqual(6, count)

        # any directories named data
        it = PathIterator(dirpath)
        for count, fp in enumerate(it.dirs(regex=r"data$"), 1):
            pass
        self.assertEqual(2, count)

    def test_finish_1(self):
        modpath = "firm"
        dp = testdata.create_modules({
            f"{modpath}.foo": "",
            f"{modpath}.foo.bar.__init__": "",
            f"{modpath}.che.baz.boo": "",
        })

        dp.child_file(modpath, "data", "one.txt").write_text("1")
        dp.child_file(modpath, "foo", "bar", "data", "two.txt").write_text("2")
        dp.child_file(
            modpath,
            "che",
            "other_name",
            "one_dir",
            "three.txt"
        ).write_text("3")
        dp.child_file(
            modpath,
            "che",
            "other_name",
            "two_dir",
            "four.txt"
        ).write_text("4")

        count = 0
        it = dp.dirs()
        nr = set([
            f"{modpath}/data",
            f"{modpath}/che/other_name",
            f"{modpath}/foo/bar/data"
        ])
        for p in it:
            if not p.has_file("__init__.py") or p.endswith("data"):
                count += 1
                self.assertTrue(p.relative_to(dp) in nr)
                it.finish(p)
        self.assertEqual(3, count)

    def test_finish_2(self):
        dp = testdata.create_files({
            "foo": {
                "bar": {
                    "sentinal.txt": "",
                    "ignored 1": {
                        "ignored 2": {},
                        "ignored 3": {},
                    },
                    "nested bar": {
                        "sentinal.txt": "",
                        "ignored 5": {
                            "sentinal.txt": "",
                        },
                    },
                },
            },
        })

        def is_dir(p):
            return p.has_file("sentinal.txt")

        it = dp.dirs().callback(is_dir, finish=True)
        for count, p in enumerate(it, 1):
            self.assertTrue(p.endswith("/foo/bar"))
        self.assertEqual(1, count)

        dp = testdata.create_files({
            "foo": {
                "bar": {
                    "sentinal.txt": "",
                    "ignored 1": {
                        "ignored 2": {},
                        "ignored 3": {},
                    },
                    "nested bar": {
                        "sentinal.txt": "",
                        "ignored 5": {
                            "sentinal.txt": "",
                        },
                    },
                },
                "che": {
                    "one": {
                        "two": {
                            "sentinal.txt": "",
                        },
                        "ignored 4": {},
                    },
                },
            },
            "baz": {
                "three": {
                    "boo": {
                        "sentinal.txt": "",
                        "ignored 3.txt": "",
                    },
                },
            },
        })

        it = dp.dirs().callback(is_dir, finish=True)
        for count, p in enumerate(it, 1):
            if p.endswith("foo/bar"):
                pass

            elif p.endswith("foo/che/one/two"):
                pass

            elif p.endswith("baz/three/boo"):
                pass

            else:
                raise ValueError(p)
        self.assertEqual(3, count)

    def test_match_dir_and_file(self):
        dp = testdata.create_files({
            "bar/foo.txt": "body 1",
            "boo/foo/3.txt": "body 2",
            "boo/bam/foobar.txt": "body 3",
        })

        its = [
            dp.iterator.regex(r"(?:^|/)foo(?:\.|$)"),
            dp.iterator.eq_fileroot("foo"),
            dp.iterator.eq_file("foo.txt").eq_dir("foo"),
        ]

        for it in its:
            for count, p in enumerate(it, 1):
                if p.endswith("foo.txt") or p.endswith("foo"):
                    pass
                else:
                    raise ValueError(p)
            self.assertEqual(2, count)

    def test_depth_change(self):
        """Assure passing in depth to change the depth for a certain match works
        as expected"""
        dp = testdata.create_files({
            "bar": {
                "sentinal.txt": "",
                "one": {
                    "ignored 2": {
                        "sentinal.txt": "",
                        "two.txt": "",
                    },
                    "ignored 3": {
                        "ignored 4.txt": "",
                    },
                },
                "two": {
                    "sentinal.txt": "",
                },
                "three.txt": "",
            },
            "che": {
                "ignored 5.txt": "",
            },
            "four.txt": "",
        })

        def is_dir(p):
            return p.has_file("sentinal.txt")

        it = dp.iterator.in_dir(callback=is_dir, depth=1)

        for count, p in enumerate(it, 1):
            if p.endswith("/bar"):
                pass

            elif p.endswith("/four.txt"):
                pass

            elif p.endswith("/bar/sentinal.txt"):
                pass

            elif p.endswith("/bar/three.txt"):
                pass

            elif p.endswith("/bar/one"):
                pass

            elif p.endswith("/bar/two"):
                pass

            elif p.endswith("/che"):
                pass

            else:
                raise ValueError(p)

        self.assertEqual(7, count)

    def test_dynamic_methods(self):
        dp = testdata.create_files({
            "1.txt": "",
            "bar/2.txt": "",
            "boo/3.txt": "",
            "boo/baz/4.txt": "",
            "boo/baz/5.md": "",
            "che/6.md": "",
        })

        def cb(fileroot):
            return fileroot.startswith("b")

        it = dp.iterator.in_fileroot(callback=cb).eq_pattern("*.txt")
        for count, p in enumerate(it, 1):
            pass
        self.assertEqual(4, count)

        it = dp.iterator.eq_fileroot("4")
        for count, p in enumerate(it, 1):
            self.assertTrue(p.endswith("4.txt"))
        self.assertEqual(1, count)

    def test_hidden_and_private(self):
        dp = testdata.create_files({
            "1.txt": "",
            "_2.txt": "",
            "bar/3.txt": "",
            ".boo/4.txt": "",
            ".boo/baz/5.md": "",
            "che/.6.md": "",
            "che/_7.txt": "",
            "_bam/8.md": "",
        })

        paths = list(dp.iterator.nin_private())
        for p in paths:
            self.assertFalse(p.isdir() and p.is_private(), p)

        paths = list(dp.iterator.ignore_private())
        for p in paths:
            self.assertFalse(p.is_private(), p)

        paths = list(dp.iterator.ignore_hidden())
        for p in paths:
            self.assertFalse(p.is_hidden(), p)

        paths = list(dp.iterator.nin_hidden())
        for p in paths:
            self.assertFalse(p.isdir() and p.is_hidden(), p)


class DataDirpathTest(TestCase):
    def test_discovery_success(self):
        basedir = self.create_modules({
            "foos": {
                "bar": {
                    "che": "",
                },
            },
        })

        basedir.add_file(["foos", "bar", "che", "data", "1.txt"])
        basedir.add_file(["foos", "bar", "data", "2.txt"])
        basedir.add_file(["foos", "data", "3.txt"])

        dp = DataDirpath("foos.bar.che")
        self.assertTrue(dp.endswith("/foos/bar/data"))

        dp = DataDirpath("foos.bar")
        self.assertTrue(dp.endswith("/foos/bar/data"))

        dp = DataDirpath("foos")
        self.assertTrue(dp.endswith("/foos/data"))

    def test_discovery_failure(self):
        basedir = self.create_modules({
            "foof": {
                "bar": {
                    "che": "",
                },
            },
        })

        with self.assertRaises(NotADirectoryError):
            dp = DataDirpath("foof.bar.che")

