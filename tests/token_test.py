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
)


from . import TestCase as _TestCase, testdata


class TestCase(_TestCase):
    def create_instance(self, buffer, **kwargs):
        if isinstance(buffer, list):
            if buffer[-1] != "":
                buffer.append("")
            buffer = "\n".join(buffer)

        return self.tokenizer_class(buffer, **kwargs)


class WordTokenizerTest(TestCase):
    tokenizer_class = WordTokenizer

    def create_instance(self, buffer, delims=None):
        tokenizer = super().create_instance(buffer, delims=delims)
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
        token = t.prev()
        self.assertEqual(None, token)

        t.seek(4)
        token = t.prev()
        self.assertEqual("0123", String(token))

        t.seek(2)
        token = t.prev()
        self.assertEqual(None, token)

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
        token = t.prev()
        self.assertEqual(None, token)

    def test_prev_2(self):
        t = self.create_instance("foo bar che")
        self.assertIsNone(t.prev())

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

        t.reset()
        self.assertEqual(2, len(t.readall()))

    def test_unicode_pure(self):
        text = testdata.get_unicode_words(100)
        t = self.create_instance(text)
        # really, we just need .readall() not to raise an error and we know it worked
        self.assertGreaterEqual(100, len(t.readall()))

    def test_unicode_mixed(self):
        """make sure mixed unicode and ascii work as expected"""
        text = testdata.get_words(100)
        t = self.create_instance(text)
        # really, we just need .readall() not to raise an error and we know it worked
        self.assertGreaterEqual(100, len(t.readall()))

    def test_count_total(self):
        t = self.create_instance("foo bar che bam boo")
        total = t.total()
        self.assertEqual(total, t.count())

        t.next()
        t.next()
        self.assertEqual(3, t.count())
        self.assertLess(t.count(), t.total())
        self.assertEqual(total, t.total())
        self.assertEqual(total, len(t))

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
        s = self.create_instance("foo bar \\\[[che]] baz")
        self.assertEqual("foo bar \\\[[", s.read_until_delim("[["))

        s = self.create_instance("foo bar \\[[che]] baz")
        self.assertEqual("foo bar \\[[che]] baz", s.read_until_delim("[["))

        s = self.create_instance("foo bar \\\" che \" baz")
        self.assertEqual("foo bar \\\" che \"", s.read_until_delim("\""))

        s = self.create_instance("foo bar \\\" che \" baz")
        self.assertEqual("foo bar \\\" che ", s.read_to_delim("\""))

    def test_multichar_delim(self):
        text = "before [[foo bar ]] middle [[ che baz]] after"
        s = self.create_instance(text)

        subtext = s.read_to_delim("[[")
        self.assertEqual("before ", subtext)

        subtext = s.read_until_delim("]]")
        self.assertEqual("[[foo bar ]]", subtext)

        subtext = s.read_to_delim("[[")
        self.assertEqual(" middle ", subtext)

        subtext = s.read_until_delim("]]")
        self.assertEqual("[[ che baz]]", subtext)

        subtext = s.read_to_delim("[[")
        self.assertEqual(" after", subtext)


