# -*- coding: utf-8 -*-
from collections.abc import Iterable
from collections import Counter
from functools import cached_property
import re

from ..compat import *
from ..string import String
from ..token import Token, Tokenizer, Scanner


class HTML(String):
    """Adds HTML specific methods on top of the String class"""

    # https://developer.mozilla.org/en-US/docs/Glossary/Void_element
    # https://developer.mozilla.org/en-US/docs/Glossary/Empty_element
    # void, or empty, elements are elements that don't have a body
    VOID_TAGNAMES = set([
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "keygen",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ])

    # https://developer.mozilla.org/en-US/docs/Web/HTML/Block-level_elements
    # https://www.w3schools.com/html/html_blocks.asp
    BLOCK_TAGNAMES = set([
        "article",
        "aside",
        "blockquote",
        "body",
        "br",
        "button",
        "canvas",
        "caption",
        "col",
        "colgroup",
        "dd",
        "div",
        "dl",
        "dt",
        "embed",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hgroup",
        "hr",
        "li",
        "map",
        "object",
        "ol",
        "output",
        "p",
        "pre",
        "progress",
        "section",
        "table",
        "tbody",
        "textarea",
        "tfoot",
        "th",
        "thead",
        "tr",
        "ul",
        "video",
    ])

    # https://www.w3schools.com/html/html_blocks.asp
    # NOTE: an inline element cannot contain a block-level element
    INLINE_TAGNAMES = set([
        "a",
        "abbr",
        "acronym",
        "b",
        "bdo",
        "big",
        "cite",
        "code",
        "dfn",
        "em",
        "i",
        "img",
        "input",
        "kbd",
        "label",
        "map",
        "object",
        "output",
        "q",
        "samp",
        "script",
        "select",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "time",
        "tt",
        "var",
    ])

    def plain(self, **kwargs):
        hc = kwargs.pop("cleaner_class", HTMLCleaner)(**kwargs)
        return hc.feed(self)

    def tags(self, tagnames=None, **kwargs):
        """Return only the tags in `tagnames`

        :param tagnames: list[str], the tags to return
        :returns: HTMLTokenizer[HTMLToken]
        """
        tokenizer_class = kwargs.get("tokenizer_class", HTMLTagTokenizer)
        return tokenizer_class(self, tagnames)

    def inject_into_head(self, html):
        """Inject passed in html into head

        Moved from bang.utils on 1-6-2023

        :param html: str, the html that will be injected to the head tag of
            self
        :returns: HTML, a new HTML string with the injected html
        """
        def callback(m):
            return "{}{}{}".format(m.group(1), html, m.group(0))

        regex = r"(\s*)(</head>)"
        ret = re.sub(regex, callback, self, flags=re.I|re.M)
        return type(self)(ret)

    def inject_into_body(self, html):
        """Inject passed in html into body

        Moved from bang.utils on 1-6-2023

        :param html: str, the html that will be injected to the body tag of
            self
        :returns: HTML, a new HTML string with the injected html
        """
        def callback(m):
            return "{}{}{}".format(m.group(1), html, m.group(0))

        regex = r"(\s*)(</body>)"
        ret = re.sub(regex, callback, self, flags=re.I|re.M)
        return type(self)(ret)

    def strip_tags(self, strip_tagnames=None, **kwargs):
        """Strip tags, completely removing any tags in remove_tags list

        This is different than `.plain()` in that only the html tags that
        in `strip_tagnames` are completely removed, all other html tags
        remain intact

        Moved from bang.utils on 1-6-2023

        http://stackoverflow.com/a/925630

        :param strip_tagnames: list[str], a list of tags that will be
        completely removed from the html
        :returns: str, the html with tags in `strip_tagnames` completely
            removed
        """
        hc = kwargs.pop("cleaner_class", HTMLCleaner)(
            ignore_tagnames=True,
            strip_tagnames=strip_tagnames
        )
        return hc.feed(self)

    def blocks(self, *, ignore_tagnames=None, **kwargs):
        """Tokenize the html into blocks. This is tough to describe so go
        read the description on the html block iterator this returns

        :returns: HTMLBlockTokenizer
        """
        tokenizer_class = kwargs.get("tokenizer_class", HTMLBlockTokenizer)
        return tokenizer_class(self, ignore_tagnames=ignore_tagnames)


