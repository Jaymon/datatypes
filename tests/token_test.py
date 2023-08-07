# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.string import String
from datatypes.token import (
    Tokenizer,
    StopWordTokenizer,
    Scanner,
)

from . import TestCase, testdata


class TokenizerTest(TestCase):
    def create_instance(self, s, delims=None):
        tokenizer = Tokenizer(s, delims) if delims else Tokenizer(s)
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
    def create_instance(self, s):
        tokenizer = StopWordTokenizer(s)
        return tokenizer

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
    def create_instance(self, s):
        return Scanner(s)

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

