# -*- coding: utf-8 -*-
import re
import inspect
from socket import gethostname
import os

from .compat import *
from .string import String, ByteString, NormalizeString
from .token import StopWordTokenizer


class Url(String):
    r"""A url string on steroids, this is here to make it easy to manipulate
    urls.

    It tries to map the supported fields to their urlparse equivalents, with
    some additions

    https://en.wikipedia.org/wiki/URL
    https://tools.ietf.org/html/rfc3986.html

        A URI can be further classified as a locator, a name, or both.  The
        term "Uniform Resource Locator" (URL) refers to the subset of URIs
        that, in addition to identifying a resource, provide a means of
        locating the resource by describing its primary access mechanism
        (e.g., its network "location").

        foo://example.com:8042/over/there?name=ferret#nose
        \_/   \______________/\_________/ \_________/ \__/
         |           |            |            |        |
        scheme     authority       path        query   fragment

    Given a url: 

        http://user:pass@foo.com:1000/bar/che?baz=boom#anchor

    .scheme = http
    .netloc = user:pass@foo.com:1000
    .authority = user:pass@foo.com:1000
    .username = user
    .password = pass
    .userinfo = user:pass
    .hostloc = foo.com:1000
    .hostname = foo.com
    .port = 1000
    .path = bar/che
    .fragment = anchor
    .anchor = anchor
    .uri = /bar/che?baz=boom#anchor
    .host(...) = http://foo.com/...
    .base(...) = http://user:pass@foo.com/bar/che/...
    """
    scheme = ""
    """The http scheme (eg, "http" or "https")

    By default this class won't set a scheme except when it can be "correctly"
    inferred. But a child class could set the scheme to a default value and
    then it will fallback to the set default

    :example:
        u = Url("//example.com")
        u.scheme # "" because the // says the scheme wasn't wanted
        u = Url("example.com:80")
        u.scheme # "http" because a host was passed in with the plain port
    """

    username = None

    password = None

    hostname = ""

    port = None

    netloc = ""

    path = ""

    query_kwargs = {}

    fragment = ""

    @property
    def root(self):
        """just return scheme://netloc"""
        if netloc := self.netloc:
            ret = parse.urlunsplit((
                self.scheme,
                self.netloc,
                "",
                "",
                ""
            ))

        else:
            if self.scheme.startswith("http"):
                ret = ""

            else:
                ret = self.scheme

        return ret

    @property
    def anchor(self):
        """alternative name for fragment"""
        return self.fragment

    @property
    def authority(self):
        """This is the official RFC name for netloc"""
        return self.netloc

    @property
    def userinfo(self):
        """The Wikipedia name for the user information before the @

        https://en.wikipedia.org/wiki/Uniform_Resource_Identifier#Syntax

        :returns: str, a string containing <USERNAME>:<PASSWORD>
        """
        username = self.username or ""
        password = self.password or ""
        return f"{username}:{password}"

    @property
    def absolute(self):
        """return the absolute URI, which is everything but base (no scheme,
        host, etc). It's basically the path onwards
        """
        uristring = self.path
        if self.query:
            uristring += "?{}".format(self.query)
        if self.fragment:
            uristring += "#{}".format(self.fragment)

        return uristring

    @property
    def paths(self):
        """Returns the list of breadcrumbs for path, similar to path.Path.paths

        Moved from bang.utils.Url on 1-6-2023

        :returns: list, so if path was /foo/bar/che this would return
            [/foo, /foo/bar, /foo/bar/che]
        """
        ret = []
        paths = self.parts

        for x in range(1, len(paths) + 1):
            ret.append("/" + "/".join(paths[0:x]))

        return ret

    @property
    def parts(self):
        """Return a list of the path parts, similar to path.Path.parts"""
        path = self.path.strip("/")
        return path.split("/") if path else []

    @property
    def ext(self):
        """return the extension of the file, the basename without the fileroot

        Moved from bang.utils.Url.ext on 1-10-2023
        """
        return os.path.splitext(self.basename)[1].lstrip(".")

    @property
    def extension(self):
        return self.ext

    @property
    def basename(self):
        """Returns the basename of the path portion of the url

        Moved from bang.utils.Url.ext on 1-10-2023
        """
        return os.path.basename(self.path)

    @classmethod
    def keys(cls):
        # we need to ignore property objects also
        def is_valid(k, v):
            return not k.startswith("_") \
                and not callable(v) \
                and not isinstance(v, property) \
                and not k.isupper()

        keys = set(k for k, v in inspect.getmembers(cls) if is_valid(k, v))
        return keys

    @classmethod
    def default_values(cls):
        """Return the default values for the defined keys in the class

        :returns: dict, the key is the default class variable name and the value
            is the value it is set to
        """
        values = {}
        for k in cls.keys():
            v = getattr(cls, k)
            if isinstance(v, dict):
                values[k] = dict(v)

            elif isinstance(v, list):
                values[k] = list(v)

            else:
                values[k] = v

        return values

    @classmethod
    def merge(cls, urlstring="", *args, **kwargs):
        # we handle port before any other because the port of host:port in
        # hostname takes precedence the port on the host would take precedence
        # because proxies mean that the host can be something:10000 and the
        # port could be 9000 because 10000 is being proxied to 9000 on the
        # machine, but we want to automatically account for things like that
        # and then if custom behavior is needed then this method can be
        # overridden
        parts = cls.default_values()

        # we're going to remove our default scheme so we can make sure we set
        # everything up correctly using passed in data, we'll add it back after
        # we've got everything we needed
        default_scheme = parts.pop("scheme", "")

        if urlstring:
            properties = [
                "scheme", # 0
                "netloc", # 1
                "path", # 2
                "query", # 3
                "fragment", # 4
                "username",
                "password",
                "hostname",
                "port",
            ]

            has_host = is_url = False

            if is_url := cls.is_url(urlstring):
                o = parse.urlsplit(String(urlstring))

            else:
                s = String(urlstring)
                part = s.split("/", maxsplit=1)[0]
                has_host = "." in part or ":" in part \
                    or part.lower().startswith("localhost") \
                    or part.startswith("127.0.0.1")

                if has_host:
                    # if we don't have a url but it looks like we have a host
                    # so let's make it a url by putting // in front of it so it
                    # will still parse correctly
                    s = "//{}".format(String(urlstring))

                o = parse.urlsplit(s)

            for k in properties:
                v = getattr(o, k)
                if v:
                    parts[k] = v

            if is_url:
                parts["scheme"] = getattr(o, "scheme")

            query = parts.get("query", "")
            if query:
                parts["query_kwargs"].update(cls.parse_query(query))

        query = kwargs.pop("query", "")
        if query:
            parts["query_kwargs"].update(cls.parse_query(query))

        query_kwargs = kwargs.pop("query_kwargs", {})
        if query_kwargs:
            parts["query_kwargs"].update(query_kwargs)

        parts["query"] = ""
        if parts["query_kwargs"]:
            parts["query"] = cls.unparse_query(parts["query_kwargs"])

        ports = kwargs.pop("ports", {
            "": 80,
            "http": 80,
            "https": 443,
        })

        for k, v in kwargs.items():
            parts[k] = v

        domain, port = cls.split_hostname_from_port(parts["hostname"])
        parts["hostname"] = domain
        if port:
            parts["port"] = kwargs.get("port", port)

        if not parts.get("port", None):
            if "default_port" in kwargs:
                parts["port"] = kwargs["default_port"]

            else:
                parts["port"] = ports.get(
                    parts.get("scheme", default_scheme),
                    None
                )

        # make sure port is an int
        if parts["port"]:
            parts["port"] = int(parts["port"])

        hostloc = parts["hostname"]
        port = parts["port"]
        # we don't want common ports to be a part of a .geturl() call, but we
        # do want .port to return them
        if port and port not in set(ports.values()):
            hostloc = '{}:{}'.format(hostloc, port)
        parts["hostloc"] = hostloc

        parts["netloc"] = parts["hostloc"]
        username = kwargs.get("username", parts["username"])
        password = kwargs.get("password", parts["password"])
        if username:
            parts["netloc"] = "{}:{}@{}".format(
                username or "",
                password or "",
                parts["hostloc"]
            )

        parts["path"] = "/".join(cls.normalize_paths(parts["path"], *args))
        # compensate for "/" being the first path part
        if parts["path"].startswith("//"):
            parts["path"] = parts["path"][1:]

        if parts["path"]:
            if parts["hostname"]:
                # if path exists than we want to make sure it has a starting /
                # if a hostname exists also, user could've passed in a relative
                # path but we'll need to assume it is absolute since host
                # exists
                if not parts["path"].startswith("/"):
                    parts["path"] = "/" + parts["path"]

            else:
                if not parts.get("scheme", ""):
                    parts["scheme"] = ""

        # let's add our default scheme now that we've generated everything
        # we needed with the passed in values
        if "scheme" not in parts:
            if default_scheme:
                parts.setdefault("scheme", default_scheme)

            else:
                if parts.get("hostloc", ""):
                    if parts.get("port", None) == 443:
                        parts.setdefault("scheme", "https")

                    else:
                        parts.setdefault("scheme", "http")

        if not parts.get("scheme", ""):
            parts["scheme"] = ""

        parts["urlstring"] = parse.urlunsplit((
            parts["scheme"],
            parts["netloc"],
            parts["path"],
            parts["query"],
            parts["fragment"],
        ))

        for k in parts:
            if isinstance(parts[k], bytes):
                parts[k] = String(parts[k])

        return parts

    @classmethod
    def parse_query(cls, query):
        """return name=val&name2=val2 strings into {name: val} dict"""
        if not query:
            return {}

        if isinstance(query, bytes):
            query = String(query)

        try:
            # https://docs.python.org/2/library/urlparse.html
            query_kwargs = parse.parse_qs(query, True, strict_parsing=True)

        except ValueError:
            # try and parse the query manually, this will allow boolean values
            # (arguments with no value)
            query_kwargs = {}
            for part in query.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                else:
                    k = part
                    v = "True"
                query_kwargs.setdefault(k, [])
                query_kwargs[k].append(v)

        return cls.normalize_query_kwargs(query_kwargs)

    @classmethod
    def normalize_query_kwargs(cls, query_kwargs):
        d = {}
        # https://docs.python.org/2/library/urlparse.html
        for k, kv in query_kwargs.items():
            #k = k.rstrip("[]") # strip out php type array designated variables
            if isinstance(k, bytes):
                k = String(k)

            if len(kv) > 1:
                d[k] = kv

            else:
                d[k] = kv[0]

        return d

    @classmethod
    def unparse_query(cls, query_kwargs):
        """Given query kwargs in a dict format, convert them back into a string

        This will encode [] in the name as discussed in:
            https://stackoverflow.com/a/39294315/5006
            https://github.com/ljharb/qs/issues/235

        Luckily, it seems most servers will transparently handle encoded [] in 
        variable names

        :param query_kwargs: dict, eg {"foo": "bar", "che": 1}
        :returns: str, foo=bar&che=1
        """
        return urlencode(query_kwargs, doseq=True)

    @classmethod
    def normalize_paths(cls, *paths):
        """turns a bunch of paths into something that can be concatenated
        without any issues

        :param *parts: str|list, things like "/foo/bar" or ["foo", "bar/che"]
        :returns: list, a list of normalized parts with most of the "/" stripped
            out, the exception is if the path is absolute then the first part
            will be "/", so "/foo/bar" -> ["/", "foo", "bar"]
        """
        args = []
        for ps in paths:
            if not ps:
                continue
            if ps == ".":
                continue

            if isinstance(ps, int):
                args.append(String(ps))

            elif isinstance(ps, basestring):
                if not args and ps.startswith("/"):
                    args.append("/")
                    ps.lstrip("/")

                args.extend(filter(None, ps.split("/")))

            else:
                for p in ps:
                    nps = cls.normalize_paths(p)
                    if nps:
                        if args and nps[0] == "/":
                            args.extend(nps[1:])
                        else:
                            args.extend(nps)
        return args

    @classmethod
    def split_hostname_from_port(cls, hostname, default_port=None):
        """given a hostname:port return a tuple (hostname, port)"""
        bits = hostname.split(":", 2)
        p = int(default_port) if default_port else default_port
        d = bits[0]
        if len(bits) == 2:
            p = int(bits[1])
        return d, p

    @classmethod
    def is_full_url(cls, urlstring):
        """Return True if urlstring is a url"""
        return True if re.match(r"^\S+://", urlstring) else False

    @classmethod
    def is_relative_url(cls, urlstring):
        """Return True if urlstring is a relative url (does not have a scheme
        but instead starts with //)
        """
        return urlstring.startswith("//")

    @classmethod
    def is_path_url(cls, urlstring):
        """Return true if this is a path url (url that doesn't have a host)

        a path url: /foo/bar
        """
        return True if re.match(r"^/[^/]", urlstring) else False

    @classmethod
    def is_url(cls, urlstring):
        """Returns True if urlstring is an actual full or relative url

        Moved from bang.utils.Url.match on 1-10-2023
        """
        # REGEX = re.compile(r"^(?:https?:\/\/|\/\/)", re.I)
        return cls.is_full_url(urlstring) or cls.is_relative_url(urlstring)

    @classmethod
    def create_instance(cls, *args, **kwargs):
        #return type(self)(*args, **kwargs)
        return Url(*args, **kwargs)

    def __new__(cls, urlstring=None, *args, **kwargs):
        parts = cls.merge(urlstring, *args, **kwargs)
        urlstring = parts.pop("urlstring")
        instance = super().__new__(cls, urlstring)
        for k, v in parts.items():
            setattr(instance, k, v)
        return instance

    def create(self, *args, **kwargs):
        return self.create_instance(*args, **kwargs)

    def add(self, **kwargs):
        """Just a shortcut to change the current url, equivalent to
        Url(self, **kwargs)
        """
        if "path" in kwargs:
            path = kwargs["path"]
            if isinstance(path, bytes):
                path = String(path)
            if not path[0].startswith("/"):
                paths = self.normalize_paths(self.path, path)
            else:
                paths = self.normalize_paths(path)
            kwargs["path"] = "/".join(paths)
        return self.create(self, **kwargs)

    def subtract(self, *paths, **kwargs):
        sub_kwargs = self.jsonable()

        path2 = self.normalize_paths(paths)
        path2.extend(self.normalize_paths(kwargs.pop("path", "")))
        if path2:
            sub_path = self.normalize_paths(self.path)
            for p in path2:
                try:
                    sub_path.remove(p)
                except ValueError:
                    pass

            sub_kwargs["path"] = sub_path

        for k, v in kwargs.items():
            if k == "query_kwargs":
                for qk, qv in kwargs[k].items():
                    if str(sub_kwargs[k][qk]) == str(qv):
                        sub_kwargs[k].pop(qk)

            else:
                if str(sub_kwargs[k]) == str(v):
                    sub_kwargs.pop(k)

        return self.create(**sub_kwargs)

    def _normalize_params(self, *paths, **query_kwargs):
        """a lot of the helper methods are very similar, this handles their
        arguments"""
        kwargs = {}

        if paths:
            fragment = String(paths[-1])
            if fragment:
                if fragment.startswith("#"):
                    kwargs["fragment"] = fragment
                    paths.pop(-1)

            kwargs["path"] = "/".join(self.normalize_paths(*paths))

        kwargs["query_kwargs"] = query_kwargs
        return kwargs

    def parent(self, *paths, **query_kwargs):
        """create a new Url instance one level up from the current Url instance

        so if self contains /foo/bar then self.parent() would return /foo

        :param *paths: list, the paths to append to the parent path
        :param **query_kwargs: dict, any query string params to add
        :returns: new Url instance
        """
        kwargs = self._normalize_params(*paths, **query_kwargs)
        path_args = self.path.split("/")
        if path_args:
            urlstring = self.subtract(path_args[-1])
        else:
            urlstring = self

        return urlstring.add(**kwargs)

    def base(self, *paths, **query_kwargs):
        """create a new url object using the current base path as a base

        if you had requested /foo/bar, then this would append *paths and
        **query_kwargs to /foo/bar

        :example:
            # current path: /foo/bar

            print url # http://host.com/foo/bar

            print url.base() # http://host.com/foo/bar
            print url.base("che", boom="bam") # http://host/foo/bar/che?boom=bam

        :param *paths: list, the paths to append to the current path without
            query params
        :param **query_kwargs: dict, any query string params to add
        """
        kwargs = self._normalize_params(*paths, **query_kwargs)
        if self.path:
            if "path" in kwargs:
                paths = self.normalize_paths(self.path, kwargs["path"])
                kwargs["path"] = "/".join(paths)
            else:
                kwargs["path"] = self.path
        return self.create(self.root, **kwargs)

    def host(self, *paths, **query_kwargs):
        """create a new url object using the host as a base

        if you had requested http://host/foo/bar, then this would append *paths
        and **query_kwargs to http://host

        :example:
            # current url: http://host/foo/bar

            print(url) # http://host.com/foo/bar

            print(url.host()) # http://host.com/
            print(url.host("che", boom="bam")) # http://host/che?boom=bam

        :param *paths: list, the path parts to append to the current host
        :param **query_kwargs: dict, any query string params to add
        """
        kwargs = self._normalize_params(*paths, **query_kwargs)

        # because path is from host then it is automatically absolute
        if "path" in kwargs and not kwargs["path"].startswith("/"):
            kwargs["path"] = "/" + kwargs["path"]

        return self.create(self.root, **kwargs)

    def child(self, *paths, **kwargs):
        """Layers paths and kwargs on top of self, using passed in values to
        replace anything in self

        :Example:
            u = Url("foo", 1)
            print(u) # foo/1

            u2 = u.child("bar", 2)
            print(u2) # foo/1/bar/2

            u3 = u.child(path=["bar", 2])
            print(u2) # bar/2

        :param *paths: url path parts
        :param **kwargs: same kwargs that can be passed into creation
        :returns: a new instance of this class
        """
        return self.create(self, *paths, **kwargs)

    def jsonable(self):
        return dict(
            scheme=self.scheme,
            username=self.username,
            password=self.password,
            hostname=self.hostname,
            port=self.port,
            path=self.path,
            query_kwargs=self.query_kwargs,
            fragment=self.fragment,
        )

    def copy(self):
        return self.__deepcopy__()

    def __copy__(self):
        return self.__deepcopy__()

    def __deepcopy__(self, memodict={}):
        return self.create(**self.jsonable())
