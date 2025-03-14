# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.string import String
from datatypes.token.base import (
    Scanner,
)
from datatypes.token.word import (
    WordTokenizer,
    StopWordTokenizer,
)
from datatypes.token.abnf import (
    ABNFGrammar,
    ABNFParser,
    ParseError,
)


from . import TestCase as _TestCase, testdata


class TestCase(_TestCase):
    def create_instance(self, buffer="", **kwargs):
        if isinstance(buffer, list):
            if buffer[-1] != "":
                buffer.append("")
            buffer = "\n".join(buffer)

        return self.tokenizer_class(buffer, **kwargs)


class WordTokenizerTest(TestCase):
    tokenizer_class = WordTokenizer

    def create_instance(self, buffer, chars=None):
        tokenizer = super().create_instance(buffer, chars=chars)
        tokenizer.stream = tokenizer.buffer
        return tokenizer

    def test_tell_ldelim(self):
        t = self.create_instance(" 123 567  ABC")

        t.stream.seek(6)
        self.assertEqual(4, t.tell_ldelim())

        t.stream.seek(10)
        self.assertEqual(8, t.tell_ldelim())

        t.stream.seek(9)
        self.assertEqual(8, t.tell_ldelim())

        t.stream.seek(0)
        self.assertEqual(0, t.tell_ldelim())

        t.stream.seek(2)
        self.assertEqual(0, t.tell_ldelim())

        t.stream.seek(6)
        self.assertEqual(4, t.tell_ldelim())

        t = self.create_instance("0123 567  ABC")

        t.stream.seek(0)
        self.assertEqual(-1, t.tell_ldelim())

        t.stream.seek(3)
        self.assertEqual(-1, t.tell_ldelim())

        t = self.create_instance("")
        t.stream.seek(0)
        with self.assertRaises(StopIteration):
            t.tell_ldelim()

        t = self.create_instance("0123456789")

        t.stream.seek(0)
        self.assertEqual(-1, t.tell_ldelim())

        t.stream.seek(4)
        self.assertEqual(-1, t.tell_ldelim())

        t.stream.seek(9)
        self.assertEqual(-1, t.tell_ldelim())

    def test_next_1(self):
        t = self.create_instance(" 123 567  ABC")

        t.stream.seek(10)
        token = t.next()
        self.assertEqual("  ", String(token.ldelim))
        self.assertEqual("ABC", String(token))
        self.assertEqual(None, token.rdelim)

        t.stream.seek(6)
        token = t.next()
        self.assertEqual(" ", String(token.ldelim))
        self.assertEqual("567", String(token))
        self.assertEqual("  ", String(token.rdelim))

        t.stream.seek(9)
        token = t.next()
        self.assertEqual("  ", String(token.ldelim))
        self.assertEqual("ABC", String(token))
        self.assertEqual(None, token.rdelim)

        t.stream.seek(0)
        token = t.next()
        self.assertEqual(" ", String(token.ldelim))
        self.assertEqual("123", String(token))
        self.assertEqual(" ", String(token.rdelim))

        t.stream.seek(2)
        token = t.next()
        self.assertEqual(" ", String(token.ldelim))
        self.assertEqual("123", String(token))
        self.assertEqual(" ", String(token.rdelim))

        t = self.create_instance("0123 567  ABC")

        t.stream.seek(0)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123", String(token))
        self.assertEqual(" ", String(token.rdelim))

        t.stream.seek(3)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123", String(token))
        self.assertEqual(" ", String(token.rdelim))

        t = self.create_instance("")
        t.stream.seek(0)
        with self.assertRaises(StopIteration):
            t.next()

        t = self.create_instance("0123456789")

        t.stream.seek(0)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123456789", String(token))
        self.assertEqual(None, token.rdelim)

        t.stream.seek(4)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123456789", String(token))
        self.assertEqual(None, token.rdelim)

        t.stream.seek(9)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123456789", String(token))
        self.assertEqual(None, token.rdelim)

        t = self.create_instance("0123456789   ")

        t.stream.seek(9)
        token = t.next()
        self.assertEqual(None, token.ldelim)
        self.assertEqual("0123456789", String(token))
        self.assertEqual("   ", String(token.rdelim))

        t.stream.seek(10)
        with self.assertRaises(StopIteration):
            t.next()

    def test_next_2(self):
        t = self.create_instance("123 567")

        token = t.next()
        self.assertEqual("123", String(token))

        token = t.next()
        self.assertEqual("567", String(token))

        with self.assertRaises(StopIteration):
            t.next()

    def test_next_3(self):
        def callback(ch):
            return ch == "A"
        t = self.create_instance("fooAbarAcheAbooAbaz", callback)

        w = t.next()
        self.assertEqual("foo", String(w))

        w = t.next()
        self.assertEqual("bar", String(w))

        w = t.next()
        self.assertEqual("che", String(w))

        w = t.next()
        self.assertEqual("boo", String(w))

        w = t.next()
        self.assertEqual("baz", String(w))

        with self.assertRaises(StopIteration):
            t.next()

    def test_next_4(self):
        def cb(ch):
            return ch.isspace()
        t = self.create_instance("september 15-17, 2019", cb)
        self.assertEqual(["september", "15-17,", "2019"], [String(w) for w in t])

        def cb(ch):
            return String(ch).ispunc() or ch.isspace()
        t = self.create_instance("september 15-17, 2019", cb)
        tokens = [w for w in t]
        self.assertEqual(["september", "15", "17", "2019"], [String(w) for w in tokens])
        self.assertTrue("-", tokens[1].rdelim)
        self.assertTrue("-", tokens[2].ldelim)

    def test_prev_1(self):
        s = "0123 567 9ABC"
        t = self.create_instance(s)

        t.seek(0)
        with self.assertRaises(StopIteration):
            token = t.prev()
            #self.assertEqual(None, token)

        t.seek(4)
        token = t.prev()
        self.assertEqual("0123", String(token))

        t.seek(2)
        with self.assertRaises(StopIteration):
            token = t.prev()
            #self.assertEqual(None, token)

        t.seek(6)
        token = t.prev()
        self.assertEqual("0123", String(token))

        t.seek(len(s))
        token = t.prev()
        self.assertEqual("9ABC", String(token))

        t.seek(len(s))
        token = t.prev()
        self.assertEqual("9ABC", String(token))
        token = t.prev()
        self.assertEqual("567", String(token))
        token = t.prev()
        self.assertEqual("0123", String(token))
        with self.assertRaises(StopIteration):
            token = t.prev()
            #self.assertEqual(None, token)

    def test_prev_2(self):
        t = self.create_instance("foo bar che")
        with self.assertRaises(StopIteration):
            t.prev()
            #self.assertIsNone(t.prev())

        foo = t.next()
        self.assertEqual("foo", String(foo))
        self.assertEqual("foo", String(t.prev()))

        t.next() # t.prev() would move us back to before foo, so skip it
        bar = t.next()
        self.assertEqual("bar", String(bar))
        self.assertEqual("bar", String(t.prev()))

        t.next()
        che = t.next()
        self.assertEqual("che", String(che))
        self.assertEqual("che", String(t.prev()))

    def test_read_1(self):
        t = self.create_instance("0123 567  ABC")

        t.stream.seek(0)
        tokens = t.read(2)
        self.assertEqual(2, len(tokens))
        self.assertEqual("0123", String(tokens[0]))
        self.assertEqual("567", String(tokens[1]))

        t.stream.seek(0)
        tokens = t.read(5)
        self.assertEqual(3, len(tokens))
        self.assertEqual("0123", String(tokens[0]))
        self.assertEqual("567", String(tokens[1]))
        self.assertEqual("ABC", String(tokens[2]))

        t.stream.seek(0)
        tokens = t.read()
        self.assertEqual(3, len(tokens))
        self.assertEqual("0123", String(tokens[0]))
        self.assertEqual("567", String(tokens[1]))
        self.assertEqual("ABC", String(tokens[2]))

    def test_read_2(self):
        t = self.create_instance("foo 07 19")
        t.seek(4)

        r = t.read(2)
        self.assertEqual(2, len(r))
        self.assertEqual("07", String(r[0]))
        self.assertEqual("19", String(r[1]))
        self.assertEqual(None, t.peek())

    def test___iter__(self):
        t = self.create_instance("foo bar")
        r = ""
        for w in t:
            r += String(w)
        self.assertEqual("foobar", r)

    def test_peek(self):
        t = self.create_instance("foo bar. Che? Boom!")
        w = t.next()
        self.assertEqual("foo", String(w))
        self.assertEqual("bar", String(t.peek()))

        w = t.next()
        self.assertEqual("bar", String(w))

        self.assertEqual("Che", String(t.peek()))

        w = t.next()
        self.assertEqual("Che", String(w))

    def test_string_tokenize(self):
        s = String("foo bar che")
        tokens = [t for t in s.tokenize()]
        self.assertEqual(["foo", "bar", "che"], tokens)

    def test_ldelim_failure(self):
        text = "1 2345678"
        t = self.create_instance(text)

        t.seek(3)
        r = t.next()
        self.assertEqual("2345678", r.text)

        t.seek(0)
        self.assertEqual(2, len(t.read()))

    def test_unicode_pure(self):
        text = testdata.get_unicode_words(100)
        t = self.create_instance(text)
        # really, we just need .read() not to raise an error and we know it
        # worked
        self.assertGreaterEqual(100, len(t.read()))

    def test_unicode_mixed(self):
        """make sure mixed unicode and ascii work as expected"""
        text = testdata.get_words(100)
        t = self.create_instance(text)
        # really, we just need .read() not to raise an error and we know it
        # worked
        self.assertGreaterEqual(100, len(t.read()))

    def test_word_sizes_1(self):
        s = "I is the have steps foobar"
        t = self.create_instance(s)
        self.assertEqual(6, len(list(t)))

    def test_word_sizes_2(self):
        s = "foo I bar"
        t = self.create_instance(s)
        self.assertEqual(3, len(list(t)))


