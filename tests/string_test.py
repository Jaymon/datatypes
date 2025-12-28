# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.string import (
    String,
    ByteString,
    Base64,
    Character,
    Codepoint,
    NamingConvention,
    EnglishWord,
    Password,
)

from . import TestCase, testdata


class Base64Test(TestCase):
    def test_encode_decode(self):
        s = testdata.get_words()

        b = Base64.encode(s)
        self.assertTrue(isinstance(b, unicode))
        self.assertNotEqual(b, s)

        s2 = Base64.decode(b)
        self.assertTrue(isinstance(s2, unicode))
        self.assertNotEqual(b, s2)
        self.assertEqual(s, s2)


class StringTest(TestCase):
    def test_xmlescape(self):
        s = String("<&")
        se = s.xmlescape()
        self.assertEqual("&lt;&amp;", se)

    def test_regex(self):
        s = String("foo bar foo")
        r = s.regex(r"foo").count()
        self.assertEqual(2, r)
        self.assertEqual(2, len(s.regex(r"foo")))
        self.assertEqual(1, len(s.regex(r"bar")))

    def test_string_int(self):
        i = testdata.get_int(0, 1000)
        s = String(i)
        self.assertEqual(str(i), String(i))

    def test_unicode_1(self):
        s = String(testdata.get_unicode())
        s2 = ByteString(s)
        s3 = String(s2)
        self.assertEqual(s, s3)

    def test_unicode_2(self):
        d = {"foo": testdata.get_unicode()}
        s2 = String(d)
        s3 = ByteString(s2)
        s4 = String(s3)
        self.assertEqual(s2, s4)

    def test_string(self):
        s = String(1)
        self.assertEqual("1", s)

        s = String(b"foo")
        self.assertEqual("foo", s)

        s = String({"foo": 1})
        self.assertEqual("{'foo': 1}", s)

        s = String((1, 2))
        self.assertEqual("(1, 2)", s)

        s = String([1, 2])
        self.assertEqual("[1, 2]", s)

        s = String(True)
        self.assertEqual("True", s)

        s = String(None)
        self.assertEqual("None", s)

        s = String("foo")
        self.assertEqual("foo", s)

        su = testdata.get_unicode()
        s = String(su)
        sb = bytes(s)
        s2 = String(sb)
        self.assertEqual(s, s2)

    def test_truncate(self):
        """tests that we can truncate a string on a word boundary"""
        s = String("foo bar bang bing")
        self.assertEqual("foo", s.truncate(5, ""))
        self.assertEqual("foo bar", s.truncate(10, ""))
        self.assertEqual("foo bar bang", s.truncate(15, ""))
        self.assertEqual("foo...", s.truncate(8, "..."))
        self.assertEqual("foo bar...", s.truncate(14, "..."))
        self.assertEqual("foop", s.truncate(5, "p"))
        self.assertEqual(s, s.truncate(len(s) + 100, "..."))

    def test_indent_simple(self):
        s = String("foo\nbar\nche")

        s2 = s.indent("  ")
        self.assertNotEqual(s, s2)
        for line in s2.splitlines():
            self.assertTrue(line.startswith("  "))

    def test_indent_issue37(self):
        #s = String("\nFOO\n").indent(1, "...")
        s = String("\nFOO\n").indent("...")
        self.assertEqual("...\n...FOO\n", s)

    def test_indent_count(self):
        s = String("foo")
        self.assertTrue(s.indent(".", 3).startswith("..."))
        self.assertFalse(s.indent(".", 2).startswith("..."))

    def test_wrap(self):
        s = String("foo bar che").wrap(5)
        self.assertEqual("foo\nbar\nche", s)

    def test_ispunc(self):
        s = String("{.}")
        self.assertTrue(s.ispunc())

        s = String(".A.")
        self.assertFalse(s.ispunc())

    def test_hash(self):
        h1 = String("4356").hash("YYYY-MM-DD")
        h2 = String("4356").hash("YYYY-MM-DD")
        h3 = String("4356").hash("YYYZ-MM-DD")
        h4 = String("4356").hash("YYYY-MM-DD", nonce="foobar")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertNotEqual(h1, h4)
        self.assertNotEqual(h3, h4)

    def test_casting(self):
        s = String(testdata.get_unicode_words())

        # https://stackoverflow.com/a/47113725
        self.assertFalse(type(s) is str)
        self.assertTrue(type(s) is String)
        self.assertTrue(type(s.unicode()) is String)

        s2 = str(s)
        self.assertTrue(type(s2) is str)
        self.assertFalse(type(s2) is String)

        b = s.bytes()
        self.assertTrue(type(b) is ByteString)
        self.assertFalse(type(b) is bytes)

        b2 = bytes(s)
        self.assertTrue(type(b2) is bytes)
        self.assertFalse(type(b2) is ByteString)

    def test_dedent(self):
        s = String("""
            foo
            bar
                che
        """).dedent().strip()

        self.assertTrue(s.startswith("foo"))
        self.assertTrue(s.endswith("    che"))

    def test_md5_uuid(self):
        s = String("id1")

        uuid = str(s.md5_uuid())
        self.assertEqual(36, len(uuid))

        parts = iter(uuid.split("-"))
        self.assertEqual(8, len(next(parts)))
        self.assertEqual(4, len(next(parts)))
        self.assertEqual(4, len(next(parts)))
        self.assertEqual(4, len(next(parts)))
        self.assertEqual(12, len(next(parts)))

        self.assertEqual(s.md5(), "".join(uuid.split("-")))

    def test_uuid_1(self):
        s = String("12345678-9abc-defg-hijk-lmnopqrstuvw")
        self.assertEqual(s.md5_uuid(), s.uuid())

        s = String("foo")
        self.assertNotEqual(s, str(s.uuid()))

        s = String("a633ce9c-bf50-9309-b9fa-3c9fb0735467")
        self.assertEqual(s, str(s.uuid()))

    def test_uuid_2(self):
        s = String("urn:uuid:5730e1fb-647d-4c7b-8f0d-04e70dc1682b")
        self.assertEqual("5730e1fb-647d-4c7b-8f0d-04e70dc1682b", str(s.uuid()))