#             scheme=self.scheme,
#             username=self.username,
#             password=self.password,
#             hostname=self.hostname,
#             port=self.port,
#             path=self.path,
#             query_kwargs=self.query_kwargs,
#             fragment=self.fragment,
#         )

    def __add__(self, other):
        ret = ""
        if isinstance(other, Mapping):
            ret = self.add(query_kwargs=other)

        elif isinstance(other, MutableSequence):
            ret = self.add(path=other)

        elif isinstance(other, basestring):
            ret = self.add(path=other)

        elif isinstance(other, Sequence):
            ret = self.add(path=other)

        else:
            raise ValueError("Not sure how to add {}".format(type(other)))

        return ret
    __iadd__ = __add__

    def __truediv__(self, other):
        ret = ""
        if isinstance(other, MutableSequence):
            ret = self.add(path=other)

        elif isinstance(other, basestring):
            ret = self.add(path=other)

        elif isinstance(other, Sequence):
            ret = self.add(path=other)

        else:
            raise ValueError("Not sure how to add {}".format(type(other)))

        return ret
    __itruediv__ = __truediv__

    def __sub__(self, other):
        """Return a new url with other removed"""
        ret = ""
        if isinstance(other, Mapping):
            ret = self.subtract(query_kwargs=other)

        elif isinstance(other, MutableSequence):
            ret = self.subtract(path=other)

        elif isinstance(other, basestring):
            ret = self.subtract(path=other)

        elif isinstance(other, Sequence):
            ret = self.subtract(path=other)

        else:
            raise ValueError("Not sure how to add {}".format(type(other)))

        return ret
    __isub__ = __sub__

    def jsonable(self):
        ret = {}
        for k in self.keys():
            v = getattr(self, k)
            if k == "query_kwargs":
                ret[k] = dict(v)
            else:
                ret[k] = v

        return ret

    def has_hostname(self):
        """Return True if this url has a host"""
        return True if self.hostname else False

    def is_hostname(self, hostname):
        """return true if the url's host matches host"""
        ret = False
        if not self.has_hostname() and not hostname:
            ret = True
        else:
            ret = self.hostname.lower() == hostname.lower()
        return ret

    def is_relative(self):
        """return True if this url is a path or relative url

        a relative url: //hostname.tld/foo/bar
        """
        return self.is_relative_url(self)

    def is_full(self):
        """return True if this url is a path or relative url

        a full url: scheme//hostname.tld/foo/bar
        """
        return self.is_full_url(self)

    def is_path(self):
        """Return true if this is a path url (url that doesn't have a host)

        a path url: /foo/bar
        """
        return self.is_path_url(self)

    def is_local(self):
        """return True if is a localhost url"""
        return (
            self.is_path()
            or self.is_hostname("localhost")
            or self.is_hostname("127.0.0.1")
        )

    def unsplit(self):
        """By default, the URL won't contain a scheme if it wasn't passed in,
        this will add the default scheme and return the url"""
        return parse.urlunsplit((
            self.scheme,
            self.netloc,
            self.path,
            self.query,
            self.fragment,
        ))

    def full(self):
        """alias of .unsplit()"""
        return self.unsplit()
