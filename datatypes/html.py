# -*- coding: utf-8 -*-
from collections import Counter
import re

from . import environ
from .compat import *
from .compat import HTMLParser as BaseHTMLParser
from .utils import make_list
from .string import String
from .token import Token, Tokenizer, Scanner


class HTML(String):
    """Adds HTML specific methods on top of the String class"""
    def plain(self, *args, **kwargs):
        return HTMLCleaner.strip_tags(self, *args, **kwargs)

    def tags(self, tagnames=None):
        from .token import HTMLTokenizer # avoid circular dep

        tokenizer = HTMLTokenizer(self, tagnames)
        for t in tokenizer:
            yield t

    def inject_into_head(self, html):
        """Inject passed in html into head

        Moved from bang.utils on 1-6-2023

        :param html: str, the html that will be injected to the head tag of self
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

        :param html: str, the html that will be injected to the body tag of self
        :returns: HTML, a new HTML string with the injected html
        """
        def callback(m):
            return "{}{}{}".format(m.group(1), html, m.group(0))

        regex = r"(\s*)(</body>)"
        ret = re.sub(regex, callback, self, flags=re.I|re.M)
        return type(self)(ret)

    def strip_tags(self, remove_tags=None):
        """Strip tags, completely removing any tags in remove_tags list

        you probably should use .plain() instead but this still has a place because
        it will completely remove anything in remove_tags which HTMLCleaner doesn't
        support (.plain() uses HTMLCleaner)

        Moved from bang.utils on 1-6-2023

        :param remove_tags: list, a list of tags that will be completely removed
            not just plained
        :returns: str, the plain text of the html with remove_tags completely removed
        """
        return HTMLStripper(self, remove_tags=remove_tags).get_data()


class HTMLCleaner(BaseHTMLParser):
    """strip html tags from a string

    :example:
        html = "this is <b>some html</b>
        text = HTMLCleaner.strip_tags(html)
        print(text) # this is some html

    http://stackoverflow.com/a/925630/5006
    https://docs.python.org/2/library/htmlparser.html
    """
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Block-level_elements
    BLOCK_TAGNAMES = set([
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "canvas",
        "dd",
        "div",
        "dl",
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
        "main",
        "nav",
        "noscript",
        "ol",
        "output",
        "p",
        "pre",
        "section",
        "table",
        "tfoot",
        "ul",
        "video",
    ])

    @classmethod
    def strip_tags(cls, html, *args, **kwargs):
        s = cls(*args, **kwargs)
        # convert entities back otherwise stripper will get rid of them
        # http://stackoverflow.com/a/28827374/5006
        #html = s.unescape(html)
        s.feed(html)
        return s.get_data()

    def __init__(self, block_sep="\n", inline_sep="", keep_img_src=False):
        """create an instance and configure it

        :param block_sep: string, strip a block tag and then add this to the end of the
            stripped tag, so if you have <p>foo bar<p> and block_sep=\n, then the stripped
            string would be foo bar\n
        :param inline_sep: string, same as block_sep, but gets added to the end of the
            stripped inline tag
        :param keep_img_src: boolean, if True, the img.src attribute will replace the <img />
            tag
        """
        self.fed = []
        self.block_sep = block_sep
        self.inline_sep = inline_sep
        self.keep_img_src = keep_img_src

        super().__init__()

    def handle_data(self, d):
        self.fed.append(d)

    def handle_entityref(self, name):
        self.fed.append("&{};".format(name))

    def handle_starttag(self, tag, attrs):
        # https://docs.python.org/3/library/html.parser.html#html.parser.HTMLParser.handle_starttag
        if tag == "img" and self.keep_img_src:
            for attr_name, attr_val in attrs:
                if attr_name == "src":
                    self.fed.append("\n{}\n".format(attr_val))

    def handle_endtag(self, tagname):
        if tagname in self.BLOCK_TAGNAMES:
            if self.block_sep:
                self.fed.append(self.block_sep)
        else:
            if self.inline_sep:
                self.fed.append(self.inline_sep)

    def get_data(self):
        return self.unescape("".join(self.fed))

    @classmethod
    def unescape(cls, s):
        """unescapes html entities (eg, &gt;) to plain text (eg, &gt; becomes >)"""
        # https://stackoverflow.com/a/2087433/5006
        return html.unescape(s)