class HTMLParser(HTMLParser):
    """Internal parent class. Used by other more specialized HTML parsers"""
    def _normalize_tagnames(self, tagnames) -> set[str]:
        tnames = set()

        if tagnames:
            tnames.update(map(lambda s: s.lower(), tagnames))

        return tnames

    def _in_tagnames(self, tagname, attrs, tagnames) -> bool:
        """Check if `tagnames` is in `tagnames`.

        Uses `attrs` for simple css selector support (eg, `div.foo` to match
        div tags with the `foo` class, and `div#foo` to match div tags with
        the `foo` id)

        :param tagname: str
        :param attrs: list[tuple[str, str]]
        :param tagnames: set, usually the value returned from
            `._normalize_tagnames()`
        """
        ret = False

        if tagnames:
            if tagname in tagnames:
                ret = True

            else:
                # really basic css selector support
                for k, v in attrs:
                    if k == "class":
                        selector = "{}.{}".format(tagname, v)
                        if selector in tagnames:
                            ret = True
                            break

                    elif k == "id":
                        selector = "{}#{}".format(tagname, v)
                        if selector in tagnames:
                            ret = True
                            break

        return ret


class HTMLCleaner(HTMLParser):
    """Internal class. Can turn html to plain text, completely remove
    certain tags, or both

    .. Example:
        # convert html to plain text
        html = "this is <b>some html</b>
        text = HTMLCleaner().feed(html)
        print(text) # this is some html

        # strip certain tags from the html
        html = "<p>this is some <span>fancy text</span> stuff</p>"
        text = HTMLCleaner(
            ignore_tagnames=True,
            strip_tagnames=["span"]
        ).feed(html)
        print(text) # <p>this is some stuff</p>

    http://stackoverflow.com/a/925630/5006
    https://docs.python.org/3/library/html.parser.html
    """
    def __init__(
        self,
        *,
        ignore_tagnames=None,
        strip_tagnames=None,
        block_sep="\n",
        inline_sep="",
        keep_img_src=False,
        **kwargs
    ):
        """create an instance and configure it

        :keyword ignore_tagnames: Collection[str]|bool|None, the list of
            tagnames to not clean, either a list of tagnames (eg ["a"]) or
            True. If True, then all tags will be ignored except the tags in
            `strip_tagnames`
        :keyword strip_tagnames: Collection[str]|None, the list of tags to
            be completely stripped out (everything from the opening <TAGNAME
            to the closing </TAGNAME> will be removed)
        :keyword block_sep: string, strip a block tag and then add this to the
            end of the stripped tag, so if you have <p>foo bar<p> and
            block_sep=\n, then the stripped string would be foo bar\n
        :keyword inline_sep: string, same as block_sep, but gets added to the
            end of the stripped inline tag
        :keyword keep_img_src: boolean, if True, the img.src attribute will
            replace the full <img /> tag, this is nice when you want plain
            text but want to keep knowledge of the images that were in the
            original html
        """
        if ignore_tagnames is True:
            self.ignore_tagnames = ignore_tagnames

        else:
            self.ignore_tagnames = self._normalize_tagnames(ignore_tagnames)

        self.strip_tagnames = self._normalize_tagnames(strip_tagnames)

        self.block_sep = block_sep
        self.inline_sep = inline_sep
        self.keep_img_src = keep_img_src

        super().__init__(**kwargs)

    def reset(self):
        self.cleaned_html = ""
        self.stripping_tagnames_stack = []
        self.stripping_tags = Counter()

        super().reset()

    def feed(self, data) -> str:
        """process `data` based on the instance flags

        :returns: str, the processed/cleaned data
        """
        self.cleaned_html = ""

        super().feed(data)

        return self.cleaned_html

    def close(self) -> str:
        """Finish processing any data left in the buffer and return the
        cleaned buffer

        :returns: str, the processed/cleaned buffer
        """
        self.cleaned_html = ""

        super().close()

        return self.cleaned_html

    def _is_ignored(self, tagname, attrs=None) -> bool:
        """Return True if tagname should be ignored"""
        if self.ignore_tagnames is True:
            return True

        else:
            return self._in_tagnames(
                tagname,
                attrs or [],
                self.ignore_tagnames
            )

    def _is_stripped(self, tagname, attrs=None) -> bool:
        """Return True if tagname should be completely stripped"""
        return self._in_tagnames(
            tagname,
            attrs or [],
            self.strip_tagnames
        )

    def handle_data(self, data):
        if not self.stripping_tags:
        #if not self.stripping_tagnames_stack:
            self.cleaned_html += data

    def handle_entityref(self, name):
        """keep entityrefs as they were

        https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_entityref
        > This method is never called if convert_charrefs is True
        """
        entity = f"&{name};"
        self.cleaned_html += entity

    def handle_starttag(self, tagname, attrs):
        # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag

        if self._is_stripped(tagname, attrs):
            self.stripping_tags[tagname] += 1
            #self.stripping_tagnames_stack.append(tagname)

        else:
            if not self.stripping_tags:
                if self._is_ignored(tagname, attrs):
                    self.cleaned_html += self.get_starttag_text()

                else:
                    if tagname == "img" and self.keep_img_src:
                        for attr_name, attr_val in attrs:
                            if attr_name == "src":
                                self.cleaned_html += "{}{}".format(
                                    self.block_sep,
                                    attr_val
                                )

    def handle_endtag(self, tagname):
        if self.stripping_tags:
            if tagname in self.stripping_tags:
                self.stripping_tags[tagname] -= 1
                if self.stripping_tags[tagname] == 0:
                    del self.stripping_tags[tagname]

        else:
            if self._is_ignored(tagname):
                self.cleaned_html += f"</{tagname}>"

            else:
                if tagname in HTML.BLOCK_TAGNAMES:
                    self.cleaned_html += self.block_sep

                else:
                    if tagname == "img" and self.keep_img_src:
                        self.cleaned_html += self.block_sep

                    else:
                        self.cleaned_html += self.inline_sep


