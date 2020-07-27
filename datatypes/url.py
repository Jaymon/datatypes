# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import re
import inspect
from socket import gethostname

from .compat import *
from .string import String, ByteString
from .path import Cachepath, Path


class Url(String):
    """a url object on steroids, this is here to make it easy to manipulate urls
    we try to map the supported fields to their urlparse equivalents, with some additions

    https://tools.ietf.org/html/rfc3986.html

    given a url http://user:pass@foo.com:1000/bar/che?baz=boom#anchor

    .scheme = http
    .netloc = user:pass@foo.com:1000
    .hostloc = foo.com:1000
    .hostname = foo.com
    .host() = http://foo.com
    .port = 1000
    .base = http://user:pass@foo.com:1000/bar/che
    .fragment = anchor
    .anchor = fragment
    .uri = /bar/che?baz=boom#anchor
    .host(...) = http://foo.com/...
    .base(...) = http://foo.com/bar/che/...
    """
    scheme = "http"

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
        return parse.urlunsplit((
            self.scheme,
            self.netloc,
            "",
            "",
            ""
        ))

    @property
    def anchor(self):
        """alternative name for fragment"""
        return self.fragment

    @property
    def uri(self):
        """return the uri, which is everything but base (no scheme, host, etc)"""
        uristring = self.path
        if self.query:
            uristring += "?{}".format(self.query)
        if self.fragment:
            uristring += "#{}".format(self.fragment)

        return uristring

    @classmethod
    def keys(cls):
        # we need to ignore property objects also
        is_valid = lambda k, v: not k.startswith("__") and not callable(v) and not isinstance(v, property)
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
    def merge(cls, urlstring="", **kwargs):
        # we handle port before any other because the port of host:port in hostname takes precedence
        # the port on the host would take precedence because proxies mean that the
        # host can be something:10000 and the port could be 9000 because 10000 is
        # being proxied to 9000 on the machine, but we want to automatically account
        # for things like that and then if custom behavior is needed then this method
        # can be overridden
        parts = cls.default_values()
