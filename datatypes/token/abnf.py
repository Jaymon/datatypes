# -*- coding: utf-8 -*-
from contextlib import contextmanager
from collections import defaultdict
import itertools
import functools

from ..compat import *
from ..logging import *
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


class ABNFDefinition(object):
    @functools.cached_property
    def definitions(self):
        definitions = []
        for value in self.values:
            if isinstance(value, ABNFDefinition):
                definitions.append(value)

        return definitions

    @functools.cached_property
    def parsable(self):
        definitions = []
        for value in self.definitions:
            if value.is_parsable():
                definitions.append(value)

        return definitions

    @property
    def defname(self):
        """Return the grammar's rulename (ie, the rulename defined in the 
        grammar"""
        if self.name == "rule":
            rulename = self.values[0].values[0]

        elif self.name == "rulename":
            rulename = self.values[0]

        else:
            raise AttributeError(f"No defname property on {self.name}")

        return rulename

    @property
    def min(self):
        if self.is_val_chars():
            raise AttributeError(f"No min property on {self.name} with chars")

        if self.is_bin_val():
            ret = int(Binary(self.values[2]))

        elif self.is_dec_val():
            ret = int(self.values[2])

        elif self.is_hex_val():
            ret = int(Hex(self.values[2]))

        elif self.is_repeat():
            ret = int(self.values[0])

        else:
            raise AttributeError(f"No min property on {self.name}")

        return ret

    @property
    def max(self):
        if self.is_val_chars():
            raise AttributeError(f"No max property on {self.name} with chars")

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
            raise AttributeError(f"No max property on {self.name}")

        return ret

    @property
    def chars(self):
        if self.is_val_range():
            raise AttributeError(f"No chars property on {self.name} with range")

        chars = set()
        for ch in self.values[2::2]:
            if self.is_bin_val():
                chars.add(int(Binary(ch)))

            elif self.is_dec_val():
                chars.add(int(ch))

            elif self.is_hex_val():
                chars.add(int(Hex(ch)))

        return chars

    @classmethod
    def normalize_name(cls, name):
        # ABNF keys can't contain underscores but python attribute names can't
        # contain dashes and rule names are case-insensitive
        return name.replace("_", "-").lower()
        #return name.replace("-", "").replace("_", "").lower()

    def __init__(self, name, values, start, stop, **options):
        self.name = self.normalize_name(name)
        self.values = values
        self.start = start
        self.stop = stop
        self.options = options

    def __getattr__(self, key):
        if key.startswith("is_"):
            _, name = key.split("_", maxsplit=1)
            #classname = self.__class__.__name__.lower()
            name = self.normalize_name(name)
            return lambda *_, **__: self.name == name

        else:
            values = []
            name = self.normalize_name(key)
            for value in self.values:
                if isinstance(value, ABNFDefinition):
                    if value.name == name:
                        values.append(value)

                    else:
                        try:
                            values.extend(getattr(value, key))

                        except AttributeError:
                            pass

            if values:
                return values

        raise AttributeError(key)

    def __str__(self):
        parts = []

        parts.append(f"{self.name} [{self.start}:{self.stop}]:")

        for value in self.values:
            if isinstance(value, ABNFDefinition):
                if value.is_rulename():
                    parts.append(f"{value.name}({value.values[0]})")

                elif value.is_definedas():
                    sign = value.options["sign"]
                    parts.append(f"{value.name}({sign})")

                else:
                    parts.append(value.name)

            else:
                parts.append(str(value))

        return " ".join(parts)

    def is_parsable(self):
        return not self.is_internal()

    def is_internal(self):
        return self.is_c_wsp() \
            or self.is_c_nl() \
            or self.is_defined_as() \
            or self.is_comment()

    def is_num_val(self):
        return self.is_bin_val() \
            or self.is_dec_val() \
            or self.is_hex_val()

    def is_val_range(self):
        if self.is_num_val():
            return len(self.values) == 5 and self.values[3] == "-"

        return False

    def is_val_chars(self):
        if self.is_num_val():
            return len(self.values) >= 5 and self.values[3] == "."

        return False

    def merge(self, definition):
        if self.is_rule() and definition.is_rule():
            # we need to make sure the defined-as definition is =/
            definedas = definition.values[1]
            for v in definedas.values:
                if isinstance(v, str):
                    if v == "=/":
                        self.values.append(definition)
                        break

                    else:
                        raise ValueError(" ".join([
                            f"When merging {self.rulename} the second",
                            f"{self.rulename} must have an =/",
                        ]))

        else:
            raise ValueError(f"Cannot have 2 {self.rulename} defined")


