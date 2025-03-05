# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.filetypes.html import (
    HTML,
    HTMLCleaner,
    HTMLTagTokenizer,
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


class HTMLBlockTokenizerTest(TestCase):
    def test_blocks_1(self):
        html = HTML("<p></p>")
        count = 0
        for tag, plain in html.blocks():
            count += 1
        self.assertEqual(2, count)

    def test_blocks_2(self):
        """make sure bad html with no end tag is handled"""
        html = HTML("<p>")
        count = 0
        for tag, plain in html.blocks():
            count += 1
        self.assertEqual(1, count)

    def test_blocks_2(self):
        """make sure bad html with no end ignored tag is handled"""
        html = HTML("<p>after p <pre> after pre")
        count = 0
        for tag, plain in html.blocks(ignore_tagnames=["pre"]):
            count += 1
        self.assertEqual(2, count)

    def test_blocks_3(self):
        html = HTML("""
            <div>
                before p
                <p>
                    after p <a href=\"/foo/bar/che\">inside a</a>
                    after a
                </p>
                after p
            </div>
        """)

        count = 0
        for tag, plain in html.blocks(ignore_tagnames=["a", "pre"]):
            count += 1
        self.assertEqual(6, count)


class HTMLCleanerTest(TestCase):
    def test_lifecycle(self):
        s = HTMLCleaner().feed("foo<br />bar")
        self.assertEqual("foo\nbar", s)

        s = HTMLCleaner().feed("&lt;:‑|<br />&gt;:)")
        self.assertEqual("<:‑|\n>:)", s)

    def test_images(self):
        html = 'foo <IMG src="bar.jpg" /> che'

        s_keep = HTMLCleaner(keep_img_src=True).feed(html)
        self.assertTrue("bar.jpg" in s_keep)

        s = HTMLCleaner(keep_img_src=False).feed(html)
        self.assertFalse("bar.jpg" in s)

        self.assertNotEqual(s, s_keep)

    def test_whitespace(self):
        html = (
            'Sideways <a'
            ' href="/wiki/Latin_1"'
            ' class="mw-redirect"'
            ' title="Latin 1"'
            '>Latin</a>-only emoticons'
        )
        s = HTMLCleaner(inline_sep="").feed(html)
        self.assertEqual("Sideways Latin-only emoticons", s)

    def test_unescape(self):
        s = "&lt;:‑|&gt;:)"

        s = HTMLCleaner().feed(s)
        self.assertEqual("<:‑|>:)", s)

        s = HTMLCleaner().feed(s)
        self.assertEqual("<:‑|>:)", s)

    def test_ignore_tagnames(self):
        hc = HTMLCleaner(
            ignore_tagnames=["span"]
        )

        plain = hc.feed("""
            <div>
                After div before p
                <p>
                    after p before span <span class="red">between span</span>
                    after span
                </p>
                after p
            </div>
        """)
        self.assertTrue('<span class="red">' in plain)
        self.assertTrue("</span>" in plain)

    def test_strip_tagnames(self):
        hc = HTMLCleaner(
            strip_tagnames=["div"]
        )

        plain = hc.feed(
            '<div class="foo">1<div>2</div>3</div><div>4</div><p>5</p>'
        )
        self.assertEqual("5\n", plain)

    def test_plain(self):
        html = HTML("""
            <p>one</p>
            <p>two</p>
            <p>three</p>
        """)

        plain = html.plain()
        self.assertFalse("<p>" in plain)
        self.assertTrue("two" in plain)

    def test_strip_tags(self):
        html = HTML("""
            <p>one</p>
            <p>two <span>between span</span></p>
            <p>three</p>
        """)

        stripped_html = html.strip_tags(["span"])
        self.assertTrue("<p>" in stripped_html)
        self.assertTrue("two" in stripped_html)
        self.assertFalse("<span>between span</span>" in stripped_html)