class NamingConventionTest(TestCase):
    def test_camelcase(self):
        s = NamingConvention("foo_bar").camelcase()
        self.assertEqual("FooBar", s)

        s = NamingConvention("foo BAR").camelcase()
        self.assertEqual("FooBar", s)

    def test_snakecase_1(self):
        s = NamingConvention("FooBar").snakecase()
        self.assertEqual("foo_bar", s)

        s = NamingConvention("foo_bar_FooBar").snakecase()
        self.assertEqual("foo_bar_foo_bar", s)

    def test_snakecase_acronym_1(self):
        s = NamingConvention("FooBAR")
        self.assertEqual("foo_bar", s.snakecase())

    def test_snakecase_acronym_2(self):
        s = NamingConvention("FooBAR-Test")
        self.assertEqual("foo_bar_test", s.snakecase())

        s = NamingConvention("FooBAR Test")
        self.assertEqual("foo_bar_test", s.snakecase())

        s = NamingConvention("FooBAR_Test")
        self.assertEqual("foo_bar_test", s.snakecase())

        s = NamingConvention("FooBARTest")
        self.assertEqual("foo_bar_test", s.snakecase())

    def test_name(self):
        s = NamingConvention("FooBar")
        self.assertEqual("Foo_Bar", s.underscore())
        self.assertEqual("Foo-Bar", s.dash())
        a = set([
            "FooBar",
            "foobar",
            "Foo_Bar",
            "foo_bar",
            "Foo-Bar",
            "foo-bar"
        ])
        self.assertEqual(a, s.variations(upper=False))

        s = NamingConvention("Foo-Bar")
        self.assertEqual("Foo_Bar", s.underscore())
        self.assertEqual("Foo-Bar", s.dash())
        a = set(["Foo_Bar", "foo_bar", "Foo-Bar", "foo-bar"])
        self.assertEqual(a, s.variations(upper=False))

        s = NamingConvention("Foo_Bar")
        self.assertEqual("Foo_Bar", s.underscore())
        self.assertEqual("Foo-Bar", s.dash())
        a = set(["Foo_Bar", "foo_bar", "Foo-Bar", "foo-bar"])
        self.assertEqual(a, s.variations(upper=False))

        s = NamingConvention("Foo_bar")
        self.assertEqual("Foo_bar", s.underscore())
        self.assertEqual("Foo-bar", s.dash())
        a = set(["Foo_bar", "foo_bar", "Foo-bar", "foo-bar"])
        self.assertEqual(a, s.variations(upper=False))

    def test_varname(self):
        s = NamingConvention("Foo Bar")
        self.assertEqual("foo_bar", s.varname())

    def test_lower_camelcase(self):
        s = NamingConvention("FooBar")
        self.assertEqual("fooBar", s.lower_camelcase())

    def test_split(self):
        s = NamingConvention("FooBar")
        self.assertEqual(["Foo", "Bar"], s.split())

        s = NamingConvention("FooBar Che-Baz")
        self.assertEqual(["Foo", "Bar", "Che", "Baz"], s.split())

    def test_variations(self):
        s = NamingConvention("FooBar")
        vs = s.variations()
        self.assertTrue("foobar" in vs)
        self.assertTrue("FOOBAR" in vs)
        self.assertTrue("foo-bar" in vs)
        self.assertTrue("foo_bar" in vs)

    def test_punctuation(self):
        s = NamingConvention("foo.bar")
        self.assertEqual("fooBar", s.lower_camelcase())

    def test_cli(self):
        s = NamingConvention("foo_bar")
        self.assertEqual("--foo-bar", s.cli_keyword())
        self.assertEqual("foo_bar", s.cli_positional())
        self.assertEqual("foo_bar", s.cli_dest())
        self.assertEqual("FOO_BAR", s.cli_metavar())

        s = NamingConvention("f")
        self.assertEqual("-f", s.cli_keyword())
        self.assertEqual("f", s.cli_dest())
        self.assertEqual("F", s.cli_metavar())


