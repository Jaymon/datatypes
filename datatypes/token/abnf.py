# -*- coding: utf-8 -*-
from contextlib import contextmanager
from collections import defaultdict
import itertools
import functools

from ..compat import *
from .. import logging
from ..string import String
from ..decorators import property as cachedproperty
from ..utils import batched
from ..number import Binary, Hex
from .base import Token, Tokenizer, Scanner


logger = logging.getLogger(__name__)


class ParseError(ValueError):
    """Raised in ABNFParser when buffer can't be parsed"""
    pass


class GrammarError(ValueError):
    """Raised in ABNFGrammar when the grammar can't be parsed"""
    pass


class ABNFToken(object):
    """Returned by the ABNF Parsers"""
    @classmethod
    def normalize_name(cls, name):
        # ABNF keys can't contain underscores but python attribute names can't
        # contain dashes and rule names are case-insensitive
        return name.replace("_", "-").lower()

    def __init__(self, name, values, start, stop, **options):
        self.name = self.normalize_name(name)
        self.values = values
        self.start = start
        self.stop = stop
        self.options = options

    def __str__(self):
        if "parser" in self.options:
            scanner = self.options["parser"].scanner.getvalue()
            return scanner[self.start:self.stop]

        else:
            return self.name

    def __getattr__(self, key):
        if key.startswith("is_"):
            _, name = key.split("_", maxsplit=1)
            name = self.normalize_name(name)
            return lambda *_, **__: self.name == name

        elif not key.startswith("_"):
            name = self.normalize_name(key)
            if values := list(self.tokens(name, depth=0)):
                return values

        raise AttributeError(key)

    def tokens(self, name, depth=1, related=False):
        """Get all the name tokens

        :param name: str, the name of the tokens you want
        :param depth: int, if 1, then this will only return immediate tokens
            that match name. If depth is >1 then it will return up to depth
            levels of name tokens. If depth is <=0 then it will return all
            levels of name tokens. It's handy to have this level of control when
            actually parsing something
        :param related: bool, only matters if depth != 1, if True then this will
            only yield subsequent depths from found name tokens. So if you were
            looking for "foo" tokens and passed in depth=0 and related=True, you
            would get foo.foo... tokens but not bar.foo tokens if that makes
            sense
        :returns: generator, yields name tokens
        """
        vs = []
        for value in self.values:
            if isinstance(value, ABNFToken):
                if not name or name == value.name:
                    yield value
                    if depth > 1 or depth <= 0:
                        vs.append(value)

        if depth > 1 or depth <= 0:
            if related:
                for v in vs:
                    for t in v.tokens(name, depth - 1):
                        yield t

            else:
                for value in self.values:
                    if isinstance(value, ABNFToken):
                        for t in value.tokens(name, depth - 1):
                            yield t


