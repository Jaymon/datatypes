# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.filetypes.html import (
    HTML,
    HTMLCleaner,
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

    def test_delim_in_attr(self):
        """make sure bad html with no end ignored tag is handled"""
        html = HTML("<p data=\"foo>bar\">between p</p>")

        blocks = list(html.blocks())

        self.assertEqual(2, len(blocks))

        self.assertEqual("<p data=\"foo>bar\">", blocks[0][0])
        self.assertEqual("between p", blocks[0][1])

        self.assertEqual("</p>", blocks[1][0])
        self.assertEqual("", blocks[1][1])


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

    def test_entity_ref_escape(self):
        s = "&lt;:‑|&gt;:)"

        s = HTMLCleaner().feed(s)
        self.assertEqual("<:‑|>:)", s)

        s = HTMLCleaner().feed(s)
        self.assertEqual("<:‑|>:)", s)

    def test_entity_ref_unescape(self):
        between = "4 &gt; 3 &lt; 5"
        html = f"<p>{between}</p>"
        plain = HTMLCleaner(convert_charrefs=False).feed(html)
        self.assertEqual(between, plain.strip())

    def test_ignore_tagnames_1(self):
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

    def test_ignore_tagnames_2(self):
        html = "<p>this is some <span>fancy text</span> stuff</p>"
        plain = HTMLCleaner(
            ignore_tagnames=["p"],
        ).feed(html)
        self.assertEqual("<p>this is some fancy text stuff</p>", plain)

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

    def test_css_selector(self):
        html = HTML("""
            <p>one</p>
            <p>
                two <span class="foo">between <bold>span 1</bold></span>
                three <span>between span 2</span>
            </p>
            <p>four</p>
        """)

        plain = html.plain(strip_tagnames=["span.foo"])
        self.assertFalse("span 1" in plain)
        self.assertTrue("span 2" in plain)
        for tag in ["<p>", "<bold>", "<span"]:
            self.assertFalse(tag in plain)


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