class HTMLTagParser(HTMLParser):
    """Internal class. This is the parser used by HTMLTagTokenizer.

    This is not a general purpose parser, it's purpose is only to find the
    tagnames passed into it, for example, if you pass into a website's html
    and don't specify the tags you want (like "a"), then it will return you
    one tag info dict, the top level "html" tag, all the other tags will be
    in the "body" keys.

    If you need something more full featured you should use BeautifulSoup or
    the like.

    https://docs.python.org/3/library/html.parser.html
    """
    def __init__(self, tagnames=None):
        """
        :param tagnames: Collection[str], the list of wanted tag names
        """
        super().__init__()

        self.tagnames = self._normalize_tagnames(tagnames)

    def reset(self):
        super().reset()

        # as child tags are parsed they are placed in here until the closing
        # tag is found
        self.tag_stack = []

        # once the tag stack is completely depleted the main tag is appended
        # into this property, this is returned in `.feed()` and `.close()`
        self.closed_tags = []

    def _include_tag(self, tagname, attrs) -> bool:
        """Returns True if tagname is one of the tags that should be parsed

        :param tagname: str, lowercase tagname
        :returns: True if tagname should be parsed, False otherwise
        """
        return (
            not self.tagnames
            or self._in_tagnames(tagname, attrs, self.tagnames)
        )

    def _add_tag(self, tag):
        if self.tag_stack:
            self.tag_stack[-1]["body"].append(tag)

        else:
            self.closed_tags.append(tag)

    def feed(self, data) -> dict|None:
        """This reaturns the tag info dict or None if no tag was found. this
        method is called in `HTMLTokenizer.next()`"""
        self.closed_tags = []

        super().feed(data)

        return self.closed_tags

    def close(self) -> dict|None:
        """This reaturns the tag info dict or None if no straggler tag was
        found. this method is called in `HTMLTokenizer.next()` if the buffer
        is depleted"""
        self.closed_tags = []

        super().close()

        while self.tag_stack:
            tag = self.tag_stack.pop(-1)

            stop_line, stop_ch = self.getpos()
            tag["stop"] = stop_ch
            tag["stop_line"] = stop_line

            self._add_tag(tag)

        return self.closed_tags

    def handle_starttag(self, tagname, attrs):
        """
        https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
        """
        # we add the tag if it is in the wanted tag list or if it is part of
        # the body of another tag
        #pout.b(tagname)

        if not self._include_tag(tagname, attrs) and not self.tag_stack:
            return

        start_line, start_ch = self.getpos()

        tag = {
            "tagname": tagname,
            "attrs": attrs,
            "body": [],
            "start": start_ch,
            "start_line": start_line,
        }

        if tagname in HTML.VOID_TAGNAMES:
            tag["stop"] = start_ch
            tag["stop_line"] = start_line
            self._add_tag(tag)

        else:
            self.tag_stack.append(tag)


    def handle_data(self, data):
        """
        https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_data
        """
        if not self.tag_stack:
            return

        start_line, start_ch = self.getpos()

        self.tag_stack[-1]["body"].append({
            "body": [data],
            "start": start_ch,
            "start_line": start_line,
            "stop": start_ch + len(data),
        })

    def handle_endtag(self, tagname):
        """
        https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
        """
        if not self.tag_stack or (self.tag_stack[-1]["tagname"] != tagname):
            return

        stop_line, stop_ch = self.getpos()

        tag = self.tag_stack.pop(-1)

        tag["stop"] = stop_ch
        tag["stop_line"] = stop_line

        self._add_tag(tag)