#         parts = {
#             "hostname": cls.hostname,
#             "port": cls.port,
#             "query_kwargs": dict(cls.query_kwargs),
#             "scheme": cls.scheme,
#             "netloc": cls.netloc,
#             "path": cls.path,
#             "fragment": cls.fragment,
#             "username": cls.username,
#             "password": cls.password,
#         }

        if urlstring:
            properties = [
                "scheme", # 0
                "netloc", # 1
                "path", # 2
                "fragment", # 5
                "username",
                "password",
                "hostname",
                "port",
                "query", # 4
            ]

            if re.match(r"^\S+://", urlstring) or urlstring.startswith("//"):
                o = parse.urlsplit(String(urlstring))

            else:
                # if we don't have a scheme we put // in front of it so it will
                # still parse correctly
                s = "//{}".format(String(urlstring))
                o = parse.urlsplit(s)

            for k in properties:
                v = getattr(o, k)
                if v:
                    parts[k] = v

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

        for k, v in kwargs.items():
            parts[k] = v

        ports = {
            "http": 80,
            "https": 443,
        }
        domain, port = cls.split_hostname_from_port(parts["hostname"])
        parts["hostname"] = domain
        if port:
            parts["port"] = kwargs.get("port", port)

        if not parts.get("port", None):
            if "default_port" in kwargs:
                parts["port"] = kwargs["default_port"]
            else:
                parts["port"] = ports.get(parts["scheme"], None)

        # make sure port is an int
        if parts["port"]:
            parts["port"] = int(parts["port"])

        hostloc = parts["hostname"]
        port = parts["port"]
        # we don't want common ports to be a part of a .geturl() call, but we do
        # want .port to return them
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

        parts["path"] = "/".join(cls.normalize_paths(parts["path"]))

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
        if not query: return {}

        if isinstance(query, bytes):
            query = String(query)

        # https://docs.python.org/2/library/urlparse.html
        query_kwargs = parse.parse_qs(query, True, strict_parsing=True)
        return cls.normalize_query_kwargs(query_kwargs)

    @classmethod
    def normalize_query_kwargs(cls, query):
        d = {}
        # https://docs.python.org/2/library/urlparse.html
        for k, kv in query.items():
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
        return urlencode(query_kwargs, doseq=True)

    @classmethod
    def normalize_paths(cls, *paths):
        args = []
        for ps in paths:
            if isinstance(ps, basestring):
                args.extend(filter(None, ps.split("/")))
                #args.append(ps.strip("/"))
            else:
                for p in ps:
                    args.extend(cls.normalize_paths(p))
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

    def __new__(cls, urlstring=None, **kwargs):
        parts = cls.merge(urlstring, **kwargs)
        urlstring = parts.pop("urlstring")
        instance = super(Url, cls).__new__(cls, urlstring)
        for k, v in parts.items():
            setattr(instance, k, v)
        return instance

    def create(self, *args, **kwargs):
        return type(self)(*args, **kwargs)

    def add(self, **kwargs):
        """Just a shortcut to change the current url, equivalent to Url(self, **kwargs)"""
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
        """a lot of the helper methods are very similar, this handles their arguments"""
        kwargs = {}

        if paths:
            fragment = paths[-1]
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

        if you had requested /foo/bar, then this would append *paths and **query_kwargs
        to /foo/bar

        :example:
            # current path: /foo/bar

            print url # http://host.com/foo/bar

            print url.base() # http://host.com/foo/bar
            print url.base("che", boom="bam") # http://host/foo/bar/che?boom=bam

        :param *paths: list, the paths to append to the current path without query params
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

        if you had requested http://host/foo/bar, then this would append *paths and **query_kwargs
        to http://host

        :example:
            # current url: http://host/foo/bar

            print url # http://host.com/foo/bar

            print url.host() # http://host.com/
            print url.host("che", boom="bam") # http://host/che?boom=bam

        :param *paths: list, the paths to append to the current path without query params
        :param **query_kwargs: dict, any query string params to add
        """
        kwargs = self._normalize_params(*paths, **query_kwargs)
        return self.create(self.root, **kwargs)

    def copy(self):
        return self.__deepcopy__()

    def __copy__(self):
        return self.__deepcopy__()

    def __deepcopy__(self, memodict={}):
        return self.create(
            scheme=self.scheme,
            username=self.username,
            password=self.password,
            hostname=self.hostname,
            port=self.port,
            path=self.path,
            query_kwargs=self.query_kwargs,
            fragment=self.fragment,
        )

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


class Host(tuple):
    """Creates a tuple (hostname, port) that can be passed to built-in PYthon server
    classes and anything that uses that same interface, does all the lifting to
    figure out what the hostname and port should be based on the passed in input,
    so you can pass things like hostname:port, or (host, port), etc.
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
        return "{}:{}".format(self.hostname, self.port)
    netloc = hostloc

    def __new__(cls, host, port=None):
        u = Url(host, default_port=port)
        return super(Host, cls).__new__(cls, [u.hostname, u.port if u.port else 0])

    def __str__(self):
        return self.__bytes__() if is_py2 else self.__unicode__()

    def __unicode__(self):
        return String(self.hostloc)

    def __bytes__(self):
        return ByteString(self.hostloc)

    def client(self):
        """Url can technically hold a hostname like 0.0.0.0, this will compensate
        for that, useful for test clients

        :returns: a netloc (host:port) that a client can use to make a request
        """
        netloc = ""
        domain, port = self
        netloc = gethostname() if domain == "0.0.0.0" else domain
        if port:
            netloc += ":{}".format(port)
        return netloc



class Urlpath(Cachepath):

    def __new__(cls, url, path="", **kwargs):
        # TODO -- pass in client? I should move testdata.client.HTTP (and really
        # all of testdata.client into .client.py module

        keys = []
        if path:
            path = Path.create_file(path)
            kwargs.setdefault("dir", path.parent)
            keys.append(path.basename)

        instance = super(Urlpath, cls).__new__(cls, *keys, **kwargs)
        instance.url = url
        return instance


    def read(self):
        raise NotImplementedError()
        # TODO -- if the file doesn't exist fetch it then read
        pass

    def read_text(self):
        raise NotImplementedError()
        # TODO -- if the file doesn't exist fetch it then read
        pass

    def read_bytes(self):
        raise NotImplementedError()
        # TODO -- if the file doesn't exist fetch it then read
        pass