class StopWordTokenizerTest(TestCase):
    tokenizer_class = StopWordTokenizer

    def test_words_1(self):
        s = "this IS something I hAVe tO do"
        t = self.create_instance(s)
        self.assertEqual(1, len(list(t)))

    def test_words_2(self):
        s = "foo-bar <there is che>"
        t = self.create_instance(s)
        words = list(t)
        self.assertEqual(3, len(words))


class ScannerTest(TestCase):
    tokenizer_class = Scanner

    def test_escaped(self):
        s = self.create_instance(r"foo bar \\\[[che]] baz")
        self.assertEqual(
            r"foo bar \\\[[",
            s.read_to(delim="[[", include_delim=True)
        )

        s = self.create_instance("foo bar \\[[che]] baz")
        self.assertEqual(
            "foo bar \\[[che]] baz",
            s.read_to(delim="[[", include_delim=True)
        )

        s = self.create_instance("foo bar \\\" che \" baz")
        self.assertEqual(
            "foo bar \\\" che \"",
            s.read_to(delim="\"", include_delim=True)
        )

        s = self.create_instance("foo bar \\\" che \" baz")
        self.assertEqual(
            "foo bar \\\" che ",
            s.read_to(delim="\"")
        )

    def test_read_to_1(self):
        text = "before [[foo bar ]] middle [[ che baz]] after"
        s = self.create_instance(text)

        subtext = s.read_to(delim="[[")
        self.assertEqual("before ", subtext)

        subtext = s.read_to(delim="]]", include_delim=True)
        self.assertEqual("[[foo bar ]]", subtext)

        subtext = s.read_to(delim="[[")
        self.assertEqual(" middle ", subtext)

        subtext = s.read_to(delim="]]", include_delim=True)
        self.assertEqual("[[ che baz]]", subtext)

        subtext = s.read_to(delim="[[")
        self.assertEqual(" after", subtext)

    def test_read_to_2(self):
        delims = ["->", "+>"]

        s = self.create_instance("foo+>bar")
        subtext = s.read_to(delims=delims, include_delim=True)
        self.assertTrue(subtext.endswith("+>"))

        s.seek(0)
        subtext = s.read_to(delims=delims)
        self.assertEqual("foo", subtext)

        s = self.create_instance("foo->bar")
        subtext = s.read_to(delims=delims, include_delim=True)
        self.assertTrue(subtext.endswith("->"))

    def test_read_thru_1(self):
        s = self.create_instance("foo bar")
        subtext = s.read_thru(delim="foo")
        self.assertEqual("foo", subtext)

        subtext = s.read_thru(whitespace=True)
        self.assertEqual(" ", subtext)

        subtext = s.read_thru(delims=["bar"])
        self.assertEqual("bar", subtext)

        s = self.create_instance("foo bar")

        subtext = s.read_thru(delim="bar")
        self.assertEqual("", subtext)
        self.assertEqual(0, s.tell())

        subtext = s.read_thru(delim="foo", include_delim=False)
        self.assertEqual("", subtext)
        self.assertEqual(3, s.tell())

        s = self.create_instance("foo bar")
        subtext = s.read_thru(delim="foo", include_delim=True)
        self.assertEqual("foo", subtext)
        self.assertEqual(3, s.tell())

    def test_read_thru_2(self):
        s = self.create_instance("foobar")
        delims = {"f": 1, "o": 1}

        subtext = s.read_thru(chars="fo")
        self.assertEqual("foo", subtext)
        self.assertEqual(3, s.tell())

    def test_read_between_1(self):
        s = self.create_instance("/* foo bar */ che")
        subtext = s.read_between(start_delim="/*", stop_delim="*/")
        self.assertEqual("/* foo bar */", subtext)

        s = self.create_instance("(foo bar (che))")
        subtext = s.read_between(start_delim="(", stop_delim=")")
        self.assertEqual("(foo bar (che))", subtext)

    def test_read_between_2(self):
        s = self.create_instance("```foo bar ```che``` bam``` after")
        subtext = s.read_between(delim="```")
        self.assertEqual("```foo bar ```", subtext)
        self.assertEqual(14, s.tell())

        s = self.create_instance("```foo bar ``` after")
        subtext = s.read_between(start_delim="```", stop_delim="```")
        self.assertEqual("```foo bar ```", subtext)
        self.assertEqual(14, s.tell())

        s = self.create_instance(r"```foo bar \``` che ``` after")
        subtext = s.read_between(delim="```")
        self.assertEqual(r"```foo bar \``` che ```", subtext)

    def test_read_between_include_delim(self):
        s = self.create_instance("(foo bar) after")
        subtext = s.read_between(
            start_delim="(",
            stop_delim=")",
            include_delim=False
        )
        self.assertEqual("foo bar", subtext)
        self.assertEqual(9, s.tell())

        s = self.create_instance("`foo bar` after")
        subtext = s.read_between(
            start_delim="`",
            stop_delim="`",
            include_delim=False
        )
        self.assertEqual("foo bar", subtext)
        self.assertEqual(9, s.tell())

    def test_read_between_no_stop(self):
        s = self.create_instance("(foo bar")
        subtext = s.read_between(start_delim="(", stop_delim=")")
        self.assertEqual("", subtext)
        self.assertEqual(0, s.tell())

        s = self.create_instance("```foo bar")
        subtext = s.read_between(delim="```", include_delim=False)
        self.assertEqual("", subtext)
        self.assertEqual(0, s.tell())

        s = self.create_instance("```foo bar")
        subtext = s.read_between(delim="```")
        self.assertEqual("", subtext)
        self.assertEqual(0, s.tell())

    def test__normalize_delims(self):
        s = self.create_instance()
        delims = s._normalize_delims(
            delim="foo",
            delims=["bar", "che"],
            chars="abc",
            char="d",
            whitespace=True
        )

        for delim in ["foo", "che", "d", "\n"]:
            self.assertTrue(delim in delims)

    def test__read_to_delim_1(self):
        s = self.create_instance("foo (bar)")

        partial, delim, delim_len = s._read_to_delim({"(": 1})
        self.assertEqual("foo ", partial)
        self.assertEqual("(", delim)
        self.assertEqual(4, s.tell())

        partial, delim, delim_len = s._read_to_delim({")": 1})
        self.assertEqual("(bar", partial)
        self.assertEqual(")", delim)
        self.assertEqual(8, s.tell())

    def test__read_to_delim_2(self):
        s = self.create_instance("12 */ 34")
        t = s._read_to_delim({"/*": 2, "*/": 2})
        self.assertEqual("12 ", t[0])
        self.assertEqual("*/", t[1])
        self.assertEqual(3, s.tell())

    def test__read_thru_delim_1(self):
        s = self.create_instance("foobar")

        partial, delim, delim_len = s._read_thru_delim({"bar": 3})
        self.assertEqual("", partial)
        self.assertEqual("", delim)
        self.assertEqual(0, delim_len)
        self.assertEqual(0, s.tell())

        partial, delim, delim_len = s._read_thru_delim({"foo": 3})
        self.assertEqual("foo", partial)
        self.assertEqual("foo", delim)
        self.assertEqual(0, s.tell())

        s.seek(s.tell() + delim_len)

        partial, delim, delim_len = s._read_thru_delim({"bar": 3})
        self.assertEqual("bar", partial)
        self.assertEqual("bar", delim)
        self.assertEqual(3, s.tell())

    def test_read_to_ignore_between(self):
        s = self.create_instance("<p data=\"foo>bar\">after")

        partial = s.read_to(
            chars=">",
            ignore_between_char="\"",
            include_delim=True
        )
        self.assertEqual("<p data=\"foo>bar\">", partial)

    def test_read_between_ignore_between(self):
        s = self.create_instance("<p data=\"foo>bar\">after")
        partial = s.read_between(
            start_char="<",
            stop_char=">",
            ignore_between_char="\"",
            include_delim=True
        )
        self.assertEqual("<p data=\"foo>bar\">", partial)

        s = self.create_instance("|data=(foo|bar)|after")
        partial = s.read_between(
            char="|",
            ignore_between_start_char="(",
            ignore_between_stop_char=")",
            include_delim=True
        )
        self.assertEqual("|data=(foo|bar)|", partial)

        s = self.create_instance("|data=(foo|bar)|after")
        partial = s.read_between(
            char="|",
            include_delim=True
        )
        self.assertEqual("|data=(foo|", partial)

    def test_convert_escaped(self):
        s = self.create_instance(
            r"|before 1\|after 1|" + "\n" + r"|before 2\|after 2|",
            convert_escaped=True
        )
        data = s.read()
        self.assertEqual("|before 1|after 1|\n|before 2|after 2|", data)

        s = self.create_instance(
            r"|before 1\|after 1|" + "\n" + r"|before 2\|after 2|",
            convert_escaped=True
        )
        line = s.readline()
        self.assertEqual("|before 1|after 1|\n", line)
        line = s.readline()
        self.assertEqual("|before 2|after 2|", line)

        s = self.create_instance(
            r"|before 1\|after 1|" + "\n" + r"|before 2\|after 2|",
            convert_escaped=True
        )
        with self.assertRaises(Exception):
            lines = s.readlines()