class ABNFDefinition(ABNFToken):
    """Returned by the ABNFGrammar, this hads some helper methods to make it
    easier to manipulate and check ABNF grammars against input to be parsed"""
    @property
    def defname(self):
        """Return the grammar's rulename (ie, the rulename defined in the 
        grammar, I would've loved to name this "rulename" but an ABNF grammar
        has a rulename rule and so there could be a name collision"""
        if self.name == "rule":
            rulename = self.values[0].values[0]

        elif self.name == "rulename":
            rulename = self.values[0]

        else:
            raise ValueError(f"No defname property on {self.name}")

        return rulename

    @property
    def min(self):
        """If we have a repeat or val rule range then this will return the
        minimum range or the minimum amount of times to repeat"""
        if self.is_val_chars():
            raise ValueError(f"No min property on {self.name} with chars")

        if self.is_bin_val():
            ret = int(Binary(self.values[2]))

        elif self.is_dec_val():
            ret = int(self.values[2])

        elif self.is_hex_val():
            ret = int(Hex(self.values[2]))

        elif self.is_repeat():
            ret = int(self.values[0])

        else:
            raise ValueError(f"No min property on {self.name}")

        return ret

    @property
    def max(self):
        """If we have a repeat or val rule range then this will return the
        maximum range or the maximum amount of times to repeat"""
        if self.is_val_chars():
            raise ValueError(f"No max property on {self.name} with chars")

        if self.is_bin_val():
            if len(self.values) >= 5:
                ret = int(Binary(self.values[4]))

            else:
                ret = self.min

        elif self.is_dec_val():
            if len(self.values) >= 5:
                ret = int(self.values[4])

            else:
                ret = self.min

        elif self.is_hex_val():
            if len(self.values) >= 5:
                ret = int(Hex(self.values[4]))

            else:
                ret = self.min

        elif self.is_repeat():
            ret = int(self.values[1])

        else:
            raise ValueError(f"No max property on {self.name}")

        return ret

    @property
    def chars(self):
        """If the val concatenated chars then this will return those chars as a
        list"""
        if self.is_val_range():
            raise ValueError(f"No chars property on {self.name} with range")

        chars = []
        for ch in self.values[2::2]:
            if self.is_bin_val():
                chars.append(int(Binary(ch)))

            elif self.is_dec_val():
                chars.append(int(ch))

            elif self.is_hex_val():
                chars.append(int(Hex(ch)))

        return chars

    def __str__(self):
        if "grammar" in self.options:
            body = [
                self.options["grammar"].getvalue()[self.start:self.stop].strip()
            ]
            for md in self.options.get("merged", []):
                body.append(
                    self.options["grammar"].getvalue()[md.start:md.stop].strip()
                )

            return "{}({})".format(
                self.name,
                ", ".join(body)
            )

        else:
            return super().__str__()

    def is_parsable(self):
        """Return True if this definition is parsable"""
        return not self.is_internal()

    def is_internal(self):
        """Return True if this definition is an internal definition that can
        be safely ignored when checking input against a grammar"""
        return self.is_c_wsp() \
            or self.is_c_nl() \
            or self.is_defined_as() \
            or self.is_comment()

    def is_num_val(self):
        """Return True if this definition is a numval token"""
        return self.is_bin_val() \
            or self.is_dec_val() \
            or self.is_hex_val()

    def is_val_range(self):
        """Return True if this grammar is a numval token and represents a range
        of values"""
        if self.is_num_val():
            return len(self.values) == 5 and self.values[3] == "-"

        return False

    def is_val_chars(self):
        """Return True if this grammar is a numval token and represents a set
        of values"""
        if self.is_num_val():
            return len(self.values) >= 5 and self.values[3] == "." \
                or not self.is_val_range()

        return False

    def parsable(self):
        """Returns all the parsable definition tokens"""
        definitions = []
        for value in self.tokens():
            if value.is_parsable():
                definitions.append(value)

        return definitions

    def merge(self, definition):
        """Merge a rule definition into this rule definition

        :param definition: ABNFDefinition, this will be merged into this rule
            this rule should have been defined using =/
        """
        if self.is_rule() and definition.is_rule():
            # we need to make sure the defined-as definition is =/
            definedas = definition.values[1]
            for v in definedas.values:
                if isinstance(v, str):
                    if v == "=/":
                        # we want to find the alternation of self and append the
                        # concatenation values of definition's alternation

                        # we add rule, elements, and alternation to options more
                        # for logging than anything else

                        elements1 = self.values[2]
                        elements2 = definition.values[2]

                        elements1.options.setdefault("merged", [])
                        elements1.options["merged"].append(elements2)

                        alternation1 = elements1.values[0]
                        alternation2 = elements2.values[0]

                        alternation1.values.extend(alternation2.values)
                        alternation1.options.setdefault("merged", [])
                        alternation1.options["merged"].append(alternation2)

                        self.options.setdefault("merged", [])
                        self.options["merged"].append(definition)
                        break

                    else:
                        raise ValueError(" ".join([
                            f"When merging {self.defname} the second",
                            f"{self.defname} must have an =/",
                        ]))

        else:
            raise ValueError(f"Cannot have 2 {self.defname} defined")

    def ranges(self):
        """For value ranges and concatenations this will yield tuples that can
        be checked against a character

        :returns: generator(tuple[int, int]), the (min, max) of each character
            that has to be checked for the *val rule
        """
        if self.is_val_range():
            yield (self.min, self.max)

        elif self.is_val_chars():
            for ch in self.chars:
                yield (ch, ch)

        else:
            raise ValueError(f"No ranges on {self.name}")


