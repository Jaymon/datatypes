# -*- coding: utf-8 -*-
from contextlib import contextmanager
from collections import defaultdict
import itertools
import functools

from ..compat import *
from ..logging import *
from ..string import String
from ..decorators import property as cachedproperty
from .base import Token, Tokenizer, Scanner


logger = logging.getLogger(__name__)


class ABNFDefinition(object):
    @functools.cached_property
    def definitions(self):
        definitions = []
        for value in self.values:
            if isinstance(value, ABNFDefinition):
                definitions.append(value)

        return definitions

    def __init__(self, grammar, name, values, start, stop, **options):
        self.grammar = grammar
        self.name = self.normalize_name(name)
        self.values = values
        self.start = start
        self.stop = stop
        self.options = options

    def normalize_name(self, name):
        return name.replace("-", "").replace("_", "").lower()

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

#         if self.is_rulename():
#             parts.append(f"{self.name}({self.values[0]})")
# 
#         elif self.is_definedas():
#             sign = self.options["sign"]
#             parts.append(f"{self.name}({sign})")
# 
#         elif self.is_elements():
#             count = len(self.alternation)
#             parts.append(f"{self.name}({count})")
# 
#         else:
        for value in self.values:
            if isinstance(value, ABNFDefinition):
                if value.is_rulename():
                    parts.append(f"{value.name}({value.values[0]})")

                elif value.is_definedas():
                    sign = value.options["sign"]
                    parts.append(f"{value.name}({sign})")

                # this is useless because elements always has one alternation
#                 elif value.is_elements():
#                     count = len(value.alternation)
#                     parts.append(f"{value.name}({count})")

                else:
                    parts.append(value.name)

            else:
                parts.append(str(value))

        return " ".join(parts)

    def is_numval(self):
        return self.is_binval() \
            or self.is_decval() \
            or self.is_hexval()

    def is_terminal(self):
        return self.is_quotedstring() or self.is_numval()

    def parse(self, buffer):
        if self.is_rule():
            for rule in itertools.chain([self.values[2]], self.values[4:]):
                try:
                    return rule.parse(buffer)

                except ValueError:
                    pass


        elif self.is_alternation():
            for rule in self.definitions:
                try:
                    return rule.parse(buffer)

                except ValueError:
                    pass

        elif self.is_repetition():
            # https://stackoverflow.com/questions/312443/how-do-i-split-a-list-into-equally-sized-chunks
            for repeat, elem in itertools.zip_longest(*[iter(self.values)] * 2):
                #pout.v(repeat, elem)
                p = elem.parse(buffer)

        elif self.is_rulename():
            pout.v(self.values[0])
            rule = self.grammar.parser_rules[self.values[0]]
            return rule.parse(buffer)

        elif self.is_quotedstring():
            pout.v(self.values)

        elif self.is_numval():
            pout.v(self.values)

        else:
            for rule in self.definitions:
                p = rule.parse(buffer)

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

#     @cachedproperty(cached="_parser_rules")
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