class ABNFGrammarTest(TestCase):
    tokenizer_class = ABNFGrammar

    def test_read_rule(self):
        t = self.create_instance([
            "foo = bar / che",
            "  / baz",
            "  / boo",
            "bar = cheboo",
        ])

        rule = t.read_rule()
        for part in ["foo = bar / che", "/ baz", "/ boo"]:
            self.assertTrue(part in rule)

        self.assertEqual("bar = cheboo", t.read_rule())

        self.assertEqual("", t.read_rule())

    def test_scan_rulename(self):
        t = self.create_instance("foobar")
        self.assertEqual("foobar", t.scan_rulename().values[0])

        t = self.create_instance("foobar = ")
        self.assertEqual("foobar", t.scan_rulename().values[0])

        t = self.create_instance("foo-bar = ")
        self.assertEqual("foo-bar", t.scan_rulename().values[0])

        t = self.create_instance("foo_bar")
        self.assertEqual("foo", t.scan_rulename().values[0])

        with self.assertRaises(ValueError):
            self.create_instance(" = ").scan_rulename()

    def test_scan_comment(self):
        t = self.create_instance("; foo bar\n")
        self.assertEqual("foo bar", t.scan_comment().values[0])

        t = self.create_instance(";\r\n")
        self.assertEqual("", t.scan_comment().values[0])

        t = self.create_instance(";\n")
        self.assertEqual("", t.scan_comment().values[0])

        with self.assertRaises(ValueError):
            self.create_instance("; foo bar").scan_comment()

        with self.assertRaises(ValueError):
            self.create_instance("foo bar").scan_comment()

    def test_scan_c_nl(self):
        with self.assertRaises(ValueError):
            self.create_instance(" ").scan_c_nl()

        self.assertTrue(
            self.create_instance("; foo\n").scan_c_nl().values[0].is_comment()
        )

        self.assertTrue(
            self.create_instance("\r\n").scan_c_nl().values[0].is_crlf()
        )
        self.assertTrue(
            self.create_instance("\n").scan_c_nl().values[0].is_crlf()
        )

    def test_scan_c_wsp(self):
        self.assertTrue(
            self.create_instance("   ").scan_c_wsp().is_c_wsp()
        )

        cwsp = self.create_instance("; foo\n ").scan_c_wsp()
        self.assertTrue(cwsp.values[0].is_c_nl())

        with self.assertRaises(ValueError):
            self.create_instance("; foo\n").scan_c_wsp()

    def test_scan_defined_as(self):
        with self.assertRaises(ValueError):
            self.create_instance(" ").scan_defined_as()

        self.create_instance(" =").scan_defined_as()
        self.create_instance(" =/").scan_defined_as()
        self.create_instance(" =/ ").scan_defined_as()
        self.create_instance("=/ ").scan_defined_as()
        self.create_instance("= ").scan_defined_as()

    def test_scan_repeat(self):
        r = self.create_instance("*").scan_repeat()
        self.assertEqual([0, 0], r.values)

        r = self.create_instance("1*").scan_repeat()
        self.assertEqual([1, 0], r.values)

        r = self.create_instance("1*2").scan_repeat()
        self.assertEqual([1, 2], r.values)

        r = self.create_instance("*2").scan_repeat()
        self.assertEqual([0, 2], r.values)

    def test_scan_quoted_string(self):
        s = "foo bar che"
        self.assertEqual(
            s,
            self.create_instance(f"\"{s}\"").scan_quoted_string().values[0]
        )

        s = ""
        self.assertEqual(
            s,
            self.create_instance(f"\"{s}\"").scan_quoted_string().values[0]
        )

        with self.assertRaises(ValueError):
            self.create_instance("foo").scan_quoted_string()

    def test_scan_val_1(self):
        s = "12343567890"
        self.assertEqual(
            s,
            self.create_instance(f"%d{s}").scan_val().values[-1]
        )

        with self.assertRaises(ValueError):
            self.create_instance("%d").scan_val()

        s = "01101010101"
        self.assertEqual(
            s,
            self.create_instance(f"%b{s}").scan_val().values[-1]
        )

        with self.assertRaises(ValueError):
            self.create_instance("%b").scan_val()

        s = "abcdefABCDEF0123456789"
        self.assertEqual(
            s,
            self.create_instance(f"%x{s}").scan_val().values[-1]
        )

        with self.assertRaises(ValueError):
            self.create_instance("%x").scan_val()

        r = self.create_instance("%d10-500").scan_val()
        self.assertEqual("10", r.values[2])
        self.assertEqual("500", r.values[4])

        r = self.create_instance("%s\"foo bar\"").scan_val()
        self.assertEqual("foo bar", r.values[2].values[0])
        self.assertTrue(r.values[2].options["case_sensitive"])

        r = self.create_instance("%i\"foo bar\"").scan_val()
        self.assertEqual("foo bar", r.values[2].values[0])
        self.assertFalse(r.values[2].options["case_sensitive"])

    def test_scan_prose_val(self):
        r = self.create_instance("<foo bar>").scan_prose_val()
        self.assertEqual("foo bar", r.values[0])

    def test_scan_group(self):
        r = self.create_instance("(foo bar)").scan_group()
        concat = r.values[1].values[0]
        elem = concat.values[0].values[1]
        rulename = elem.values[0].values[0]
        self.assertEqual("foo", rulename)

    def test_scan_repetition(self):
        r = self.create_instance("1foo").scan_repetition()
        self.assertEqual([1, 1], r.repeat[0].values)
        self.assertEqual("foo", r.rulename[0].values[0])

        r = self.create_instance("1*DIGIT").scan_repetition()
        self.assertEqual([1, 0], r.repeat[0].values)
        self.assertEqual("DIGIT", r.rulename[0].values[0])

        r = self.create_instance("3*5DIGIT").scan_repetition()
        self.assertEqual([3, 5], r.repeat[0].values)
        self.assertEqual("DIGIT", r.rulename[0].values[0])

    def test_scan_concatenation(self):
        r = self.create_instance("1foo bar").scan_concatenation()
        self.assertEqual("foo", r.rulename[0].values[0])
        self.assertEqual("bar", r.rulename[1].values[0])

    def test_scan_alternation(self):
        r = self.create_instance("foo | bar | che").scan_alternation()
        self.assertEqual("foo", r.rulename[0].values[0])
        self.assertEqual("bar", r.rulename[1].values[0])
        self.assertEqual("che", r.rulename[2].values[0])

    def test_parser_rules(self):
        g = self.create_instance([
            "exp = exp \"+\" term | exp \"-\" term | term",
            "term = term \"*\" power | term \"/\" power | power",
            "power = factor \"^\" power | factor",
            "factor = \"(\" exp \")\" | int",
            "int = 1*DIGIT",
        ])

        for rulename in ["exp", "term", "power", "factor", "int"]:
            self.assertTrue(rulename in g.parser_rules)

    def test_scan_rulelist(self):
        g = self.create_instance([
            ";; first line of comment",
            ";; second line of comment",
            "",
            "foo = DIGIT",
            "",
            ";; third comment",
            "",
            "bar = DIGIT",
            "    ;; fourth comment",
            "che = DIGIT ; fifth comment",
        ])

        r = g.scan_rulelist()

        self.assertEqual(5, len(r.comment))
        self.assertEqual(3, len(r.rule))
        self.assertEqual("foo", r.rule[0].rulename[0].values[0])
        self.assertEqual("bar", r.rule[1].rulename[0].values[0])
        self.assertEqual("che", r.rule[2].rulename[0].values[0])

    def test_core_rules(self):
        g = self.create_instance("")
        g.core_rules() # if there isn't an error then it's working

    def test_rule_merge(self):
        g = self.create_instance([
            "foo = DIGIT",
            "foo =/ ALPHA",
        ])

        foo = g.parser_rules["foo"]
        self.assertTrue(isinstance(foo.values[-1], type(foo)))

        with self.assertRaises(ValueError):
            g = self.create_instance([
                "foo = DIGIT",
                "foo = ALPHA",
            ]).parser_rules

    def test_bad_rulename(self):
        with self.assertRaises(ValueError):
            g = self.create_instance([
                "foo_bar = DIGIT",
            ])
            g.parser_rules

        with self.assertRaises(ValueError):
            g = self.create_instance([
                "foo_bar = DIGIT",
            ])
            g.scan_rulelist()

        with self.assertRaises(ValueError):
            g = self.create_instance([
                "foo_bar = DIGIT",
            ])
            g.scan_rule()