class ABNFGrammar(Scanner):
    """This lexes an ABNF grammar

    This is an internal class used by ABNFParser

    It's a pretty standard lexer that follows rfc5234:

        https://www.rfc-editor.org/rfc/rfc5234

    and the update for char-val in rfc7405:

        https://datatracker.ietf.org/doc/html/rfc7405

    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form

    This class isn't as strict as an actual grammar parser should be:

        * \r\n and \n are both considered valid line endings
        * / and | are both considered valid alternation deliminators
        * <...> is converted to a rulename instead of prose-val
    """
    definition_class = ABNFDefinition

    @functools.cached_property
    def parser_rules(self):
        """Parse all the grammar rules and return them as a dict

        ABNFParser uses this
        """
        rules = {}
        for rule in self:
        #for rule in itertools.chain(self, self.core_rules()):
            rulename = rule.values[0].values[0]
            if rulename in rules:
                rules[rulename].merge(rule)

            else:
                rules[rulename] = rule

        # all grammars have certain core rules always defined so we should add
        # the core rules to the user defined rules
        for rule in self.core_rules():
            rulename = rule.defname
            # if they've defined a core rule then we don't want to over-write
            if rulename not in rules:
                rules[rulename] = rule

        return rules

    def __init__(self, buffer, definition_class=None):
        if definition_class:
            self.definition_class = definition_class

        super().__init__(buffer)

    @contextmanager
    def optional(self):
        """Context manager that will reset the cursor if it fails"""
        try:
            with self.transaction() as scanner:
                yield scanner

        except (IndexError, GrammarError) as e:
            pass

    def log_method(self, method):
        if not logger.isEnabledFor(logging.DEBUG):
            return method

        def logpeek():
            ch = self.peek()
            if ch == "\r":
                ch = "\\r"

            elif ch == "\n":
                ch = "\\n"

            return ch

        def wrapper(*args, **kwargs):
            name = method.__name__
            ch = logpeek()
            start = self.tell()

            logger.debug(
                f"[{start}] {name} starting at character: {ch}"
            )

            ret = method(*args, **kwargs)

            stop = self.tell()
            ch = logpeek()
            logger.debug(
                f"[{stop}] {name} stopping at character: {ch}"
            )

            return ret

        return wrapper

    def __getattribute__(self, key):
        if key.startswith("scan_"):
            return self.log_method(super().__getattribute__(key))

        else:
            return super().__getattribute__(key)

    def __iter__(self):
        """If you just iterate the grammar instance it will just iterate the
        user-defined rules, not the core rules

        To get all the rules, including the core rules, use the .parser_rules
        property
        """
        self.seek(0)

        r = self.scan_rulelist()
        for value in r.values:
            if isinstance(value, self.definition_class):
                if value.name == "rule":
                    yield value

    def create_definition(self, *args, **kwargs):
        return self.definition_class(
            *args,
            grammar=self,
            **kwargs
        )

    def core_rules(self):
        """Return the core rules defined in rfc5234 appendix B.1

        We get very meta here in that we get the rules by parsing them

        https://www.rfc-editor.org/rfc/rfc5234#appendix-B.1

        :returns: dict, the key is the rule name and the value is the rule
            instance
        """
        buffer = "\n".join([
            "ALPHA = %x41-5A / %x61-7A   ; A-Z / a-z",
            "BIT =  \"0\" / \"1\"",
            "CHAR =  %x01-7F"
            "   ; any 7-bit US-ASCII character,",
            "   ;  excluding NUL",
            "CR = %x0D",
            "   ; carriage return",
            "CRLF = CR LF",
            "   ; Internet standard newline",
            "CTL = %x00-1F / %x7F",
            "   ; controls",
            "DIGIT = %x30-39",
            "   ; 0-9",
            "DQUOTE = %x22",
            "; \" (Double Quote)",
            "HEXDIG = DIGIT / \"A\" / \"B\" / \"C\" / \"D\" / \"E\" / \"F\"",
            "HTAB = %x09",
            "; horizontal tab",
            "LF = %x0A",
            "   ; linefeed",
            "LWSP = *(WSP / CRLF WSP)",
            "   ; Use of this linear-white-space rule",
            "   ;  permits lines containing only white",
            "   ;  space that are no longer legal in",
            "   ;  mail headers and have caused",
            "   ;  interoperability problems in other",
            "   ;  contexts.",
            "   ; Do not use when defining mail",
            "   ;  headers and use with caution in",
            "   ;  other contexts.",
            "OCTET = %x00-FF",
            "   ; 8 bits of data",
            "SP = %x20",
            "VCHAR = %x21-7E",
            "   ; visible (printing) characters",
            "WSP = SP / HTAB",
            "   ; white space",
            "", # we need to end with a newline
        ])

        g = type(self)(buffer)
        for rule in g:
            yield rule

    def read_rule(self):
        """This is a throwback to when I was first building the ABNF grammar
        parser, it returns each defined rule in the grammar. This is more for
        informational purposes and this class doesn't use this internally
        """
        lines = []
        scanner = self
        start = scanner.tell()
        line = scanner.readline()
        if line and not line[0].isspace():
            lines.append(line.strip())
            offset = scanner.tell()

            line = scanner.readline()
            while line and line[0].isspace():
                lines.append(line.strip())
                offset = scanner.tell()
                line = scanner.readline()

            scanner.seek(offset)

        stop = scanner.tell() - 1
        return "\n".join(lines)

    def scan_rulelist(self):
        """
        rulelist       =  1*( rule / (*c-wsp c-nl) )
        """
        start = self.tell()
        values = []
        eoftell = len(self)

        while self.tell() < eoftell:
            try:
                values.append(self.scan_rule())

            except GrammarError:
                with self.optional() as scanner:
                    values.append(scanner.scan_c_wsp())

                values.append(self.scan_c_nl())

        return self.create_definition(
            "rulelist",
            values,
            start,
            self.tell()
        )

    def scan_rule(self):
        """
        rule           =  rulename defined-as elements c-nl
                                ; continues if next line starts
                                ;  with white space
        """
        rulename = self.scan_rulename()
        logger.info(f"Parsing rule: {rulename.values[0]}")

        defined_as = self.scan_defined_as()
        elements = self.scan_elements()
        cnl = self.scan_c_nl()

        return self.create_definition(
            "rule",
            [rulename, defined_as, elements, cnl],
            rulename.start,
            cnl.stop
        )

    def scan_rulename(self):
        """
        rulename       =  ALPHA *(ALPHA / DIGIT / "-")

        rule names are case-insensitive
        """
        start = self.tell()
        ch = self.peek()
        if ch and ch in String.ALPHA:
            rulename = self.read_thru_chars(String.ALPHANUMERIC + "-")

        else:
            raise GrammarError(f"[{ch}] was not an ALPHA character")

        stop = self.tell()
        return self.create_definition(
            "rulename",
            [rulename],
            start,
            stop
        )

    def scan_prose_val(self):
        """
        prose-val      =  "<" *(%x20-3D / %x3F-7E) ">"
                                ; bracketed string of SP and VCHAR
                                ;  without angles
                                ; prose description, to be used as
                                ;  last resort

        as far as I can tell prose-val is equivalent to rulename so this returns
        a rulename definition so other functionality can pick it up, it looks
        like if you wanted to have spaces in your rulenames you would use these
        """
        start = self.tell()

        if self.read(1) != "<":
            raise GrammarError("prose-val begins with <")

        val = self.read_until_delim(">").strip(">")
        return self.create_definition(
            "rulename",
            [val],
            start,
            self.tell()
        )



    def scan_defined_as(self):
        """
        defined-as     =  *c-wsp ("=" / "=/") *c-wsp
                                ; basic rules definition and
                                ;  incremental alternatives
        """
        values = []
        start = self.tell()
        options = {}

        with self.optional() as scanner:
            values.append(scanner.scan_c_wsp())

        sign = scanner.read_thru_chars("=/")
        if sign in set(["=", "=/"]):
            values.append(sign)
            options["sign"] = sign

        else:
            val = sign or scanner.peek()
            raise GrammarError(f"{val} is not = or =/")

        with self.optional() as scanner:
            values.append(scanner.scan_c_wsp())

        return self.create_definition(
            "defined-as",
            values,
            start,
            self.tell(),
            **options
        )

    def scan_c_wsp(self):
        """
        c-wsp          =  WSP / (c-nl WSP)
        """
        start = self.tell()
        space = self.read_thru_hspace()
        if space:
            stop = self.tell()
            cwsp = self.create_definition("c-wsp", [space], start, stop)

        else:
            comment = self.scan_c_nl()
            start = self.tell()
            space = self.read_thru_hspace()
            if space:
                stop = self.tell()
                cwsp = self.create_definition(
                    "c-wsp",
                    [comment, space],
                    start,
                    stop
                )

            else:
                raise GrammarError("(c-nl WSP) missing WSP")

        return cwsp

    def scan_c_nl(self):
        """
        c-nl           =  comment / CRLF
                                ; comment or newline
        """
        ch = self.peek()
        if ch == ";":
            comment = self.scan_comment()
            cnl = self.create_definition(
                "c-nl",
                [comment],
                comment.start,
                comment.stop,
            )

        elif ch == "\r" or ch == "\n":
            # we loosen restrictions a bit here by allowing \r\n or just \n
            start = self.tell()
            newline = self.read_until_newline()
            stop = self.tell()
            crlf = self.create_definition("CRLF", newline, start, stop)

            cnl = self.create_definition(
                "c-nl",
                [crlf],
                crlf.start,
                crlf.stop,
            )

        else:
            raise GrammarError("c-nl rule failed")

        return cnl

    def scan_comment(self):
        """
        comment        =  ";" *(WSP / VCHAR) CRLF
        """
        start = self.tell()
        if self.read(1) != ";":
            raise GrammarError("Comment must start with ;")

        comment = self.read_until_newline()
        if not comment.endswith("\n"):
            raise GrammarError("Comment must end with a newline")

        stop = self.tell()
        return self.create_definition(
            "comment",
            [comment.strip()],
            start,
            stop
        )

    def scan_elements(self):
        """
        elements       =  alternation *c-wsp
        """
        start = self.tell()
        values = []

        values.append(self.scan_alternation())

        with self.optional() as scanner:
            values.append(scanner.scan_c_wsp())

        return self.create_definition(
            "elements",
            values,
            start,
            self.tell()
        )

    def scan_alternation(self):
        """
        alternation    =  concatenation
                           *(*c-wsp "/" *c-wsp concatenation)
        """
        start = self.tell()
        values = []

        values.append(self.scan_concatenation())

        while True:
            with self.optional() as scanner:
                values.append(scanner.scan_c_wsp())

            ch = self.peek()
            if ch == "/" or ch == "|":
                values.append(self.read(1))

                with self.optional() as scanner:
                    values.append(scanner.scan_c_wsp())

                values.append(self.scan_concatenation())

            else:
                break

        return self.create_definition(
            "alternation",
            values,
            start,
            self.tell()
        )

    def scan_concatenation(self):
        """
        concatenation  =  repetition *(1*c-wsp repetition)
        """
        start = self.tell()
        values = []

        values.append(self.scan_repetition())

        while True:
            try:
                with self.transaction() as scanner:
                    values.append(scanner.scan_c_wsp())
                    values.append(scanner.scan_repetition())

            except (IndexError, ValueError):
                break

        return self.create_definition(
            "concatenation",
            values,
            start,
            self.tell()
        )

    def scan_repetition(self):
        """
        repetition     =  [repeat] element
        """
        repeat = self.scan_repeat()
        element = self.scan_element()
        return self.create_definition(
            "repetition",
            [repeat, element],
            repeat.start,
            element.stop
        )

    def scan_repeat(self):
        """
        repeat         =  1*DIGIT / (*DIGIT "*" *DIGIT)

        This one is is a little different because Definition.values will always
        be length 2 representing min_repeat, max_repeat and max_repeat being
        zero/negative means unlimited:

            [1, 0] # 1*
            [1, 1] # 1
            [1, 5] # 1*5
            [0, 5] # *5
            [0, 0] # *
        """
        start = self.tell()
        mrep = self.read_thru_chars(String.DIGITS)
        if mrep:
            min_repeat = int(mrep)

        else:
            min_repeat = 1

        ch = self.peek()
        if ch == "*":
            self.read(1)
            max_repeat = 0
            if not mrep:
                min_repeat = 0

            ch = self.peek()
            if ch and ch in String.DIGITS:
                max_repeat = int(self.read_thru_chars(String.DIGITS))

        else:
            max_repeat = min_repeat

        return self.create_definition(
            "repeat",
            [min_repeat, max_repeat],
            start,
            self.tell()
        )

    def scan_element(self):
        """
        element        =  rulename / group / option /
                           char-val / num-val / prose-val
        """
        start = self.tell()
        values = []

        ch = self.peek()

        if ch in String.ALPHA:
            values.append(self.scan_rulename())

        elif ch == "\"":
            qs = self.scan_quoted_string(case_sensitive=False)
            # we wrap it in a char-val to be rfc7405 consistent
            values.append(
                self.create_definition(
                    "char-val",
                    [qs],
                    qs.start,
                    qs.stop
                )
            )

        elif ch == "(":
            values.append(self.scan_group())

        elif ch == "[":
            values.append(self.scan_option())

        elif ch == "%":
            values.append(self.scan_val())

        elif ch == "<":
            values.append(self.scan_prose_val())

        else:
            raise GrammarError(f"Unknown element starting with [{ch}]")

        return self.create_definition(
            "element",
            values,
            start,
            self.tell()
        )

    def scan_quoted_string(self, case_sensitive=False):
        """
        https://datatracker.ietf.org/doc/html/rfc7405

        quoted-string  =  DQUOTE *(%x20-21 / %x23-7E) DQUOTE
                                ; quoted string of SP and VCHAR
                                ;  without DQUOTE

        When parsing the grammar any quoted-string rules are wrapped with
        char-val so they stay consistent with ABNF updates from RFT7405
        """
        if self.peek() != "\"":
            raise GrammarError("Char value begins with double-quote")

        start = self.tell()
        charval = self.read_until_delim("\"", count=2)
        charval = charval.strip("\"")
        return self.create_definition(
            "quoted-string",
            [charval],
            start,
            self.tell(),
            case_sensitive=case_sensitive
        )

    def scan_val(self):
        """
        terminal value

        https://datatracker.ietf.org/doc/html/rfc7405

        num-val        =  "%" (bin-val / dec-val / hex-val)

        bin-val        =  "b" 1*BIT
                           [ 1*("." 1*BIT) / ("-" 1*BIT) ]
                                ; series of concatenated bit values
                                ;  or single ONEOF range

        dec-val        =  "d" 1*DIGIT
                           [ 1*("." 1*DIGIT) / ("-" 1*DIGIT) ]

        hex-val        =  "x" 1*HEXDIG
                           [ 1*("." 1*HEXDIG) / ("-" 1*HEXDIG) ]

        char-val       =  case-insensitive-string /
                           case-sensitive-string

        case-insensitive-string =
                           [ "%i" ] quoted-string

        case-sensitive-string =
                           "%s" quoted-string
        """
        start = self.tell()
        values = []

        ch = self.read(1)
        if ch != "%":
            raise GrammarError("num-val starts with %")

        values.append(ch)

        ch = self.read(1)
        values.append(ch)

        if ch in "bdx":
            if ch == "b":
                numchars = "01"
                name = "bin-val"

            elif ch == "d":
                numchars = String.DIGITS
                name = "dec-val"

            elif ch == "x":
                numchars = String.HEXDIGITS
                name = "hex-val"

            v = self.read_thru_chars(numchars)
            if not v:
                raise GrammarError("num-val with no number values")

            values.append(v)

            ch = self.peek()
            if ch == "-":
                values.append(self.read(1))

                v = self.read_thru_chars(numchars)
                if not v:
                    raise GrammarError(
                        f"num-val {ch} with no number values after"
                    )

                values.append(v)

            elif ch == ".":
                while ch == ".":
                    values.append(self.read(1))
                    v = self.read_thru_chars(numchars)
                    if not v:
                        raise GrammarError(
                            f"num-val {ch} with no number values after"
                        )

                    values.append(v)
                    ch = self.peek()

        elif ch in "si":
            values.append(self.scan_quoted_string(case_sensitive=(ch == "s")))
            name = "char-val"

        else:
            raise GrammarError(f"Terminal value {ch} failed")

        return self.create_definition(
            name,
            values,
            start,
            self.tell()
        )

    def scan_group(self, start_char="(", stop_char=")"):
        """
        group          =  "(" *c-wsp alternation *c-wsp ")"
        """
        start = self.tell()
        values = []

        ch = self.read_thru_chars(start_char)
        if ch != start_char:
            raise GrammarError(f"Group must start with {start_char}")

        values.append(ch)

        with self.optional() as scanner:
            values.append(scanner.scan_c_wsp())

        values.append(self.scan_alternation())

        with self.optional() as scanner:
            values.append(scanner.scan_c_wsp())

        ch = self.read_thru_chars(stop_char)
        if ch != stop_char:
            raise GrammarError(f"Group must end with {stop_char}")

        values.append(ch)

        return self.create_definition(
            "group",
            values,
            start,
            self.tell()
        )

    def scan_option(self):
        """
        option         =  "[" *c-wsp alternation *c-wsp "]"
        """
        start = self.tell()
        group = self.scan_group("[", "]")
        return self.create_definition(
            "option",
            group.values,
            group.start,
            group.stop
        )