Urlstring = Url
UrlString = Url


class Host(tuple):
    """Creates a tuple (hostname, port) that can be passed to built-in Python
    server classes and anything that uses that same interface, does all the
    lifting to figure out what the hostname and port should be based on the
    passed in input, so you can pass things like hostname:port, or (host,
    port), etc.

    https://docs.python.org/3/library/socket.html#module-socket - creates an
    AF_INET server address
    """
    @property
    def hostname(self):
        """Return just the hostname with no port or scheme or anything

        :returns: string
        """
        return self[0]

    @property
    def port(self):
        """return just the port

        :returns: int
        """
        return self[1]

    @property
    def hostloc(self):
        """Returns hostname:port

        :returns: string
        """
        return self.url.hostloc

    def __new__(cls, host="", port=None):
        """Create a new server_address tuple

        If nothing is passed in the default address is ("", 0) which in most
        python stdlib server code will bind to localhost with some random
        free port

        :param host: str|tuple[str, int|str], can handle things strings like
            ":<PORT>", "<HOSTNAME>:<PORT>", "<HOSTNAME>", or
            ["<HOSTNAME>", "<PORT>"]
        :param port: int
        """
        if isinstance(host, tuple):
            # compensate for passing in a server_address tuple which I seem
            # to do a lot evidently
            port = host[1]
            host = host[0]

        if host.startswith(":"):
            # host is just a port like ":8000"
            port = host[1:]
            host = ""

        u = Url(host, default_port=port)

        port = u.port
        if not port:
            # If the port is empty we set it to 0 so it can trigger python's
            # internal server code to find an available port. If we didn't do
            # this we would get the error: TypeError: 'NoneType' object cannot
            # be interpreted as an integer
            port = 0

        instance = super().__new__(cls, [u.hostname, port])
        instance.url = u
        return instance

    def __str__(self):
        return self.hostloc

    def __bytes__(self):
        return ByteString(self.hostloc)

    def full(self):
        return self.url.full()

    def client(self):
        """Url can technically hold a hostname like 0.0.0.0, this will
        compensate for that, useful for test clients

        :returns: str, a netloc (eg "host:port") that a client can use to make
        a request
        """
        domain, port = self

        netloc = domain

        if domain == "0.0.0.0":
            netloc = gethostname()

        elif not domain:
            netloc = "127.0.0.1"

        if port:
            netloc += ":{}".format(port)

        return netloc


class SlugWords(StopWordTokenizer):
    """Internal class used by Slug to find all the valid slug words"""

    NON_ASCII_REGEX = re.compile(r'[^\x00-\x7F]+')
    """non-ascii characters

    https://stackoverflow.com/a/2759009/5006
    """

    def normalize(self, token):
        word = token.text
        word = self.NON_ASCII_REGEX.sub("", word)
        return word.lower()

    def is_valid(self, word):
        return word and (word not in self.STOP_WORDS)


class Slug(NormalizeString):
    """Given a string, convert it into a slug that can be used in a url path

    This tokenizes the passed in string, strips non-ascii, punctuation, and stop
    words and then returns the remaining words joined by delim (default is a
    hyphen)
    """
    @classmethod
    def before_create(cls, val, **kwargs):
        """
        :param val: str, the prospective slug
        :param **kwargs:
            * delim: str, default is a hyphen
            * size: int, the max size you want the slug
        """
        delim = kwargs.get("delim", "-")
        words = SlugWords(val)
        slug = delim.join(words)
        if size := kwargs.get("size", 0):
            slug = String(slug).truncate(size, sep=delim)
        return slug