class ABNFDefinitionTest(TestCase):
    tokenizer_class = ABNFGrammar

    def create_instance(self, name, buffer, **kwargs):
        instance = super().create_instance(buffer, **kwargs)
        method = getattr(instance, f"scan_{name}")
        return method()

    def test_val_min_max(self):
        t = self.create_instance("val", "%xfe34-fffff")
        self.assertEqual(65076, t.min)
        self.assertEqual(1048575, t.max)

        t = self.create_instance("val", "%b110-1100")
        self.assertEqual(6, t.min)
        self.assertEqual(12, t.max)
        with self.assertRaises(ValueError):
            t.chars

        t = self.create_instance("val", "%d10-200")
        self.assertEqual(10, t.min)
        self.assertEqual(200, t.max)

    def test_val_chars(self):
        t = self.create_instance("val", "%d97")
        self.assertTrue(t.is_val_chars())
        self.assertFalse(t.is_val_range())
        self.assertEqual([97], t.chars)

        t = self.create_instance("val", "%d97.98.99")
        self.assertTrue(t.is_val_chars())
        self.assertFalse(t.is_val_range())

        self.assertEqual([97, 98, 99], t.chars)

        t = self.create_instance("val", "%d10")
        self.assertEqual([10], t.chars)

        t = self.create_instance("val", "%b110")
        self.assertEqual([6], t.chars)

        t = self.create_instance("val", "%xfe34")
        self.assertEqual([65076], t.chars)
        with self.assertRaises(ValueError):
            t.min
        with self.assertRaises(ValueError):
            t.max

    def test_hex_whitespace(self):
        t = self.create_instance("val", "%x20.09") # 20 is space, 09 is tab
        self.assertEqual([32, 9], t.chars)

    def test_rule_merge(self):
        t = self.create_instance("rule", [
            "foo = DIGIT",
            "foo =/ ALPHA",
            "foo =/ CRLF / CR / LF",
        ]).options["grammar"].parser_rules["foo"]

        self.assertEqual(1, len(t.elements))
        self.assertEqual(1, len(t.alternation))
        self.assertEqual(5, len(t.concatenation))
        body = str(t)
        for b in ["foo = DIGIT", "foo =/ ALPHA", "foo =/ CRLF / CR / LF"]:
            self.assertTrue(b in body)

    def test_defname(self):
        t = self.create_instance("rulename", [
            "foo = DIGIT",
        ])
        self.assertEqual("foo", t.defname)

        t = self.create_instance("rule", [
            "foo = DIGIT",
        ])
        self.assertEqual("foo", t.defname)

    def test___getattr__(self):
        t = self.create_instance("rule", [
            "foo = DIGIT / ALPHA / CRLF",
        ])

        self.assertEqual(4, len(t.rulename))