class ABNFRecursiveDescentParser(logging.LogMixin):
    """Actually parse a buffer using a parsed grammar

    This is an internal class used by ABNFParser and this does the actual
    parsing while ABNFParser is just the UI

    This is not an LL parser because it keeps a lot of state in order to handle
    left recursion in the grammar. I've compared its output to:

        http://instaparse.mojombo.com/

    And it seems to parse my test left-recursive grammars the same.

    To use instaparse for ABNF, in the lower right, click on Options and change
    `:input-format` to ':abnf'. Then paste an ABNF grammar into the entry box
    above the options. Then you can paste something to parse into the box on the
    left.

    https://en.wikipedia.org/wiki/Recursive_descent_parser
    https://en.wikipedia.org/wiki/Left_recursion
    """
    scanner_class = Scanner
    """The buffer (input to be parsed) will be wrapped in an instance of this
    class in order to be parsed"""

    token_class = ABNFToken
    """The token that is returned from .create_token"""

    def __init__(self, parser, entry_rule):
        """The parser creates an instance of this class when used.

        :param parser: ABNFParser, the ABNFParser instance that created this 
            object instance
        :param entry_rule: ABNFDefinition, the starting rule that will be the
            entrypoint to parsing buffer when .parse(buffer) is called
        """
        self.parser = parser
        self.entry_rule = entry_rule

    def parse(self, buffer, partial=False):
        """Parse buffer and return the parsed token

        :param buffer: str, teh input to be parsed using self.parser.grammar
        :param partial: bool, True if you don't expect to completely parse
            buffer, if False (default) then buffer must be fully consumed or a
            ParseError is raised
        :returns: self.token_class, the return value will roughly correspond to
            self.entry_rule and will contain the parsed values from buffer
        """
        self.set_buffer(buffer)
        values = self.parse_rule(self.entry_rule)
        token = values[0]

        if not partial:
            eoftell = len(self.scanner)
            if token.stop < eoftell:
                raise ParseError(
                    "Only parsed {}/{} characters of buffer using {}: {}".format(
                        token.stop,
                        eoftell,
                        self.entry_rule.defname,
                        buffer[0:token.stop],
                    )
                )

        return values[0]

    def __call__(self, buffer):
        return self.parse(buffer)

    def set_buffer(self, buffer):
        """Get the buffer ready to be parsed

        :param buffer: str, the buffer that will be initialized for parsing
        """
        self.scanner = self.scanner_class(buffer)

        # these store state for handling left recursion
        self.parsing_rules_stack = []
        self.parsing_rules_lookup = defaultdict(list)
        self.parsing_rules_info = defaultdict(dict)

    def create_token(self, rule, values, start, stop, **options):
        return self.token_class(
            rule.defname,
            values,
            start,
            stop,
            parser=self,
            **options
        )

    def get_log_message(self, format_str, *format_args, **kwargs):
        parsing_rule = kwargs.get("parsing_rule", None)
        if not parsing_rule:
            if self.parsing_rules_stack:
                parsing_rule = self.parsing_rules_stack[-1]

        msg = super().get_log_message(format_str, *format_args, **kwargs)
        if parsing_rule:
            rulename = parsing_rule["rule"].defname
            count = parsing_rule["count"]
            msg = f"{rulename}({count}) -> {msg}"

        return f"[{self.scanner.tell()}] {msg}"

    @contextmanager
    def transaction(self):
        """Internal method that will revert the cursor to the previous position
        if the input fails to be parsed by the current rule
        """
        with self.scanner.transaction() as scanner:
            yield scanner

    def push(self, rule):
        """Internal method that pushes rule onto the internal stack

        This messes with state used to track left-recursion

        :param rule: ABNFDefinition, the rule about to be parsed
        """
        rulename = rule.defname

        if self.parsing_rules_lookup.get(rulename, None):
            total = len(self.parsing_rules_lookup[rulename]) + 1
            self.log_debug("Pushing {}({})", rulename, total)

            index = self.parsing_rules_lookup[rulename][-1]
            parsing_rule = self.parsing_rules_stack[index]

            if parsing_rule["start"] >= self.scanner.tell():
                self.parsing_rules_info[rulename]["left-recursion"] = True

                raise ParseError(
                    f"Parsing {rulename}({total}) infinite left recursion"
                )

        else:
            self.log_debug("Pushing {}(1)", rulename)

        self.parsing_rules_info[rulename]["left-recursion"] = False
        self.parsing_rules_info[rulename].setdefault("indexes", {})

        index = len(self.parsing_rules_stack)
        parsing_rule = {
            "rule": rule,
            "start": self.scanner.tell(),
        }

        self.parsing_rules_stack.append(parsing_rule)
        self.parsing_rules_lookup[rulename].append(index)

        parsing_rule["count"] = len(self.parsing_rules_lookup[rulename])

        return parsing_rule

    def pop(self, rule):
        """Internal method that pops rule from the internal stack

        This messes with state used to track left-recursion

        :param rule: ABNFDefinition, the rule done being parsed
        """
        rulename = rule.defname

        total = len(self.parsing_rules_lookup[rulename])
        self.log_debug("Popping {}({})", rulename, total)

        index = self.parsing_rules_lookup[rulename].pop(-1)
        parsing_rule = self.parsing_rules_stack.pop(-1)
        if parsing_rule["rule"].defname != rule.defname:
            raise ParseError(
                "Parsing stack is messed up, popped: {} instead of: {}".format(
                    parsing_rule["rule"].defname,
                    rule.defname,
                )
            )

        return parsing_rule

    def parse_rule(self, rule):
        """Most everything important goes through this parse method

        This method is responsible for calling .push() and .pop() and messes
        with state used to track left-recursion

        :param rule: ABNFDefinition, the rule to be parsed
        :returns: list, this list should only have one value in it, the rule
            that was just parsed
        """
        start = istart = stop = self.scanner.tell()
        rulename = rule.defname

        # before trying to parse the rule fresh we check the cache and return
        # the cache if this rule has already been parsed at this index
        parsing_indexes = self.parsing_rules_info[rulename].get("indexes", {})
        if start in parsing_indexes:
            token = parsing_indexes[start]

            self.log_debug(
                "Returning saved {} \"{}\" for [{}]",
                rulename,
                token,
                start
            )

            self.scanner.seek(token.stop)

        else:
            eoftell = len(self.scanner)

            self.push(rule)
            success = 0

            # you might be tempted to change this to "stop < eoftell" but that 
            # would be a mistake. You need to go through the rule one more time
            # after hitting the eof to successfully pick up any optional rules that
            # don't need to actually parse anything but do need to successfully
            # parse by returning an empty list
            while True:
                self.scanner.seek(start)

                try:
                    values = self.parse_elements(rule.values[2])

                except ParseError as e:
                    break

                else:
                    success += 1
                    istop = self.scanner.tell()

                    token = self.create_token(
                        rule,
                        values,
                        start,
                        istop
                    )

                    self.log_debug(
                        "Success({}) parsing {}: \"{}\"",
                        success,
                        rulename,
                        token
                    )

                    # we check the saved token here, if it is more "complete" than
                    # the token we just parsed let's switch to the saved token and
                    # go ahead and bail since it seems like we're done with parsing
                    # this token
                    save = True
                    parsing_info = self.parsing_rules_info[rulename]
                    if saved_token := parsing_info["indexes"].get(start, None):
                        if token.stop > saved_token.stop:
                            save = True

                        else:
                            token = saved_token
                            self.scanner.seek(token.stop)

                    if save:
                        self.log_debug(
                            "Saving {} \"{}\" for [{}]",
                            rulename,
                            token,
                            start
                        )
                        parsing_info["indexes"][start] = token

                        if istop > stop:
                            stop = istop

                            if parsing_info.get("left-recursion", False):
                                if stop < eoftell:
                                    continue

                    break

            self.pop(rule)

            if not success:
                raise ParseError(f"Rule {rulename} failed")

        return [token]

    def parse_rulename(self, rule):
        r = self.parser.grammar.parser_rules[rule.defname]
        return self.parse_rule(r)

    def parse_elements(self, rule):
        return self.parse_alternation(next(rule.tokens("alternation")))

    def parse_alternation(self, rule):
        """go through all the alternations and return the greediest one

        This has to run all the alternations but it keeps track of the longest
        alternation to parse and will ultimately return that one after running
        through all the options. It will raise a ParseError if no alternations
        succeed in parsing
        """
        success = 0
        values = []
        start = stop = self.scanner.tell()
        for index, r in enumerate(rule.tokens("concatenation"), 1):
            self.scanner.seek(start)

            try:
                self.log_debug("Alternation({}): {}", index, r)
                ivalues = self.parse_concatenation(r)
                istop = self.scanner.tell()
                success += 1

                if istop > stop:
                    stop = istop
                    values = ivalues

            except ParseError as e:
                self.log_debug(
                    "Parsing alternation({}) failed with: {}",
                    index,
                    e
                )

        if success:
            self.scanner.seek(stop)
            return values

        else:
            raise ParseError(f"Failure alternation: {rule}")

    def parse_concatenation(self, rule):
        values = []
        with self.transaction():
            for r in rule.tokens("repetition"):
                values.extend(self.parse_repetition(r))

        return values

    def parse_repetition(self, rule):
        values = []
        repeat, element = rule.values
        rmin = repeat.min
        rmax = repeat.max
        maxcount = rmax or "*"
        count = 0

        self.log_debug(
            "Repetition {} {}-{} times",
            element.values[0].name,
            rmin,
            maxcount
        )

        # we have to get at least repeat.min values
        for count in range(1, rmin + 1):
            if vs := self.parse_element(element):
                values.extend(vs)

        # now we need to either exhaust as many as we can or grab up to
        # repeat.max
        if rmax == 0 or (rmax > rmin):
            while True:
                count += 1
                try:
                    if vs := self.parse_element(element):
                        values.extend(vs)

                    else:
                        # we didn't find any values that time so we're done
                        break

                except ParseError:
                    break

                else:
                    if rmax and count >= rmax:
                        break

        return values

    def parse_element(self, rule):
        values = []
        r = rule.values[0]

        if r.is_num_val():
            method_name = f"parse_num_val"

        else:
            rule_method_name = r.name.replace("-", "_")
            method_name = f"parse_{rule_method_name}"

        method = getattr(self, method_name, None)
        if method:
            values = method(r)

        else:
            raise RuntimeError(f"No {method_name}")

        return values

    def parse_group(self, rule):
        return self.parse_alternation(next(rule.tokens("alternation")))

    def parse_option(self, rule):
        try:
            return self.parse_group(rule)

        except ParseError:
            return []