class EnglishWordTest(TestCase):
    def test_syllables(self):
        w = EnglishWord("bus")
        self.assertEqual(1, len(w.syllables()))

        w = EnglishWord("potato")
        self.assertEqual(3, len(w.syllables()))

    def test_plural(self):
        tests = {
            "cat": "cats",
            "house": "houses",
            "bus": "buses",
            "truss": "trusses",
            "marsh": "marshes",
            "lunch": "lunches",
            "tax": "taxes",
            "blitz": "blitzes",
            "class": "classes",
            "wife": "wives",
            "wolf": "wolves",
            "roof": "roofs",
            "belief": "beliefs",
            "chef": "chefs",
            "chief": "chiefs",
            "city": "cities",
            "puppy": "puppies",
            "ray": "rays",
            "boy": "boys",
            "potato": "potatoes",
            "tomato": "tomatoes",
            "photo": "photos",
            "piano": "pianos",
            "halo": "halos",
            "gas": "gases",
            "volcano": "volcanos",
            "cactus": "cactuses", # cacti
            "focus": "focuses", # foci
            "analysis": "analyses",
            "ellipsis": "ellipses",
            "phenomenon": "phenomena",
            "child": "children",
            "goose": "geese",
            "man": "men",
            "woman": "women",
            "tooth": "teeth",
            "foot": "feet",
            "mouse": "mice",
            "person": "people",
        }

        for singular, plural in tests.items():
            self.assertEqual(
                plural,
                EnglishWord(singular).plural(),
                f"{singular} -> {plural}",
            )


class ByteStringTest(TestCase):
    def test_conversion(self):
        s = testdata.get_unicode()
        bs = ByteString(s)
        bs2 = ByteString(bs)

        self.assertEqual(bs, bs2)
        self.assertEqual(s, bs.unicode())
        self.assertEqual(s, bs2.unicode())
        self.assertEqual(s, unicode(bs2))
        # self.assertNotEqual(s, bytes(bs2)) # this prints a UnicodeWarning

    def test_unicode(self):
        s = ByteString(testdata.get_unicode())
        s2 = String(s)
        s3 = ByteString(s2)
        self.assertEqual(s, s3)

    def test_int(self):
        s = ByteString(10)
        self.assertEqual(b'10', s)

    def test_bytestring(self):
        s = ByteString(1)
        self.assertEqual(b"1", s)

        s = ByteString("foo")
        self.assertEqual(b"foo", s)

        s = ByteString(True)
        self.assertEqual(b"True", s)

        with self.assertRaises(TypeError):
            s = ByteString(None)

        su = testdata.get_unicode()
        s = ByteString(su)
        self.assertEqual(su, s.unicode())