class ABNFGrammar(Scanner):
    """This lexes an ABNF grammar

    It's a pretty standard lexer that follows rfc5234:

        https://www.rfc-editor.org/rfc/rfc5234

    and the update for char-val in rfc7405:

        https://datatracker.ietf.org/doc/html/rfc7405

    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form
    """
    definition_class = ABNFDefinition

    @functools.cached_property
    def parser_rules(self):
        rules = {}
        #rules = defaultdict(list)
        for rule in itertools.chain(self, self.core_rules()):
            rulename = rule.values[0].values[0]
            if rulename in rules:
                rules[rulename].merge(rule)

            else:
                rules[rulename] = rule

        return rules

    def __init__(self, buffer, definition_class=None):
        if definition_class:
            self.definition_class = definition_class

        super().__init__(buffer)

    @contextmanager
    def optional(self):
        try:
            with self.transaction() as scanner:
                yield scanner

        except (IndexError, ValueError) as e:
            pass

    def logmethod(self, method):

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
                f"{name} starting at character {start}: [{ch}]"
            )

            ret = method(*args, **kwargs)

            stop = self.tell()
            ch = logpeek()
            logger.debug(
                f"{name} stopping at character {stop}: [{ch}]"
            )

            return ret

        return wrapper

    def __getattribute__(self, key):
        if key.startswith("scan_"):
            return self.logmethod(super().__getattribute__(key))

        else:
            return super().__getattribute__(key)

    def __iter__(self):
        """If you just iterate the grammar instance it will just iterate the
        rules"""
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
        maxtell = len(self)

        while self.tell() < maxtell:
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
        zero/negative means unlimited
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