class ABNFTokenizerTest(TestCase):
    tokenizer_class = ABNFGrammar

    def test_or_statement(self):
        t = self.create_instance("foo = bar / che / baz / boo")
        rule = t.next()
        pout.v(rule)
        for options in rule:
            pout.v(options, len(options))



    def test_next_simple(self):
        t = self.create_instance("foo = \"literal1\" rule1 \"literal2\"")
        rule = t.next()
        pout.v(rule)

        return



        t = self.create_instance([
            "foo = bar / che",
            "  / baz",
            "  / boo",
            "bar = cheboo",
        ])

        rule = t.next()



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

    def test_scan_cnl(self):
        with self.assertRaises(ValueError):
            self.create_instance(" ").scan_cnl()

        self.assertTrue(
            self.create_instance("; foo\n").scan_cnl().values[0].is_comment()
        )

        self.assertTrue(
            self.create_instance("\r\n").scan_cnl().values[0].is_crlf()
        )
        self.assertTrue(
            self.create_instance("\n").scan_cnl().values[0].is_crlf()
        )

    def test_scan_cwsp(self):
        self.assertTrue(
            self.create_instance("   ").scan_cwsp().is_cwsp()
        )

        cwsp = self.create_instance("; foo\n ").scan_cwsp()
        self.assertTrue(cwsp.values[0].is_cnl())

        with self.assertRaises(ValueError):
            self.create_instance("; foo\n").scan_cwsp()

    def test_scan_definedas(self):
        with self.assertRaises(ValueError):
            self.create_instance(" ").scan_definedas()

        self.create_instance(" =").scan_definedas()
        self.create_instance(" =/").scan_definedas()
        self.create_instance(" =/ ").scan_definedas()
        self.create_instance("=/ ").scan_definedas()
        self.create_instance("= ").scan_definedas()

    def test_scan_repeat(self):
        r = self.create_instance("*").scan_repeat()
        self.assertEqual([0, 0], r.values)

        r = self.create_instance("1*").scan_repeat()
        self.assertEqual([1, 0], r.values)

        r = self.create_instance("1*2").scan_repeat()
        self.assertEqual([1, 2], r.values)

        r = self.create_instance("*2").scan_repeat()
        self.assertEqual([0, 2], r.values)

    def test_scan_quotedstring(self):
        s = "foo bar che"
        self.assertEqual(
            s,
            self.create_instance(f"\"{s}\"").scan_quotedstring().values[0]
        )

        s = ""
        self.assertEqual(
            s,
            self.create_instance(f"\"{s}\"").scan_quotedstring().values[0]
        )

        with self.assertRaises(ValueError):
            self.create_instance("foo").scan_quotedstring()

    def test_scan_val(self):
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

    def test_scan_proseval(self):
        r = self.create_instance("<foo bar>").scan_proseval()
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

    def test_scan_concatenation(self):
        r = self.create_instance("1foo bar").scan_concatenation()
        self.assertEqual("foo", r.rulename[0].values[0])
        self.assertEqual("bar", r.rulename[1].values[0])

    def test_scan_alternation(self):
        r = self.create_instance("foo | bar | che").scan_alternation()
        self.assertEqual("foo", r.rulename[0].values[0])
        self.assertEqual("bar", r.rulename[1].values[0])
        self.assertEqual("che", r.rulename[2].values[0])

    def test_ruletree(self):
        g = self.create_instance([
            "exp = exp \"+\" term | exp \"-\" term | term",
            "term = term \"*\" power | term \"/\" power | power",
            "power = factor \"^\" power | factor",
            "factor = \"(\" exp \")\" | int",
            "int = 1*DIGIT",
        ])

        head = g.ruletree()
        for rulename in ["exp", "term", "power", "factor", "int"]:
            self.assertTrue(rulename in head.rules)

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


class ABNFDefinitionTest(TestCase):
    tokenizer_class = ABNFGrammar

    def create_instance(self, name, buffer, **kwargs):
        instance = super().create_instance(buffer, **kwargs)
        method = getattr(instance, f"scan_{name}")
        return method()

    def test_val_range(self):
        t = self.create_instance("val", "%xfe34-fffff")
        self.assertEqual(65076, t.min)
        self.assertEqual(1048575, t.max)

        t = self.create_instance("val", "%xfe34")
        self.assertEqual(65076, t.min)
        self.assertEqual(65076, t.max)

        t = self.create_instance("val", "%b110-1100")
        self.assertEqual(6, t.min)
        self.assertEqual(12, t.max)

        t = self.create_instance("val", "%b110")
        self.assertEqual(6, t.min)
        self.assertEqual(6, t.max)

        t = self.create_instance("val", "%d10-200")
        self.assertEqual(10, t.min)
        self.assertEqual(200, t.max)

        t = self.create_instance("val", "%d10")
        self.assertEqual(10, t.min)
        self.assertEqual(10, t.max)


class ABNFParserTest(TestCase):
    tokenizer_class = ABNFParser

    def test_parse_2(self):
        p = self.create_instance([
            "exp = exp \"+\" factor | exp \"-\" factor | factor",
            "factor = 1*DIGIT",
        ])
        p.grammar.parser_rules

        pout.b()

        r = p.exp.parse("6+3")



    def test_parse_1(self):
        p = self.create_instance([
            "exp = exp \"+\" term | exp \"-\" term | term",
            "term = term \"*\" power | term \"/\" power | power",
            "power = factor \"^\" power | factor",
            "factor = \"(\" exp \")\" | 1*DIGIT",
        ])


        r = p.exp.parse("6 + 3")

        return


        r = p.exp.parse("6 + 3 * 4")
        pout.v(r)


    def test_parse_toml(self):
        from datatypes import UrlFilepath
        fp = UrlFilepath("https://raw.githubusercontent.com/toml-lang/toml/1.0.0/toml.abnf")
        p = ABNFParser(fp.read_text())

        pout.v(p.ruletree)

        return

        buffer = Filepath("~/Projects/Testdata/_testdata/pyproject.toml").read_text()

        p.parse(buffer)


        #p.loads('dict = "{" statement *( "," statement ) "}"')