class HTMLTagToken(Token):
    """This is what is returned from the HTMLTokenizer

        .tagname - the name of the tag
        .text - the body of the tag
        .attrs - the attributes
    """
    @cached_property
    def text(self):
        text = ""
        for d in self.taginfo.get("body", []):
            if "tagname" in d:
                t = type(self)(self.tokenizer, d)
                text += t.__str__()

            else:
                text += "".join(d["body"])

        return text

    @cached_property
    def attrs(self):
        attrs = {}
        for attr_name, attr_val in self.taginfo.get("attrs", []):
            attrs[attr_name] = attr_val

        return attrs

    def __init__(self, tokenizer, taginfo):
        self.tagname = taginfo.get("tagname", "")
        self.taginfo = taginfo

        super().__init__(
            tokenizer,
            taginfo.get("start", -1),
            taginfo.get("stop", -1)
        )

    def __getattr__(self, key):
        if key in self.taginfo:
            return self.taginfo[key]

        else:
            # support foo-bar and foo_bar attribute fetching
            for k in [key.replace("-", "_"), key.replace("_", "-")]:
                if k in self.attrs:
                    return self.attrs[k]

        raise AttributeError(key)

    def __getitem__(self, key):
        try:
            return self.__getattr__(key)

        except AttributeError as e:
            raise KeyError(key) from e

    def tags(self, tagnames=None):
        """Returns the matching subtags of this tag"""
        tagnames = set(t.lower() for t in tagnames) if tagnames else set()

        for d in self.taginfo.get("body", []):
            if "tagname" in d:
                if not tagnames or d["tagname"] in tagnames:
                    t = type(self)(self.tokenizer, d)
                    yield t
                    yield from t.tags(tagnames)

    def __str__(self):
        attrs = ""
        for ak, av in self.attrs.items():
            attrs += ' {}="{}"'.format(ak, av)

        s = "<{}{}>{}</{}>".format(
            self.tagname,
            attrs,
            self.text,
            self.tagname
        )
        return s


class HTMLTagTokenizer(Tokenizer):
    """Tokenize HTML and only yield asked for tagnames

    This is the public interface for HTMLParser. It is primarily used via
    `HTML.tags`
    """
    token_class = HTMLTagToken

    def __init__(self, buffer, tagnames=None):
        """
        :param buffer: str|io.IOBase, this is the html that will be tokenized
        :param tagnames: Collection[str], the tags to be parsed
        """
        super().__init__(buffer)

        self.parser = HTMLTagParser(tagnames=tagnames)
        self.buffered_tags = []

    def create_token(self, taginfo):
        return self.token_class(self, taginfo)

    def next(self):
        tag = None

        if self.buffered_tags:
            taginfo = self.buffered_tags.pop(0)
            tag = self.create_token(taginfo)

        else:
            # we keep reading chunks of buffer until the html parser returns
            # something we can use
            while tag is None:
                if line := self.buffer.readline():
                    if taginfos := self.parser.feed(line):
                        self.buffered_tags.extend(taginfos)
                        tag = self.next()
                        #tag = self.create_token(taginfo)

                else:
                    if taginfos := self.parser.close():
                        self.buffered_tags.extend(taginfos)
                        #tag = self.create_token(taginfo)
                        tag = self.next()

                    break

        return tag