class CharacterTest(TestCase):
    """
    NOTE: some tests will fail with narrow unicode: `sys.maxunicode == 65535`
    """
    def test_repr(self):
        # http://www.fileformat.info/info/unicode/char/267cc/index.htm
        ch = Character("\uD859\uDFCC")
        self.assertEqual("\\xf0\\xa6\\x9f\\x8c", ch.repr_bytes())
        self.assertEqual("\\uD859\\uDFCC", ch.repr_string())

    def test_width(self):
        ch = Character("\uD859\uDFCC")
        self.assertEqual(2, ch.width())

        ch = Character("\uD83D\uDC68\uFE0F")
        self.assertEqual(2, ch.width())

        # wide characters:
        # https://www.reddit.com/r/Unicode/comments/5qa7e7/widestlongest_unicode_characters_list/ 

        # it feels like this one should be 2 characters wide
        # https://unicode-table.com/en/102A/
        # https://www.fileformat.info/info/unicode/char/102a/index.htm
        ch = Character("\u102A")
        self.assertEqual(1, ch.width())

        # it feels like this one should be 3 characters wide
        ch = Character("\uFDFD")
        self.assertEqual(1, ch.width())

    def test_is_complete(self):
        # https://www.fileformat.info/info/unicode/char/fffd/index.htm
        ch = Character("\uFFFD")
        self.assertTrue(ch.is_complete())

        ch = Character("\uDFCC")
        self.assertFalse(ch.is_complete())

        ch = Character("\U0001F642")
        self.assertTrue(ch.is_complete())

        # d859 and dfcc are surrogates
        ch = Character("\uD859\uDFCC")
        self.assertFalse(ch.is_complete())

        ch = Character("\U0001F441\u200D\U0001F5E8")
        self.assertFalse(ch.is_complete())

        ch = Character("\u102A")
        self.assertTrue(ch.is_complete())

    def test_integers(self):
        s = "\U0001F441\u200D\U0001F5E8"
        u = Character(s)
        self.assertEqual([128065, 8205, 128488], u.integers())

        u = Character([128065, 8205, 128488])
        self.assertEqual([128065, 8205, 128488], u.integers())

    def test_create(self):
        s = "\U0001F441\u200D\U0001F5E8"
        codepoints = ["1F441", "200D", "1F5E8"]

        u = Character(s)
        self.assertEqual(s, u)
        self.assertEqual(codepoints, u.hexes)

        u = Character(codepoints)
        self.assertEqual(s, u)
        self.assertEqual(codepoints, u.hexes)

        codepoints = "1F468 1F3FB 200D 1F9B0"
        u = Character(codepoints)
        self.assertEqual(codepoints.split(" "), u.hexes)

        codepoints = "1F468"
        u = Character(codepoints)
        self.assertEqual([codepoints], u.hexes)

        codepoints = "1F468-1F3FB-200D-1F9B0"
        u = Character(codepoints)
        self.assertEqual(codepoints.split("-"), u.hexes)

    def test_names_1(self):
        codepoints = ["200D"]
        u = Character(codepoints)
        self.assertEqual("ZERO WIDTH JOINER", u.names()[0])

    def test_lowercase(self):
        codepoints = '1f44f-1f3ff'
        u = Character(codepoints)
        self.assertEqual(['1F44F', '1F3FF'], u.hexes)

        codepoints = "1F468-1F3FB-200D-1F9B0"
        u = Character(codepoints)
        self.assertEqual(["1F468", "1F3FB", "200D", "1F9B0"], u.hexes)

    def test_html_chars(self):
        u = Character(b'\xf0\x9f\xa4\xa6&zwj;\xe2\x99\x80\xef\xb8\x8f')
        self.assertEqual(["1F926", "200D", "2640", "FE0F"], u.hexes)


class CodepointTest(TestCase):
    def test_character(self):
        c = Codepoint("\U0001F441")
        self.assertEqual("1F441", c.hex)
        self.assertEqual("\U0001F441", c)

        c = Codepoint("\u200D")
        self.assertEqual("200D", c.hex)
        self.assertEqual("\u200D", c)

    def test_int(self):
        c = Codepoint("\U0001F441")
        self.assertEqual(128065, int(c))

        c = Codepoint("\u200D")
        self.assertEqual(8205, int(c))

    def test_create(self):
        c = Codepoint(128065)
        self.assertEqual("1F441", c.hex)

        c = Codepoint(0x1F441)
        self.assertEqual("1F441", c.hex)

        c = Codepoint(b"1F441")
        self.assertEqual("1F441", c.hex)

        c = Codepoint("&zwj;")
        self.assertEqual("200D", c.hex)

        c = Codepoint("U+1F468")
        self.assertEqual("1F468", c.hex)

        c = Codepoint("u+200D")
        self.assertEqual("200D", c.hex)

        c = Codepoint("\u200D")
        self.assertEqual("200D", c.hex)


class PasswordTest(TestCase):
    def test_gensalt(self):
        salt = Password.gensalt()
        self.assertEqual(32, len(salt))

    def test_genprefix(self):
        salt = Password.gensalt()
        prefix, pkwargs = Password.genprefix(salt)
        self.assertEqual(1, prefix.count("."))
        self.assertEqual(5, prefix.count("$"))

    def test_hashpw(self):
        pwhash = Password.hashpw("foo bar che")
        self.assertEqual(1, pwhash.count("."))
        self.assertEqual(5, pwhash.count("$"))

    def test_checkpw(self):
        pw = self.get_string()
        pwhash = Password.hashpw(pw)
        r = Password.checkpw(pw, pwhash)
        self.assertTrue(r)