class HTMLParser(BaseHTMLParser):
    """Parses HTML

    This is a very simple html parser, if you need something more full featured
    you should use BeautifulSoup or the like

    This can act like a stream/IO object

    :Example:
        # get all <a> tags from a block of html
        p = HTMLParser(html, "a")
        for atag in p:
            print(atag)

    https://docs.python.org/3/library/html.parser.html
    """
    # https://developer.mozilla.org/en-US/docs/Glossary/Empty_element
    EMPTY_TAGNAMES = set([
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

    def __init__(self, data, tagnames=None):
        """create an instance

        :param data: string, the html
        :param tagnames: list|string, the tags you want to parse out of data
        """
        super(HTMLParser, self).__init__()

        self.handle_tagnames(tagnames)
        self.feed(data)

    def handle_tagnames(self, tagnames):
        if tagnames:
            tagnames = set(map(lambda s: s.lower(), make_list(tagnames)))

        self.tagnames = tagnames

    def is_tagname(self, tagname):
        """Returns True if tagname is one of the tags that should be parsed

        :param tagname: str, lowercase tagname
        :returns: bool, True if tagname should be parsed, False otherwise
        """
        return not self.tagnames or tagname in self.tagnames

    def feed(self, data):
        """This .feed is different than parent's .feed in that data has to be
        the full html, so you can't keep calling it, every time you call this method
        it will set .data and parse it and place it into .tags
        """
        self.stack = []
        self.tags = []
        self.data = data
        self.seek(0)

        super(HTMLParser, self).feed(data)
        self.close()

    def close(self):
        # clean up any stragglers, we now know the HTML was invalid
        while self.stack:
            self.tags.append(self.stack.pop(-1))

    def append(self, tag):
        if self.stack:
            self.stack[-1]["body"].append(tag)
        else:
            self.tags.append(tag)

    def handle_starttag(self, tagname, attrs):
        # we add the tag if it is in the wanted tag list or if it is part of the
        # body of another tag
        if not self.is_tagname(tagname) and not self.stack:
            return

        start_line, start_ch = self.getpos()

        tag = {
            "tagname": tagname,
            "attrs": attrs,
            "body": [],
            "start": start_ch,
            "start_line": start_line,
        }

        if tagname in self.EMPTY_TAGNAMES:
            tag["stop"] = start_ch
            tag["stop_line"] = start_line
            self.append(tag)

        else:
            self.stack.append(tag)

    def handle_data(self, data):
        if not self.stack:
            return

        start_line, start_ch = self.getpos()
        self.stack[-1]["body"].append({
            "body": [data],
            "start": start_ch,
            "start_line": start_line,
            "stop": start_ch + len(data),
        })

    def handle_endtag(self, tagname):
        if not self.stack or (self.stack[-1]["tagname"] != tagname):
            return

        stop_line, stop_ch = self.getpos()
        tag = self.stack.pop(-1)
        tag["stop"] = stop_ch
        tag["stop_line"] = stop_line
        self.append(tag)

    def seekable(self):
        return True

    def seek(self, offset):
        """This is the current tag position, not the position while parsing the html"""
        self.tag_offset = offset

    def fileno(self):
        return 0

    def readable(self):
        return True

    def writeable(self):
        """https://docs.python.org/3/library/io.html#io.IOBase.writable"""
        return False

    def tell(self):
        """Return the current tag position"""
        return self.tag_offset

    def next(self):
        if self.tag_offset >= len(self.tags):
            raise StopIteration()

        tag = self.tags[self.tag_offset]
        self.tag_offset += 1
        return tag

    def reset(self):
        self.stack = []
        self.tags = []
        self.seek(0)
        super(HTMLParser, self).reset()

    def __next__(self):
        return self.next()

    def __iter__(self):
        self.seek(0)
        return self

    def __len__(self):
        return len(self.tags)


class HTMLToken(Token):
    """This is what is returned from the HTMLTokenizer

        .tagname - the name of the tag
        .text - the body of the tag
    """
    @property
    def text(self):
        text = []
        for d in self.taginfo.get("body", []):
            if "tagname" in d:
                t = type(self)(self.tokenizer, d)
                text.append(t.__unicode__())

            else:
                text.extend(d["body"])

        return "".join(text)

    def __init__(self, tokenizer, taginfo):
        self.tagname = taginfo.get("tagname", "")
        self.start = taginfo.get("start", -1)
        self.stop = taginfo.get("stop", -1)
        self.taginfo = taginfo
        self.tokenizer = tokenizer

    def __getattr__(self, k):
        if k in self.taginfo:
            return self.taginfo[k]

        else:
            ret = None
            for attr_name, attr_val in self.taginfo.get("attrs", []):
                if attr_name == k:
                    return attr_val

        raise AttributeError(k)
        #return super(HTMLToken, self).__getattr__(k)

    def attrs(self):
        ret = {}
        for attr_name, attr_val in self.taginfo.get("attrs", []):
            ret[attr_name] = attr_val
        return ret

    def __pout__(self):
        """used by pout python external library

        https://github.com/Jaymon/pout
        """
        return self.__unicode__()

    def __unicode__(self):
        attrs = ""
        for ak, av in self.attrs().items():
            attrs += ' {}="{}"'.format(ak, av)

        s = "<{}{}>{}</{}>".format(
            self.tagname,
            attrs,
            self.text,
            self.tagname
        )
        return s


class HTMLTokenizer(Tokenizer):
    DEFAULT_DELIMS = None
    token_class = HTMLToken

    def __init__(self, html, tagnames=None):
        """
        :param stream: io.IOBase, this is the input that will be tokenized, the stream
            has to be seekable
        :param delims: callback|string, if a callback, it should have the signature:
            callback(char) and return True if the char is a delim, False otherwise.
            If a string then it is a string of chars that will be considered delims
        """
        stream = HTMLParser(html, tagnames)
        super(HTMLTokenizer, self).__init__(stream)

    def next(self):
        taginfo = self.stream.next()
        return self.token_class(self, taginfo)

    def prev(self):
        ret = None
        pos = self.tell()
        if pos > 0:
            self.seek(pos - 1)
            ret = self.next()
        return ret

    def tell_ldelim(self):
        raise NotImplementedError()


class UnlinkedTagTokenizer(object):
    """This will go through an html block of code and return pieces that aren't
    linked (between <a> and </a>, or pre tags), allowing you to mess with the
    blocks of plain text that isn't special in some way

    Moved from bang.utils on 1-6-2023
    """
    def __init__(self, text):
        self.s = Scanner(text)

    def __iter__(self):
        """returns plain text blocks that aren't in html tags"""
        start_set = set(["<a ", "<pre>", "<pre "])
        stop_set = set(["</a>", "</pre>"])

        s = self.s
        tag = ""
        plain = s.to("<")
        while s:
            yield tag, plain

            tag = s.until(">")
            plain = s.to("<")
            if [st for st in start_set if tag.startswith(st)]:
            #if tag.startswith("<a"):
                # get rid of </a>, we can't do anything with the plain because it
                # is linked in an <a> already
                #while not tag.endswith("</a>"):
                while len([st for st in stop_set if tag.endswith(st)]) == 0:
                    tag += plain
                    tag += s.until(">")
                    plain = s.to("<")

        # pick up any stragglers
        yield tag, plain


class HTMLStripper(BaseHTMLParser):
    """strip html tags and return plaintext data

    Moved from bang.utils on 1-6-2023, I think it would be better to use HTMLCleaner
    though, I'll leave this in for a little while. This actually still has a place
    because it supports remove_tags, at some point remove_tags should be integrated
    into HTMLCleaner and then this can be removed

    https://docs.python.org/3/library/html.parser.html
    http://stackoverflow.com/a/925630/5006
    """
    @classmethod
    def strip_tags(cls, html, remove_tags=None):
        s = cls(html, remove_tags)
        return s.get_data()

    def __init__(self, html="", remove_tags=None):
        #self.reset()
        if is_py2:
            HTMLParser.__init__(self)
        else:
            super(HTMLStripper, self).__init__()

        self.fed = []
        self.removed = Counter()
        self.remove_tags = set(remove_tags or [])

        if html:
            self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag in self.remove_tags:
            if tag not in self.removed:
                self.removed[tag] = 0

        # really basic css selector support
        for k, v in attrs:
            if k == "class":
                if "{}.{}".format(tag, v) in self.remove_tags:
                    self.removed[tag] = 0

            if k == "id":
                if "{}#{}".format(tag, v) in self.remove_tags:
                    self.removed[tag] = 0

        if tag in self.removed:
            self.removed[tag] += 1

    def handle_data(self, d):
        if sum(self.removed.values()) == 0:
            self.fed.append(d)

    def handle_endtag(self, tag):
        if sum(self.removed.values()) > 0:
            if tag in self.removed:
                self.removed[tag] -= 1
                if self.removed[tag] <= 0:
                    del self.removed[tag]

    def get_data(self):
        return ''.join(self.fed)