class HTMLBlockTokenizer(Iterable):
    """Internal class. Iterate through blocks of html and the inner text of
    the element.

    The way to describe this is that everything this iterates would equal
    the original input if it was all concatenated together.

    .. Example:
        html = HTMLBlockTokenizer(
            "before all"
            " <p>after p before a "
            " <a href=\"#\">between a</a>"
            " after a</p>"
            " after all"
        )

        blocks = ""
        for element in html:
            # ("", "before all")
            # ("<p>", "after p before a")
            # ("<a href="#">", "between a")
            # ("</a>", "after a")
            # ("</p>", "after all")
            blocks += element[0]
            blocks += element[1]

        assert blocks == html

    Now, if you pass any tags into `ignore_tagnames` then the first element
    of the tuple will be the full value of that tag

    .. Example:
        html = HTMLBlockTokenizer(
            (
                " <p>after p before a "
                " <a href=\"#\">between a</a>"
                " after a</p>"
            ),
            ignore_tagnames=["a"]
        )

        blocks = ""
        for element in html:
            # ("<p>", "after p before a")
            # ("<a href="#">between a</a>", "after a")
            # ("</p>", "")
            blocks += element[0]
            blocks += element[1]

        assert blocks == html

    This allows for things like getting all the plain text bodies for further
    processing, like automatically linking URLs and not having to worry with
    linking things that are already linked. I know that might seem niche but
    I've had to do this exact thing in multiple projects throughout the
    years.

    Moved from bang.utils on 1-6-2023, fleshed out and integrated into HTML
    on 3-3-2025
    """
    def __init__(self, html, *, ignore_tagnames=None, **kwargs):
        """Create a block tokenizer

        :param html: str|io.IOBase, the html that is going to be split into
            blocks
        :keyword ignore_tagnames: Collection, the list/set of tag names that
            should be ignored (eg, ["a", "pre"])
        :keyword scanner_class: Scanner
        """
        self.scanner = kwargs.get("scanner_class", Scanner)(html)

        self.ignore_start_set = set()
        self.ignore_stop_set = set()

        if ignore_tagnames:
            for tagname in ignore_tagnames:
                self.ignore_start_set.add(f"<{tagname}>")
                self.ignore_start_set.add(f"<{tagname} ")
                self.ignore_stop_set.add(f"</{tagname}>")

    def _startswith_tagname(self, html) -> bool:
        """Internal method. Used to see if the html starts with an ignored
        tag name"""
        for tag in self.ignore_start_set:
            if html.startswith(tag):
                return True

        return False

    def _endswith_tagname(self, html) -> bool:
        """Internal method. Used to see if the html ends with an ignored
        tag name"""
        for tag in self.ignore_stop_set:
            if html.endswith(tag):
                return True

        return False

    def __iter__(self) -> Iterable[tuple[str, str]]:
        """returns plain text blocks that aren't in html tags

        :returns: each tuple is the html tag and then the inner html of that
            tag
        """
        s = self.scanner
        html = ""
        plain = s.read_to(delim="<")
        while True:
            if html or plain:
                yield html, plain

            html = s.read_to(
                delim=">",
                ignore_between_delims=["\"", "'"],
                include_delim=True
            )
            if html:
                plain = s.read_to(delim="<")
                if self._startswith_tagname(html):
                    while not self._endswith_tagname(html):
                        html += plain
                        h = s.read_to(delim=">", include_delim=True)
                        plain = s.read_to(delim="<")

                        if h or plain:
                            html += h

                        else:
                            # we've reached EOF
                            break

            if not html:
                # we've reached the end of the file
                break