class ABNFParserTest(TestCase):
    tokenizer_class = ABNFParser

    def create_instance(self, *args, **kwargs):
        instance = super().create_instance(*args, **kwargs)

        # parse the grammar to make sure it's valid
        instance.grammar.parser_rules

        return instance

    def test_push_pop(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | factor",
            "factor = 1*DIGIT",
        ])

        rp = p.exp
        rp.set_buffer("123456")
        r = rp.entry_rule

        ri = rp.push(r)
        self.assertEqual(1, ri["count"])

        with self.assertRaises(ParseError):
            rp.push(r)

        with self.assertRaises(ParseError):
            rp.push(r)

        ri = rp.pop(r)
        self.assertEqual(1, ri["count"])

    def test_parse_numval(self):
        p = self.create_instance([
            "foo = %d49",
        ])

        r = p.foo.parse("1")
        self.assertEqual("foo", r.name)
        self.assertEqual([1], r.values)

    def test_parse_multi_numval(self):
        p = self.create_instance([
            "foo = 1*DIGIT",
        ])

        r = p.foo.parse("12")
        self.assertEqual("foo", r.name)
        self.assertEqual(2, len(r.values))

    def test_parse_charval(self):
        p = self.create_instance([
            "foo = \"bar\"",
        ])

        r = p.foo.parse("bar")
        self.assertEqual("foo", r.name)
        self.assertEqual(1, len(r.values))
        self.assertEqual("bar", r.values[0])

    def test_parse_repetition_1(self):
        p = self.create_instance([
            "one-or-more = 1*DIGIT",
            "two = DIGIT",
            "three-five = 3*5DIGIT",
        ])

        parser = p.three_five
        parser.set_buffer("123456")
        r = parser.parse_repetition(
            p.grammar.parser_rules["three-five"].repetition[0]
        )
        self.assertEqual(5, len(r))
        self.assertEqual(1, r[0].values[0])
        self.assertEqual(5, r[-1].values[0])

        parser = p.two
        parser.set_buffer("654")
        r = parser.parse_repetition(
            p.grammar.parser_rules["two"].repetition[0]
        )
        self.assertEqual(1, len(r))
        self.assertEqual(6, r[0].values[0])

        parser = p.one_or_more
        parser.set_buffer("654")
        r = parser.parse_repetition(
            p.grammar.parser_rules["one-or-more"].repetition[0]
        )
        self.assertEqual(3, len(r))

    def test_parse_repetition_2(self):
        p = self.create_instance([
            "five = 5DIGIT",
        ])
        parser = p.five
        parser.set_buffer("12x3456")

        with self.assertRaises(ParseError):
            parser.parse_repetition(
                p.grammar.parser_rules["five"].repetition[0]
            )

    def test_parse_left_recurse_1a(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | factor",
            "factor = 1*DIGIT",
        ])

        r = p.exp.parse("1+2")
        self.assertEqual("1+2", str(r))
        self.assertEqual("1", str(r.values[0]))
        self.assertEqual("2", str(r.values[2]))

    def test_parse_left_recurse_1b(self):
        p = self.create_instance([
            "exp = exp \"+\" DIGIT / DIGIT",
        ])

        r = p.exp.parse("1+2")
        self.assertEqual("1+2", str(r))
        self.assertEqual("1", str(r.values[0]))
        self.assertEqual("2", str(r.values[2]))

        r = p.exp.parse("1+2+3")
        self.assertEqual("1+2", str(r.values[0]))
        self.assertEqual("3", str(r.values[2]))

    def test_parse_left_recurse_2(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | factor",
            "factor = 1*DIGIT",
        ])

        r = p.exp.parse("1+2+3")
        self.assertEqual("1+2+3", str(r))
        self.assertEqual("1+2", str(r.values[0]))

    def test_parse_left_recurse_3a(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | factor",
            "factor = \"(\" exp \")\" | 1*DIGIT",
        ])

        r = p.exp.parse("(1+2)+3")
        self.assertEqual("(1+2)", str(r.values[0]))
        self.assertEqual("3", str(r.values[2]))

    def test_parse_left_recurse_3b(self):
        p = self.create_instance([
            "exp = exp \"+\" factor / factor",
            "factor = \"(\" exp \")\" / DIGIT",
        ])

        r = p.exp.parse("(1+2)")
        self.assertEqual("(1+2)", str(r))
        self.assertEqual("1+2", str(r.values[0].values[1]))

    def test_parse_left_recurse_4(self):
        p = self.create_instance([
            "exp = exp \"+\" term / term",
            "term = term \"*\" factor / factor",
            "factor = \"(\" exp \")\" / 1*DIGIT",
        ])

        r = p.exp.parse("(1+2)+3*4")
        self.assertEqual("(1+2)+3*4", str(r))

    def test_parse_left_recurse_5(self):
        p = self.create_instance([
            "exp = exp \"+\" power / power",
            "power = factor \"^\" power / factor",
            "factor = \"(\" exp \")\" / 1*DIGIT",
        ])

        r = p.exp.parse("(1+2)+3^4")
        self.assertEqual("(1+2)", str(r.values[0]))
        self.assertEqual("power", r.values[2].name)
        self.assertEqual("3^4", str(r.values[2]))

    def test_parse_left_recurse_6(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | exp \"-\" factor | factor",
            "factor = DIGIT",
        ])

        r = p.exp.parse("1-2")
        self.assertEqual("1-2", str(r))

    def test_parse_left_recurse_7(self):
        p = self.create_instance([
            "exp = exp \"+\" term | exp \"-\" term | term",
            "term = term \"*\" power | term \"/\" power | power",
            "power = factor \"^\" power | factor",
            "factor = \"(\" exp \")\" | 1*DIGIT",
        ])

        r = p.exp.parse("(1-2)+3")
        self.assertEqual("(1-2)", str(r.values[0]))
        self.assertEqual("+", str(r.values[1]))
        self.assertEqual("3", str(r.values[2]))

        r = p.exp.parse("(1-2)+3*4")
        self.assertEqual("(1-2)", str(r.values[0]))
        self.assertEqual("+", str(r.values[1]))
        self.assertEqual("3*4", str(r.values[2]))

    def test_entry_rule_values(self):
        p = self.create_instance([
            "foo = DIGIT *DIGIT",
        ])

        r = p.foo.parse("1234")
        self.assertEqual(4, len(r.values))

    def test_parse_rule_1(self):
        p = self.create_instance([
            "foo = *DIGIT",
        ])

        r = p.foo.parse("xy", partial=True)
        self.assertEqual(0, len(r.values))

    def test_parse_rule_2(self):
        p = self.create_instance([
            "foo = \"#\" DIGIT",
        ])

        with self.assertRaises(ParseError):
            p.foo.parse("xy")

    def test_parse_rule_3(self):
        p = self.create_instance([
            "foo = *DIGIT / *ALPHA",
        ])

        r = p.foo.parse("xy")
        self.assertEqual(2, len(r.values))

        r = p.foo.parse("--", partial=True)
        self.assertEqual(0, len(r.values))

    def test_parse_option(self):
        p = self.create_instance([
            "foo = DIGIT [ DIGIT ]",
        ])
        r = p.foo.parse("1x", partial=True)
        self.assertEqual(1, r.values[0].values[0])
        self.assertEqual(1, len(r.values))
        r = p.foo.parse("12")
        self.assertEqual(2, len(r.values))

        p = self.create_instance([
            "foo = DIGIT [ DIGIT 1*DIGIT ]",
        ])
        r = p.foo.parse("1234")
        self.assertEqual(4, len(r.values))
        r = p.foo.parse("1")
        self.assertEqual(1, len(r.values))

    def test_parse_merge(self):
        p = self.create_instance([
            "foo = ws DIGIT *( ws DIGIT )",
            "ws = *wschar",
            "wschar =  %x20  ; Space",
            "wschar =/ %x09  ; Horizontal tab",
        ])

        r = p.foo.parse("1 2 3 4")
        self.assertEqual(8, len(r.values))
        self.assertEqual(4, len(r.digit))

        r = p.foo.parse(" 1 2 3 4")
        self.assertEqual(8, len(r.values))
        self.assertEqual(4, len(r.digit))

    def test_parse_1(self):
        p = self.create_instance([
            "foo = ws [ comment ]",
            "foo =/ ws table ws [ comment ]",
            "ws = *wschar",
            "wschar =  %x20  ; Space",
            "wschar =/ %x09  ; Horizontal tab",
            "comment = %x23 *\"2\"",
            "table = %x5B 1*(\"1\") %x5D",
        ])

        r = p.foo.parse("[1]")
        self.assertEqual("", str(r.values[0]))
        self.assertEqual("[1]", str(r.values[1]))

    def test_parse_2(self):
        p = self.create_instance([
            "foo = ws [ comment ]",
            "foo =/ ws DIGIT ws [ comment ]",
            "foo =/ ws table ws [ comment ]",
            "ws = *wschar",
            "wschar =  %x20  ; Space",
            "wschar =/ %x09  ; Horizontal tab",
            "comment-start-symbol = %x23 ; #",
            "non-ascii = %x80-D7FF / %xE000-10FFFF",
            "non-eol = %x09 / %x20-7F / non-ascii",
            "comment = comment-start-symbol *non-eol",
            "table = std-table-open 1*(ALPHA / \"-\") std-table-close",
            "std-table-open  = %x5B ws     ; [ Left square bracket",
            "std-table-close = ws %x5D     ; ] Right square bracket",
        ])

        r = p.foo.parse("[build-system]")
        self.assertEqual("[build-system]", str(r.values[1]))

    def test_parse_alternation(self):
        p = self.create_instance([
            "key = simple-key / dotted-key",
            "simple-key = 1*ALPHA",
            "dotted-key = simple-key 1*( %x2E simple-key )",
        ])

        parser = p.key
        parser.set_buffer("foo.bar")
        r = parser.parse_alternation(
            next(p.grammar.parser_rules["key"].values[2].tokens("alternation"))
        )
        self.assertEqual("foo.bar", str(r[0]))

        parser = p.key
        parser.set_buffer("foo")
        r = parser.parse_alternation(
            next(p.grammar.parser_rules["key"].values[2].tokens("alternation"))
        )
        self.assertEqual("foo", str(r[0]))

        r = p.key.parse("foo.bar")
        self.assertEqual("foo.bar", str(r))

        r = p.key.parse("foo")
        self.assertEqual("foo", str(r))

    def test_parse_chars(self):
        p = self.create_instance([
            "true    = %x74.72.75.65     ; true",
            "false   = %x66.61.6C.73.65  ; false"
        ])

        r = p.true.parse("true")
        self.assertEqual("true", str(r))

        r = p.false.parse("false")
        self.assertEqual("false", str(r))