class ABNFRecursiveDescentParser(object):
    """

    https://en.wikipedia.org/wiki/Recursive_descent_parser
    https://en.wikipedia.org/wiki/Left_recursion
    """

    scanner_class = Scanner

    token_class = ABNFDefinition

    def __init__(self, parser, entry_rule):
        self.parser = parser
        self.entry_rule = entry_rule

        # these store state
        self.parsing_rules = []
        self.parsing_rules_lookup = {}

    def create_token(self, values, start, stop, **options):

        ruleinfo = self.parsing_rules[-1]
        rule = ruleinfo["rule"]

        return self.token_class(
            rule.defname,
            values,
            start,
            stop,
            parser=self.parser,
            **options
        )

    def push(self, rule):
        rulename = rule.defname

        if lookup := self.parsing_rules_lookup.get(rulename):
            index = lookup[-1]
            parsing_rule = self.parsing_rules[index]
            if parsing_rule["tell"] >= self.scanner.tell():
                parsing_rule["count"] += 1
                raise ParseError(f"Parsing {rulename} infinite left recursion")

        index = len(self.parsing_rules)
        parsing_rule = {
            "rule": rule,
            "tell": self.scanner.tell(),
            "count": 1,
        }
        self.parsing_rules.append(parsing_rule)
        self.parsing_rules_lookup[rulename].append(index)

        return parsing_rule

    def pop(self, rule):
        rulename = rule.defname

        if rulename in self.parsing_rules_lookup:
            index = self.parsing_rules_lookup[rulename].pop(-1)

            #return self.parsing_rules.pop(index)
            parsing_rule = self.parsing_rules[index]

            # we set this to None because the rule status/info we pop might not
            # be at the end of the stack and we need to maintain order, so we
            # also cleanup any ends of the stack that are None since they won't
            # be used again
            self.parsing_rules[index] = None
            while self.parsing_rules and self.parsing_rules[-1] is None:
                self.parsing_rules.pop(-1)

            return parsing_rule

        else:
            raise ParseError(f"Popping {rulename} failed")

    def __call__(self, buffer):
        return self.parse(buffer)

    def parse(self, buffer):
        self.scanner = self.scanner_class(buffer)

        values = self.descend(self.entry_rule)
        if len(values) > 1:
            rulename = self.entry_rule.defname
            raise ParseError(f"Too many values were parsed for rule {rulename}")

        return values[0]

    def descend(self, rule):

        values = []

        parsing_rule = None
        if self.parsing_rules:
            parsing_rule = self.parsing_rules[-1]["rule"]

        if rule.is_num_val():
            method_name = f"parse_num_val"

        else:
            method_name = f"parse_{rule.name}"

        method = getattr(self, method_name, None)
        if method:
            if parsing_rule:
                logger.debug(
                    "{} -> {} at {}".format(
                        parsing_rule.defname,
                        rule.name,
                        self.scanner.tell()
                    )
                )

            if vs := method(rule):
                if isinstance(vs, list):
                    values = vs

                else:
                    values.append(vs)

        else:
            logger.debug(f"Ignoring non-parsable rule {rule.name}")

        return values

    def parse_rule(self, rule):
        values = []
        start = self.scanner.tell()
        rulename = rule.defname

        count = len(self.parsing_rules_lookup.get(rulename, [])) + 1
        logger.debug(
            f"Parsing {rule.defname}({count}) at {self.scanner.tell()}"
        )

        self.push(rule)

        for r in itertools.chain([rule.values[2]], rule.values[4:]):
            try:
                values = self.descend(r)

            except ParseError:
                pass

            else:
                break

        if values:
            values = [self.create_token(
                values,
                start,
                self.scanner.tell()
            )]

            parsing_rule = self.pop(rule)
            #pout.v(parsing_rule, parsing_rule["rule"].defname, self.scanner.tell())
            if parsing_rule["count"] > 1:
                if parsing_rule["tell"] < self.scanner.tell():
                    # we run the whole thing again since this rule tried to
                    # left-recurse but we've made progress since then
                    values.extend(self.parse_rule(rule))

        else:
            raise ParseError(f"Rule {rulename} was empty")

        return values

    def parse_elements(self, rule):
        values = []
        for r in rule.definitions:
            if vs := self.descend(r):
                values.extend(vs)

        return values

    def parse_alternation(self, rule):
        for r in rule.parsable:
            try:
                return self.descend(r)

            except ParseError as e:
                logger.debug(f"Parsing alternation failed with: {e}")
                pass

        raise ParseError("Failed to successfully parse alternation")

    def parse_concatenation(self, rule):
        values = []
        for r in rule.definitions:
            if vs := self.descend(r):
                values.extend(vs)

        return values

    def parse_repetition(self, rule):
        values = []
        repeat, r = rule.values

        # we have to get at least repeat.min values
        for count in range(1, repeat.min + 1):
            logger.debug(f"Repetition minimum {count}/{repeat.min}")
            if vs := self.descend(r):
                values.extend(vs)
            #values.append(self.descend(r))

        # now we need to either exhaust as many as we can or grab up to
        # repeat.max
        if repeat.max == 0 or (repeat.max > repeat.min):
            maxcount = repeat.max or "*"
            while True:
                logger.debug(f"Repetition maximum {count}/{maxcount}")
                try:
                    if vs := self.descend(r):
                        values.extend(vs)

                    else:
                        # we didn't find any values that time so we're done
                        break

                except ParseError:
                    break

                else:
                    count += 1
                    if repeat.max and count >= repeat.max:
                        break

        return values

    def parse_element(self, rule):
        return self.descend(rule.values[0])

    def parse_rulename(self, rule):
        r = self.parser.grammar.parser_rules[rule.defname]
        return self.descend(r)

    def parse_num_val(self, rule):
        start = self.scanner.tell()
        with self.scanner.transaction() as scanner:
            v = scanner.read(1)
            if v:
                codepoint = ord(v)
                if rule.min > codepoint or codepoint > rule.max:
                    raise ParseError(
                        "Failed {} {} range: {} <= {} <= {}".format(
                            rule.name,
                            v,
                            rule.min,
                            codepoint,
                            rule.max
                        )
                    )

                logger.debug(f"Parsed {rule.name} value: {v}")
                return [int(v)]

            else:
                raise ParseError(f"Failed to parse {rule.name}")

    def parse_char_val(self, rule):
        values = []
        start = self.scanner.tell()
        qsrule = rule.values[0]
        with self.scanner.transaction() as scanner:
            sub = qsrule.values[0]
            v = self.scanner.read(len(sub))

            success = (qsrule.options["case_sensitive"] and v == sub) \
                or (v.lower() == sub.lower())

            if success:
                logger.debug(f"Parsed {rule.name} value: {v}")
                return [v]

            else:
                raise ParseError(
                    f"Failed to parse {rule.name} quoted string: {sub}"
                )


class ABNFParser(object):
    """
    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form

    A parser takes the stream of tokens from the lexer and gives it some sort
    of structure that was represented by the original text
    """
    grammar_class = ABNFGrammar

    parser_class = ABNFRecursiveDescentParser

    def __init__(self, grammar, **kwargs):
        self.grammar = self.create_grammar(grammar, **kwargs)

    def create_grammar(self, grammar, **kwargs):
        grammar_class = kwargs.get(
            "grammar_class",
            self.grammar_class
        )

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

