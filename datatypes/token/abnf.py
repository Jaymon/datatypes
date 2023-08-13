# -*- coding: utf-8 -*-
from contextlib import contextmanager

from ..compat import *
from ..string import String
from .base import Token, Tokenizer, Scanner


class Definition(object):
    def __init__(self, name, values, start, stop, **options):
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

        raise AttributeError(key)


class ABNFGrammar(Scanner):
    """This lexes an ABNF grammar

    It's a pretty standard lexer that follows 5234:

        https://www.rfc-editor.org/rfc/rfc5234

    and the update for char-val in 7405:

        https://datatracker.ietf.org/doc/html/rfc7405

    https://en.wikipedia.org/wiki/Augmented_Backus%E2%80%93Naur_form
    """

    @contextmanager
    def optional(self):
        try:
            with self.transaction() as scanner:
                yield scanner

        except (IndexError, ValueError) as e:
            pass

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

    def scan_rule(self):
        """
        rule           =  rulename defined-as elements c-nl
                                ; continues if next line starts
                                ;  with white space
        """
        rulename = self.scan_rulename()
        defined_as = self.scan_definedas()
        elements = self.scan_elements()
        cnl = self.scan_cnl()

        return Definition(
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
        if ch in String.ALPHA:
            rulename = self.read_thru_chars(String.ALPHANUMERIC + "-")

        else:
            raise ValueError(f"{ch} was not an ALPHA character")

        stop = self.tell()
        return Definition("rulename", [rulename], start, stop)

    def scan_definedas(self):
        """
        defined-as     =  *c-wsp ("=" / "=/") *c-wsp
                                ; basic rules definition and
                                ;  incremental alternatives
        """
        values = []
        start = self.tell()

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        sign = scanner.read_thru_chars("=/")
        if sign in set(["=", "=/"]):
            values.append(sign)

        else:
            raise ValueError(f"{sign} is not = or =/")

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        return Definition(
            "defined-as",
            values,
            start,
            self.tell()
        )

    def scan_cwsp(self):
        """
        c-wsp          =  WSP / (c-nl WSP)
        """
        start = self.tell()
        space = self.read_thru_hspace()
        if space:
            stop = self.tell()
            cwsp = Definition("c-wsp", [space], start, stop)

        else:
            comment = self.scan_cnl()
            start = self.tell()
            space = self.read_thru_hspace()
            if space:
                stop = self.tell()
                cwsp = Definition("c-wsp", [comment, space], start, stop)

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
            cnl = Definition(
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
            crlf = Definition("CRLF", newline, start, stop)

            cnl = Definition(
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
        return Definition("comment", [comment.strip()], start, stop)

    def scan_elements(self, scanner):
        """
        elements       =  alternation *c-wsp
        """
        start = self.tell()
        values = []

        values.append(self.scan_alternation())

        with self.optional() as scanner:
            values.append(scanner.scan_cwsp())

        return Definition(
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
            if ch == "/":
                with self.optional() as scanner:
                    values.append(scanner.scan_cwsp())

                values.append(self.scan_concatenation())

            else:
                break

        return Definition(
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

        return Definition(
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
        return Definition(
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
            if ch in String.DIGITS:
                max_repeat = int(self.read_thru_chars(String.DIGITS))

        else:
            max_repeat = min_repeat

        return Definition(
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
                Definition(
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
            raise ValueError("Unknown element")

        return Definition(
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
        return Definition(
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

        return Definition(
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
        return Definition(
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

        return Definition(
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
        return Definition(
            "option",
            group.values,
            group.start,
            group.stop
        )





class ABNFElement(object):
    CHARVAL = 1
    RULENAME = 2
    GROUP = 3
    COMMENT = 4
    def __init__(self, element_type, value=None):
        self.element_type = element_type
        self.value = value
        self.min_count = 1
        self.max_count = 1
        self.or_clause = False


class ABNFRule(Token):

    def __init__(self, tokenizer, name, start, stop):
        self.name = name
        self.definitions = []
        #self.definitions = definitions
        #self.comments = comments

        super().__init__(tokenizer, start=start, stop=stop)

    def __iter__(self):
        alternation = []
        for definition in self.definitions:
            if definition.or_clause:
                alternation.append(definition)

            else:
                if alternation:
                    alternation.append(definition)
                    yield alternation

                    alternation = []

                else:
                    yield [definition]

#     def x__init__(self, tokenizer, name, definitions, comments, start, stop):
#         self.name = name
#         self.definitions = definitions
#         self.comments = comments
# 
#         super().__init__(tokenizer, start=start, stop=stop)


class ABNFTokenizer(Tokenizer):

    rule_class = ABNFRule

    scanner_class = ABNFGrammar

    definition_class = Definition

    def set_buffer(self, buffer):
        self.buffer = self.scanner_class(buffer)

    def next(self):
        rule = self.next_rule()
        if rule:
            scanner = self.scanner_class(rule.buffer)
            rulename = self.scan_rulename(scanner)
            defined_as = self.scan_defined_as(scanner)
            elements = self.scan_elements(scanner)
            comment = self.scan_cnl(scanner)


#             rule = self.rule_class(
#                 self,
#                 rulename,
#                 start=stmt.start,
#                 stop=stmt.stop
#             )
#             return self.tokenize_definition(rule, scanner)

        else:
            raise StopIteration()

    def next2(self):
        scanner = self.buffer
        start = scanner.tell()
        comments = []
        definitions = []

        name = scanner.read_to_delim("=").strip()

        # move passed the equal sign and whitespace to the right of the equal
        # sign
        scanner.read_thru_chars("= \t")

        while scanner:
            ch = scanner.peek()

            if ch == "\"":
                literal = scanner.read_until_delim("\"", count=2)
                literal = literal.strip("\"")
                definitions.append(literal)

            elif ch in String.ASCII_LETTERS:
                rule = scanner.read_to_chars(String.WHITESPACE + ";")
                definitions.append(rule)

            elif ch == ";":
                comments.append(scanner.read_to_newline())

            elif ch == "\n":
                scanner.read_thru_chars("\n")
                ch = scanner.peek()
                if not ch.isspace():
                    break

            else:
                scanner.read_thru_chars(" \t")

        stop = scanner.tell() - 1
#         if stop < 0:
#             pout.v(scanner.getvalue())
#             stop = len(scanner.getvalue()) - 1

        return self.token_class(
            self,
            name=name,
            definitions=definitions,
            comments=comments,
            start=start,
            stop=stop
        )


    def tokenize_definition(self, rule, scanner):
        while scanner:
            ch = scanner.peek()

            if ch == "\"":
                literal = scanner.read_until_delim("\"", count=2)
                literal = literal.strip("\"")
                rule.definitions.append(self.definition_class(
                    self.definition_class.LITERAL,
                    literal
                ))

            elif ch in String.ALPHANUMERIC + "-":
                rulename = scanner.read_to_chars(String.WHITESPACE + ";")
                rule.definitions.append(self.definition_class(
                    self.definition_class.RULE,
                    rulename.lower()
                ))

            elif ch == "[":
                gstart = scanner.tell()
                gbuffer = scanner.read_until_delim("]")
                gstop = scanner.tell()
                grule = self.rule_class(
                    self,
                    "",
                    start=gstart,
                    stop=gstop,
                )
                gscanner = self.scanner_class(gbuffer[1:-1])
                grule = self.tokenize_definition(grule, gscanner)

                group = self.definition_class(
                    self.definition_class.GROUP,
                    grule,
                )
                group.min = 0
                rule.definitions.append(group)

            elif ch == "/" or ch == "|":
                rule.definitions[-1].or_clause = True
                scanner.read_thru_chars("/|")

            elif ch == ";":
                rule.definitions.append(self.definition_class(
                    self.definition_class.COMMENT,
                    scanner.read_to_newline()
                ))

            elif ch == "\n":
                scanner.read_thru_chars("\n")
                ch = scanner.peek()
                if not ch.isspace():
                    break

            else:
                scanner.read_thru_chars(" \t")

        return rule

