# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.filetypes.html import (
    HTML,
    HTMLCleaner,
    HTMLParser,
    HTMLTokenizer,
    HTMLStripper,
)
from datatypes.filetypes.toml import (
    TOML,
)

from . import TestCase, testdata


class HTMLTest(TestCase):
    def test_inject_head(self):
        html = HTML("<html><head></head><body></body></html>")
        r = html.inject_into_head("foo")
        self.assertEqual("<html><head>foo</head><body></body></html>", r)

    def test_tags(self):
        html = HTML("\n".join([
            "<p class=\"one\">one body</p>",
            "<p class=\"two\">two body</p>",
        ]))

        self.assertEqual(2, len(list(html.tags())))

        tags = html.tags()
        tag = next(tags)
        self.assertEqual("one", tag["class"])
        self.assertEqual("one body", tag.text)

        tag = next(tags)
        self.assertEqual("two", tag["class"])
        self.assertEqual("two body", tag.text)


class HTMLCleanerTest(TestCase):
    def test_lifecycle(self):
        s = HTMLCleaner.strip_tags("foo<br />bar")
        self.assertEqual("foo\nbar", s)

        s = HTMLCleaner.strip_tags("&lt;:‑|<br />&gt;:)")
        self.assertEqual("<:‑|\n>:)", s)

    def test_images(self):
        html = 'foo <IMG src="bar.jpeg" /> che'
        s_keep = HTMLCleaner.strip_tags(html, keep_img_src=True)
        s = HTMLCleaner.strip_tags(html, keep_img_src=False)
        self.assertNotEqual(s, s_keep)

    def test_whitespace(self):
        html = 'Sideways <a href="/wiki/Latin_1" class="mw-redirect" title="Latin 1">Latin</a>-only emoticons'
        s = HTMLCleaner.strip_tags(html)
        self.assertEqual("Sideways Latin-only emoticons", s)

    def test_unescape(self):
        s = "&lt;:‑|&gt;:)"

        s = HTMLCleaner.unescape(s)
        self.assertEqual("<:‑|>:)", s)

        s = HTMLCleaner.unescape(s)
        self.assertEqual("<:‑|>:)", s)


class HTMLParserTest(TestCase):
    def test_no_end_tag(self):
        html = '<div><h1 class="foo">h1 full</h1><p>this is somethign <b>bold</b> and stuff</p>'
        #html = '<body>body data before <h1 class="foo">h1 data</h1> body data after</body>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual("div", t.next()["tagname"])

    def test_tagnames(self):
        html = "\n".join([
            '<div>',
            '<p>one</p>'
            '<p>two with <a href="#">link</a></p>'
            '<p>three with <img src="foobar.jpg" /></p>'
            '<p>four with <img src="foobar.jpg" /> and <a href="#2">link</a></p>'
            '<p>five</p>'
            '</div>',
        ])
        t = HTMLParser(html, "p")
        self.assertEqual(5, len(t))
        self.assertEqual(2, len(t.tags[1]["body"]))
        self.assertEqual(2, len(t.tags[2]["body"]))
        self.assertEqual(4, len(t.tags[3]["body"]))
        self.assertEqual(1, len(t.tags[4]["body"]))

    def test_notagnames(self):
        html = '<div><h1 class="foo">h1 full</h1><p>this is something <b>bold</b> and stuff</p></div>'
        #html = '<body>body data before <h1 class="foo">h1 data</h1> body data after</body>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual(2, len(t.tags[0]["body"]))

    def test_empty_tags(self):
        html = '<div><span><img src=""><p>p data</p><br></span></div>'
        t = HTMLParser(html)
        self.assertEqual(1, len(t))
        self.assertEqual(1, len(t.tags[0]["body"]))
        self.assertEqual(3, len(t.tags[0]["body"][0]["body"]))


class HTMLTokenizerTest(TestCase):
    def test_notagnames(self):
        html = "\n".join([
            '<div>',
            '<p>one</p>'
            '<p>two with <a href="#">link</a></p>'
            '<p>three with <img src="foobar.jpg" /></p>'
            '<p>four with <img src="foobar.jpg" /> and <a href="#2">link</a></p>'
            '<p>five</p>'
            '</div>',
        ])

        t = HTMLTokenizer(html)

        tag = t.next()
        self.assertEqual("div", tag.tagname)

    def test_next_prev(self):
        html = "\n".join([
            '<one>1</one>',
            '<two>2</two>',
            '<three>3</three>',
            '<four>4</four>',
        ])
        t = HTMLTokenizer(html)

        with self.assertRaises(StopIteration):
            t.prev()

        tag = t.next()
        self.assertEqual("one", tag.tagname)

        tag = t.prev()
        self.assertEqual("one", tag.tagname)

        tag = t.next()
        self.assertEqual("one", tag.tagname)

        tag = t.next()
        self.assertEqual("two", tag.tagname)

        tag = t.next()
        self.assertEqual("three", tag.tagname)

        tag = t.next()
        self.assertEqual("four", tag.tagname)
        self.assertEqual("4", tag.text)

        with self.assertRaises(StopIteration):
            tag = t.next()

        tag = t.prev()
        self.assertEqual("four", tag.tagname)

        tag = t.prev()
        self.assertEqual("three", tag.tagname)


class HTMLStripperTest(TestCase):
    def test_remove_tags(self):
        hs = HTMLStripper(
            '<div class="foo">1<div>2</div>3</div><div>4</div><p>5</p>',
            remove_tags=["div"]
        )

        plain = hs.get_data()
        self.assertEqual("5", plain)
        return

        hs = HTMLStripper(
            '<div class="foo">1<div>2</div>3</div><div>4</div>',
            remove_tags=["div.foo"]
        )

        plain = hs.get_data()
        self.assertEqual("4", plain)


class TOMLTest(TestCase):
    def create_instance(self, lines):
        fp = self.create_file(lines)
        return TOML(fp)

    def test_table_setup(self):
        t = self.create_instance([
            "[foo]",
            "[foo.bar]",
            "[foo.\"bar.che\".bam]",
        ])

        self.assertIsNotNone(t.foo.bar)
        self.assertIsNotNone(t.foo["bar.che"].bam)

    def test_parse_array(self):
        t = self.create_instance([
            "foo = [1, 2]",
        ])
        self.assertEqual([1, 2], t.foo)

    def test_parse_dict(self):
        t = self.create_instance([
            "foo = { bar = 1, che = \"two\" }",
        ])
        self.assertEqual({"bar": 1, "che": "two"}, t.foo)

    def test_parse_1(self):
        t = self.create_instance([
            "[foo.bar]",
            "foo = 1",
            "bar = \"two\"",
            "che = [1, 2]",
        ])
        self.assertEqual(1, t.foo.bar.foo)
        self.assertEqual("two", t.foo.bar.bar)
        self.assertEqual([1, 2], t.foo.bar.che)

    def test_write(self):
        t = self.create_instance([
            "one = 1",
            "",
            "[foo]",
            "two = 2",
            "three = { four = 4, five = \"five\" }",
            "",
            "[foo.bar]",
            "six = \"six\"",
            "seven = [8, 9, \"ten\"]",
            "",
            "[eleven]",
            "twelve = 12",
        ])

        t.write()

        t2 = self.create_instance(t.path.read_text())
        self.assertEqual(t.sections, t2.sections)

    def test_add_section(self):
        t = self.create_instance("")

        t.add_section("foo.\"bar.che\".bam")
        self.assertIsNotNone(t.foo["bar.che"].bam)
        self.assertEqual(1, len(t.sections_order))