#     def xparse_num_val(self, rule):
#         """Terminal parsing rule, this actually moves the cursor and consumes
#         the buffer
#         """
#         values = []
#         start = self.scanner.tell()
#         with self.transaction() as scanner:
#             if rule.is_val_range():
#                 v = scanner.read(1)
#                 if v:
#                     codepoint = ord(v)
#                     if rule.min > codepoint or codepoint > rule.max:
#                         raise ParseError(
#                             "Failure {}, {} not in range: {} <= {} <= {}".format(
#                                 rule.name,
#                                 v,
#                                 rule.min,
#                                 codepoint,
#                                 rule.max
#                             )
#                         )
# 
#                     self.log_debug("Parsed {} value: {}", rule.name, v)
# 
#                     if v in String.DIGITS:
#                         v = int(v)
#                     values = [v]
# 
#                 else:
#                     raise ParseError(f"Failure {rule.name}")
# 
#             elif rule.is_val_chars():
#                 chars = rule.chars
#                 total_chars = len(chars)
#                 for i, ch in enumerate(chars, 1):
#                     v = scanner.read(1)
#                     if v:
#                         codepoint = ord(v)
#                         if codepoint != ch:
#                             raise ParseError(
#                                 "Failure {} character {}/{}, {} value {} != {}".format(
#                                     rule.name,
#                                     i,
#                                     total_chars,
#                                     v,
#                                     codepoint,
#                                     ch
#                                 )
#                             )
# 
#                         self.log_debug(
#                             "Parsed {} character {}/{} value: {}",
#                             rule.name,
#                             i,
#                             total_chars,
#                             v
#                         )
# 
#                         if v in String.DIGITS:
#                             v = int(v)
#                         values.append(v)
# 
#                     else:
#                         raise ParseError(f"Failure {rule.name}")
# 
#             else:
#                 raise RuntimeError(f"Unsure how to handle {rule.name}")
# 
#         return values

    def parse_num_val(self, rule):
        """Terminal parsing rule, this actually moves the cursor and consumes
        the buffer
        """
        values = []
        start = self.scanner.tell()
        with self.transaction() as scanner:
            for chmin, chmax in rule.ranges():
                v = scanner.read(1)
                if v:
                    codepoint = ord(v)
                    if chmin > codepoint or codepoint > chmax:
                        raise ParseError(
                            "Failure {}, {} not in range: {} <= {} <= {}".format(
                                rule.name,
                                v,
                                chmin,
                                codepoint,
                                chmax
                            )
                        )

                    self.log_debug("Parsed {} value: {}", rule.name, v)

                    if v in String.DIGITS:
                        v = int(v)
                    values = [v]

                else:
                    raise ParseError(f"Failure {rule.name}")

        if not values:
            raise RuntimeError(f"Unsure how to handle {rule.name}")

        return values

    def parse_char_val(self, rule):
        """Terminal parsing rule, this actually moves the cursor and consumes
        the buffer
        """
        values = []
        start = self.scanner.tell()
        qsrule = rule.values[0]
        with self.transaction() as scanner:
            sub = qsrule.values[0]
            v = self.scanner.read(len(sub))

            success = (qsrule.options["case_sensitive"] and v == sub) \
                or (v.lower() == sub.lower())

            if success:
                self.log_debug("Parsed {} value: {}", rule.name, v)
                values = [v]

            else:
                raise ParseError(
                    "Failure {}, expected: {}, got: {}".format(
                        rule.name,
                        sub,
                        v
                    )
                )

        return values