class HTMLTagTokenizerTest(TestCase):
    def test_tags(self):
        html = HTML("""
            <p class="one">one body</p>
            <p class="two">two body</p>
        """)

        self.assertEqual(2, len(list(html.tags())))

        tags = html.tags()
        tag = next(tags)
        self.assertEqual("one", tag["class"])
        self.assertEqual("one body", tag.text)

        tag = next(tags)
        self.assertEqual("two", tag["class"])
        self.assertEqual("two body", tag.text)

    def test_tag_hierarchy(self):
        html = """
            <div>
                <p> after p before span
                    <span>inside span</span>
                after span</p>
            </div>
        """.strip()
        t = HTMLTagTokenizer(html)

        tag = t.next()
        self.assertEqual("div", tag.tagname)
        self.assertEqual(html, str(tag))

    def test_no_tagnames(self):
        html = """
            <div>
                <p>one</p>
                <p>two with <a href="#">link</a></p>
                <p>three with <img src="foobar.jpg" /></p>
                <p>four with <img src="foobar.jpg" />
                    and <a href="#2">link</a>
                </p>
                <p>five</p>
            </div>
        """

        t = HTMLTagTokenizer(html)

        tag = t.next()
        self.assertEqual("div", tag.tagname)

    def test_no_tagnames_2(self):
        html = """
            <div>
                <h1 class="foo">h1 full</h1>
                <p>this is something <b>bold</b> and stuff</p>
            </div>'
        """

        tags = list(HTMLTagTokenizer(html))
        self.assertEqual(1, len(tags))
        self.assertEqual(8, len(tags[0]["body"]))

    def test_tagnames(self):
        html = """
            <div>
                <p>one</p>
                <p>two with <a href="#">link</a></p>
                <p>three with <img src="foobar.jpg" /></p>
                <p>four with <img src="foobar.jpg" />
                    and <a href="#2">link</a>
                </p>
                <p>five</p>
            </div>
        """

        t = HTMLTagTokenizer(html, tagnames=["p"])

        for _ in range(5):
            tag = t.next()
            self.assertEqual("p", tag.tagname)

    def test_close(self):
        html = """
            <div>
                <p> after p before span
                    <span>inside span
                after span
        """.strip()
        t = HTMLTagTokenizer(html)

        tag = t.next()
        # all the tags should have the same stop value at EOF
        stops = set()
        for t in tag.tags():
            stops.add(t.stop)
        self.assertEqual(1, len(stops))

    def test_next(self):
        html = "\n".join([
            "<one>1</one>",
            "<two>2</two>",
            "<three>3</three>",
            "<four>4</four>",
        ])
        t = HTMLTagTokenizer(html)

        tag = t.next()
        self.assertEqual("one", tag.tagname)

        tag = t.next()
        self.assertEqual("two", tag.tagname)

        tag = t.next()
        self.assertEqual("three", tag.tagname)

        tag = t.next()
        self.assertEqual("four", tag.tagname)
        self.assertEqual("4", tag.text)

        tag = t.next()
        self.assertIsNone(tag)

    def test_attrs(self):
        html = '<a href="/foo/bar" class="che" data-item="boo">between a</a>'
        t = HTMLTagTokenizer(html)
        tag = t.next()
        self.assertEqual("/foo/bar", tag.href)
        self.assertEqual("boo", tag.data_item)
        self.assertEqual(3, len(tag.attrs))

    def test_offsets(self):
        html = '<div><a href="/" class="che">between a</a></div>'
        t = HTMLTagTokenizer(html, ["a"])
        tag = t.next()
        self.assertEqual(5, tag.start)
        self.assertEqual(38, tag.stop) # missing the </div>

    def test_no_end_tag(self):
        html = """
            <div>
                <h1 class="foo">h1 full</h1>
                <p>this is something <b>bold</b> and stuff</p>
        """
        t = HTMLTagTokenizer(html)
        self.assertEqual("div", t.next()["tagname"])

    def test_tagnames(self):
        html = """
            <div>
                <p>one</p>
                <p>two with <a href="#">link</a></p>
                <p>three with <img src="foobar.jpg" /></p>
                <p>
                    four with <img src="foobar.jpg" />
                    and <a href="#2">link</a>
                </p>
                <p>five</p>
            </div>
        """
        tags = list(HTMLTagTokenizer(html, ["p"]))
        self.assertEqual(2, len(tags[1]["body"]))
        self.assertEqual(2, len(tags[2]["body"]))
        self.assertEqual(8, len(tags[3]["body"]))
        self.assertEqual(1, len(tags[4]["body"]))

    def test_empty_tags(self):
        html = '<div><span><img src=""><p>p data</p><br></span></div>'

        t = HTMLTagTokenizer(html).next()
        self.assertEqual(1, len(t["body"]))
        self.assertEqual(3, len(t["body"][0]["body"]))


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

    def test_parse_boolean(self):
        t = self.create_instance([
            "foo = true",
            "bar = false",
        ])

        self.assertEqual(True, t.foo)
        self.assertEqual(False, t.bar)

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