#         for rule in self.core_rules():
#             rules[rule.values[0].values[0]].append(rule)

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
        return self.definition_class(self, *args, **kwargs)

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

        try:
            while True:
                try:
                    values.append(self.scan_rule())

                except ValueError:
                    with self.optional() as scanner:
                        values.append(scanner.scan_cwsp())

                    values.append(self.scan_cnl())

        except ValueError:
            pass

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

        defined_as = self.scan_definedas()
        elements = self.scan_elements()
        cnl = self.scan_cnl()

        #pout.v(self.getvalue()[rulename.start:cnl.stop])

        return self.create_definition(
            "rule",
            [rulename, defined_as, elements, cnl],
            rulename.start,
            cnl.stop
        )

    def scan_rulename(self):
        """
        rulename       =  ALPHA *(ALPHA / DIGIT / "-")
        """
        start = self.tell()
        ch = self.peek()
        if ch and ch in String.ALPHA:
            rulename = self.read_thru_chars(String.ALPHANUMERIC + "-")

        else:
            raise ValueError(f"[{ch}] was not an ALPHA character")

        stop = self.tell()
        return self.create_definition("rulename", [rulename], start, stop)

    def scan_definedas(self):
        """
        defined-as     =  *c-wsp ("=" / "=/") *c-wsp
                                ; basic rules definition and
                                ;  incremental alternatives
        """
        values = []
        start = self.tell()
        options = {}

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        sign = scanner.read_thru_chars("=/")
        if sign in set(["=", "=/"]):
            values.append(sign)
            options["sign"] = sign

        else:
            raise ValueError(f"{sign} is not = or =/")

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        return self.create_definition(
            "defined-as",
            values,
            start,
            self.tell(),
            **options
        )

    def scan_cwsp(self):
        """
        c-wsp          =  WSP / (c-nl WSP)
        """
        start = self.tell()
        space = self.read_thru_hspace()
        if space:
            stop = self.tell()
            cwsp = self.create_definition("c-wsp", [space], start, stop)

        else:
            comment = self.scan_cnl()
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
                raise ValueError("(c-nl WSP) missing WSP")

        return cwsp

    def scan_cnl(self):
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
            raise ValueError("c-nl rule failed")

        return cnl

    def scan_comment(self):
        """
        comment        =  ";" *(WSP / VCHAR) CRLF
        """
        start = self.tell()
        if self.read(1) != ";":
            raise ValueError("Comment must start with ;")

        comment = self.read_until_newline()
        if not comment.endswith("\n"):
            raise ValueError("Comment must end with a newline")

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
            values.append(scanner.scan_cwsp())

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
                values.append(scanner.scan_cwsp())

            ch = self.peek()
            if ch == "/" or ch == "|":
                values.append(self.read(1))

                with self.optional() as scanner:
                    values.append(scanner.scan_cwsp())

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
                    values.append(scanner.scan_cwsp())
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
        min_repeat = self.read_thru_chars(String.DIGITS)
        if min_repeat:
            min_repeat = int(min_repeat)

        else:
            min_repeat = 0

        ch = self.peek()
        if ch == "*":
            self.read(1)
            max_repeat = 0

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
            qs = self.scan_quotedstring(case_sensitive=False)
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
            values.append(self.scan_proseval())

        else:
            raise ValueError(f"Unknown element starting with [{ch}]")

        return self.create_definition(
            "element",
            values,
            start,
            self.tell()
        )

    def scan_quotedstring(self, case_sensitive=False):
        """
        https://datatracker.ietf.org/doc/html/rfc7405

        quoted-string  =  DQUOTE *(%x20-21 / %x23-7E) DQUOTE
                                ; quoted string of SP and VCHAR
                                ;  without DQUOTE
        """
        if self.peek() != "\"":
            raise ValueError("Char value begins with double-quote")

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
            raise ValueError("num-val starts with %")

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
                raise ValueError("num-val with no number values")

            values.append(v)
            ch = self.peek()

            if ch == "." or ch == "-":
                values.append(self.read(1))

                v = self.read_thru_chars(numchars)
                if not v:
                    raise ValueError(
                        f"num-val {ch} with no number values after"
                    )

                values.append(v)

        elif ch in "si":
            values.append(self.scan_quotedstring(case_sensitive=(ch == "s")))
            name = "char-val"

        else:
            raise ValueError(f"Terminal value {ch} failed")

        return self.create_definition(
            name,
            values,
            start,
            self.tell()
        )

    def scan_proseval(self):
        """
        prose-val      =  "<" *(%x20-3D / %x3F-7E) ">"
                                ; bracketed string of SP and VCHAR
                                ;  without angles
                                ; prose description, to be used as
                                ;  last resort
        """
        start = self.tell()

        if self.read(1) != "<":
            raise ValueError("prose-val begins with <")

        val = self.read_until_delim(">").strip(">")
        return self.create_definition(
            "prose-val",
            [val],
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
            raise ValueError(f"Group must start with {start_char}")

        values.append(ch)

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        values.append(self.scan_alternation())

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        ch = self.read_thru_chars(stop_char)
        if ch != stop_char:
            raise ValueError(f"Group must end with {stop_char}")

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


class ABNFParser(object):
    """
    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form

    A parser takes the stream of tokens from the lexer and gives it some sort
    of structure that was represented by the original text
    """
    grammar_class = ABNFGrammar

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

    def __getattr__(self, key):
        try:
            return self.grammar.parser_rules[key]

        except KeyError as e:
            raise AttributeError(key) from e

#     def parse_rule(self, rule, scanner):
#         for definition in rule.definitions:
#             pass
# 
#     def parse(self, buffer):
#         rule = self.parse_grammar()
#         scanner = Scanner(buffer)
#         r = self.parse_rule(rule, scanner)

        # all rule definitions have the same basic structure: [rulename, elements]
        # And elements breaks down to: 
        #   elements -> alternation
        #   alternation -> concatenation
        #   concatenation -> repetition
        #   repetition -> repeat element
        #
        #   so basically every rule can eventually get to [repeat, element] and
        #   that's what we want to iterate on. They will have to be grouped into
        #   alternates, so each iteration will be a set of [repeat, element] that
        #   have to be matched for buffer to be valid. Really though, it should
        #   be a sequence of [repeat, rulename|*val].
        #
        #   so each alternation should break down to [repeat, rulename|*val], so
        #   this will be really recursive, with each rule checking itself and then
        #   bubbling up and each new rule checking the repeat value
        #   - rule