class ABNFParser(object):
    """Parses the passed in ABNF grammar and provides a fluid interface to
    parse any input

    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form

    A parser takes the stream of tokens from the lexer and gives it some sort
    of structure that was represented by the original text

    :Example:
        grammar = "\n".join([
            "exp = exp \"+\" term / exp \"-\" term / term",
            "term = term \"*\" power / term \"/\" power / power",
            "power = factor \"^\" power / factor",
            "factor = \"(\" exp \")\" / 1*DIGIT",
        ])
        p = ABNFParser(grammar)
        r = p.exp.parse("(1-2)+3*4")
        print(str(r.values[0]) # (1-2)
    """
    grammar_class = ABNFGrammar
    """The class that will parse the grammar input"""

    parser_class = ABNFRecursiveDescentParser
    """The class that will do the actual parsing. An instance of this class is
    returned when using the fluid rule interface"""

    def __init__(self, grammar, **kwargs):
        """Create an ABNF grammar parser

        :param grammar: str|list|ABNFGrammar, the grammar rules that will be
            used to parse a buffer
        """
        self.grammar = self.create_grammar(grammar, **kwargs)

    def create_grammar(self, grammar, **kwargs):
        grammar_class = kwargs.get(
            "grammar_class",
            self.grammar_class
        )

        if isinstance(grammar, grammar_class):
            return grammar

        elif not isinstance(grammar, str):
            grammar = "\n".join(grammar)

        return grammar_class(
            grammar,
            definition_class=kwargs.get("definition_class", None)
        )

    def create_parser(self, rule):
        return self.parser_class(self, rule)

    def __getitem__(self, rulename):
        rulename = ABNFDefinition.normalize_name(rulename)
        rule = self.grammar.parser_rules[rulename]
        return self.create_parser(rule)

    def __getattr__(self, rulename):
        try:
            return self[rulename]

        except KeyError as e:
            raise AttributeError(rulename) from e

