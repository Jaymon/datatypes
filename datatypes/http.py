# -*- coding: utf-8 -*-
from wsgiref.headers import Headers as BaseHeaders
import itertools
import base64
import socket
import re
import json
import email.message
import platform

from .compat import *
from .copy import Deepcopy
from .string import String, ByteString, NormalizeString
from .config.environ import environ


class HTTPHeaders(BaseHeaders, Mapping):
    """handles headers, see wsgiref.Headers link for method and use information

    Handles normalizing of header names, the problem with headers is they can
    be in many different forms and cases and stuff (eg, CONTENT_TYPE and
    Content-Type), so this handles normalizing the header names so you can
    request Content-Type or CONTENT_TYPE and get the same value.

    This has the same interface as Python's built-in wsgiref.Headers class but
    makes it even more dict-like and will return titled header names when
    iterated or anything (eg, Content-Type instead of all lowercase
    content-type)

    http headers spec:
        https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html

    wsgiref class docs:
        https://docs.python.org/2/library/wsgiref.html#module-wsgiref.headers
        https://hg.python.org/cpython/file/2.7/Lib/wsgiref/headers.py
    actual python3 code:
        https://github.com/python/cpython/blob/master/Lib/wsgiref/headers.py
    """
    encoding = "iso-8859-1"
    """From rfc2616:
        The default language is English and the default character set is
        ISO-8859-1.

        If a character set other than ISO-8859-1 is used, it MUST be encoded in
        the warn-text using the method described in RFC 2047
    """

    def __init__(self, headers=None, **kwargs):
        super().__init__([])
        self.update(headers, **kwargs)

    def _convert_string_part(self, bit):
        """each part of a header will go through this method, this allows
        further normalization of each part, so a header like FOO_BAR would call
        this method twice, once with foo and again with bar

        this is called train case or http-header case

        https://stackoverflow.com/questions/17326185/what-are-the-different-kinds-of-cases

        this method doesn't normalize all the non-standard header bits, for
        example, this would mess up ETag, HTTP2, WWW, DNT, ATT, ID, etc

        https://en.wikipedia.org/wiki/List_of_HTTP_header_fields

        :param bit: string, a part of a header all lowercase
        :returns: string, the normalized bit
        """
        if bit == "websocket":
            bit = "WebSocket"

        else:
            bit = bit.title()

        return bit

    def _convert_string_name(self, k):
        """converts things like FOO_BAR to Foo-Bar which is the normal form"""
        k = String(k, self.encoding)
        bits = k.lower().replace('_', '-').split('-')
        return "-".join((self._convert_string_part(bit) for bit in bits))

    def _convert_string_type(self, v):
        """Override the internal method wsgiref.headers.Headers uses to check
        values to make sure they are strings
        """
        # wsgiref.headers.Headers expects a str() (py3) or unicode (py2), it
        # does not accept even a child of str, so we need to convert the String
        # instance to the actual str, as does the python wsgi methods, so even
        # though we override this method we still return raw() strings so we get
        # passed all the type(v) == "str" checks
        # sadly, this method is missing in 2.7
        # https://github.com/python/cpython/blob/2.7/Lib/wsgiref/headers.py
        return String(v).raw()

    def get_all(self, name):
        """Get all the values for name

        :returns: list[str], any set values for name
        """
        name = self._convert_string_name(name)
        return super().get_all(name)

    def get(self, name, default=None):
        name = self._convert_string_name(name)
        return super().get(name, default)

    def parse(self, name):
        """Parses the name header and returns main, params

        :Example:
            h = HTTPHeaders()
            h.add_header("Content-Type", 'application/json; charset="utf8"')
            main, params = h.parse("Content-Type")
            print(main) # application/json
            print(params["charset"]) # utf8

        :param name: str, the header to parse
        :returns: tuple[str, dict], returns a tuple of (main, params)
        """
        if h := self.get(name, ""):
            em = email.message.Message()
            em[name] = h
            # get_params looks to be an internal method, it's not publicly
            # documented in the official docs
            ps = em.get_params(header=name)
            main = ps[0][0]
            params = {p[0]: p[1] for p in ps[1:]}
            return main, params

        else:
            return "", {}

    def __delitem__(self, name):
        name = self._convert_string_name(name)
        return super().__delitem__(name)

    def __setitem__(self, name, val):
        name = self._convert_string_name(name)
        return super().__setitem__(name, val)

    def setdefault(self, name, val):
        name = self._convert_string_name(name)
        return super().setdefault(name, val)

    def add_header(self, name, val, **params):
        """This is additive, meaning if name already exists then another row
        will be added containing val

        :param name: str, the header name/key
        :param val: str, the header value
        :param **params: these can be added as header variables to val
        """
        name = self._convert_string_name(name)
        return super().add_header(name, val, **params)

    def set_header(self, name, val, **params):
        """This completely replaces any currently set value of name with val

        :param name: str, the header name/key
        :param val: str, the header value
        :param **params: these can be added as header variables to val
        """
        self.delete_header(name)
        self.add_header(name, val, **params)

    def delete_header(self, name):
        """Remove header name"""
        del self[name]

    def has_header(self, name):
        return name in self

    def __contains__(self, name):
        name = self._convert_string_name(name)
        return super().__contains__(name)

    def keys(self):
        return [k for k, v in self._headers]

    def asgi(self):
        """Returns each header as a tuple of byte strings with the name as all
        lowercase

        From the ASGI spec: https://asgi.readthedocs.io/en/latest/specs/www.html
            An iterable of [name, value] two-item iterables, where name is the
            header name, and value is the header value. Order must be preserved
            in the HTTP response. Header names must be lowercased.

        :returns: generator of tuple[bytes, bytes]
        """
        for k, v in self.items():
            yield ByteString(k.lower()), ByteString(v)

    def items(self):
        for k, v in self._headers:
            yield k, v

    def iteritems(self):
        return self.items()

    def iterkeys(self):
        for k in self.keys():
            yield k

    def __iter__(self):
        for k, v in self._headers:
            yield k

    def pop(self, name, *args, **kwargs):
        """remove and return the value at name if it is in the dict

        This uses *args and **kwargs instead of default because this will raise
        a KeyError if default is not supplied, and if it had a definition like
        (name, default=None) you wouldn't be able to know if default was
        provided or not

        :param name: string, the key we're looking for
        :param default: mixed, the value that would be returned if name is not
            in dict
        :returns: the value at name if it's there
        """
        val = self.get(name)
        if val is None:
            if args:
                val = args[0]

            elif "default" in kwargs:
                val = kwargs["default"]

            else:
                raise KeyError(name)

        else:
            del self[name]

        return val

    def update(self, headers=None, **kwargs):
        """This replaces headers currently in the instance with those found in
        headers. This is not additive, the value at key in headers will
        completely replace any value currently set

        :param headers: dict[str, str], the key is the name and the value is the
            value that will be set for name
        :param **kwargs: these can be name=val keywords
        """
        if not headers:
            headers = {}

        if isinstance(headers, Mapping):
            headers.update(kwargs)
            headers = headers.items()

        else:
            if kwargs:
                headers = itertools.chain(
                    headers,
                    kwargs.items()
                )

        for k, v in headers:
            self[k] = v

    def copy(self):
        return Deepcopy().copy(self)

    def tolist(self):
        """Return all the headers as a list of headers instead of a dict"""
        return [": ".join(h) for h in self.items() if h[1]]

    def is_plain(self):
        """return True if body's content-type is text/plain"""
        ct = self.get("Content-Type", "")
        return "plain" in ct

    def is_json(self):
        """return True if body's content-type is application/json"""
        ct = self.get("Content-Type", "")
        return "json" in ct

    def is_urlencoded(self):
        """return True if body's content-type is
        application/x-www-form-urlencoded"""
        ct = self.get("Content-Type", "")
        return "form-urlencoded" in ct

    def is_multipart(self):
        """return True if body's content-type is multipart/form-data"""
        ct = self.get("Content-Type", "")
        return "multipart" in ct

    def is_chunked(self):
        """Return True if this set of headers is chunked"""
        return self.get('transfer-encoding', "").lower().startswith("chunked")

    def get_user_agent(self):
        """Return the parsed user-agent string if it exists, empty string if it
        doesn't exist

        :returns: UserAgent
        """
        ua = self.get("User-Agent", "")
        if ua:
            ua = UserAgent(ua)

        return ua


class HTTPEnviron(HTTPHeaders):
    """just like Headers but allows any values (headers converts everything to
    unicode string)"""
    def _convert_string_type(self, v):
        return v


class HTTPResponse(object):
    """This is the response object that is returned from an HTTP request, it
    tries its best to look like a requests response object so you can switch
    this out when you need a more full-featured solution
    """
    @property
    def encoding(self):
        encoding = environ.ENCODING
        if "content-type" in self.headers:
            # use the email stdlib to parse out the encoding from the content type
            em = email.message.Message()
            em.add_header("content-type", self.headers["content-type"])
            encoding = em.get_content_charset()

            # https://stackoverflow.com/questions/29761905/default-encoding-of-http-post-request-with-json-body
            # https://www.rfc-editor.org/rfc/rfc7158#section-8.1
            # JSON text SHALL be encoded in UTF-8, UTF-16, or UTF-32. The
            # default encoding is UTF-8
            #
            # https://www.rfc-editor.org/rfc/rfc2616
            # HTTP when no explicit charset parameter is provided by the sender,
            # media subtypes of the "text" type are defined to have a default
            # charset value of "ISO-8859-1" when received via HTTP. (rfc2616 is
            # superceded by rfc7231, which doesn't have this default charset but
            # I'm going to keep it right now)
            if not encoding:
                if self.http.is_json(self.headers):
                    encoding = "UTF-8"
                else:
                    if self.headers["content-type"].startswith("text/"):
                        encoding = "ISO-8859-1"

        return encoding

    @property
    def cookies(self):
        # https://stackoverflow.com/questions/25387340/is-comma-a-valid-character-in-cookie-value
        # https://stackoverflow.com/questions/21522586/python-convert-set-cookies-response-to-array-of-cookies
        # https://gist.github.com/Ostrovski/c8d16ce16759eddf6664
        if "set-cookie" in self.headers:
            # for some reason SimpleCookie leaves commas in the value
            cookie_headers = self.headers.get_all("set-cookie", "")
            cs = cookies.SimpleCookie("\r\n".join(cookie_headers))
            ret = {cs[k].key:cs[k].value for k in cs}
        else:
            ret = {}
        return ret

    @property
    def content(self):
        encoding = self.encoding
        errors = environ.ENCODING_ERRORS
        return self._body.decode(encoding, errors) if encoding else self._body

    @property
    def status_code(self):
        return self.code

    @property
    def body(self):
        if self.http.is_json(self.headers):
            body = self.json()
        else:
            body = self.content
        return body

    def __init__(self, code, body, headers, http, response):
        self.http = http
        self.response = response
        self.headers = headers
        self._body = body
        self.code = code

    def json(self):
        return json.loads(self._body)

    def iter_content(self, chunk_size=0):
        content = self.content
        if chunk_size:
            start = 0
            total = len(content)
            while start < total:
                yield content[start:start + chunk_size]
                start += chunk_size

        else:
            yield content


class HTTPClient(object):
    """A Generic HTTP request client

    Because sometimes I don't want to install requests

    https://stackoverflow.com/questions/645312/what-is-the-quickest-way-to-http-get-in-python

    :Example:
        # make a simple get request
        c = HTTP("http://example.com")
        c.get("/foo/bar")

        # make a request with a cookie
        c = HTTP("http://example.com")
        c.get("/foo/bar", cookies={"foo": "1"})

        # make a request with a different method
        c = HTTP("http://example.com")
        c.fetch("PUT", "/foo/bar")

        # make a POST request
        c = HTTP("http://example.com")
        c.post("/foo/bar", {"foo": 1})

        # make a json POST request
        c = HTTP("http://example.com")
        c.post("/foo/bar", {"foo": 1}, json=True)

    moved from testdata.client.HTTP on March 4, 2022
    """
    timeout = 10

    def __init__(self, base_url="", **kwargs):
        self.base_url = base_url
        self.query = {}

        # these are the common headers that usually don't change all that much
        self.headers = HTTPHeaders(kwargs.get("headers", None))

        if kwargs.get("json", False):
            self.headers.update({
                "Content-Type": "application/json",
            })

    def get(self, uri, query=None, **kwargs):
        """make a GET request"""
        return self.fetch('get', uri, query, **kwargs)

    def post(self, uri, body=None, **kwargs):
        """make a POST request"""
        return self.fetch('post', uri, kwargs.pop("query", None), body, **kwargs)

    def __getattr__(self, key):
        def callback(*args, **kwargs):
            return self.fetch(key, *args, **kwargs)
        return callback
        #return lambda *args, **kwargs: self.fetch(key, *args, **kwargs)

    def basic_auth(self, username, password):
        """add basic auth to this client

        this will set the Authorization header so the request will use Basic auth

        link -- http://stackoverflow.com/questions/6068674/
        link -- https://docs.python.org/2/howto/urllib2.html#id6

        :param username: str
        :param password: str
        """
        credentials = Base64.encode('{}:{}'.format(username, password))
        auth_string = 'Basic {}'.format(credentials)
        #credentials = base64.b64encode('{}:{}'.format(username, password)).strip()
        #auth_string = 'Basic {}'.format(credentials())
        self.headers['Authorization'] = auth_string

    def token_auth(self, access_token):
        """add bearer TOKEN auth to this client"""
        self.headers['Authorization'] = 'Bearer {}'.format(access_token)

    def remove_auth(self):
        """Get rid of the internal Authorization header"""
        self.headers.pop('Authorization', None)

    def fetch(self, method, uri, query=None, body=None, **kwargs):
        """wrapper method that all the top level methods (get, post, etc.) use to actually
        make the request
        """
        if not query: query = {}
        fetch_url = self.get_fetch_url(uri, query)

        fetch_kwargs = {}
        fetch_kwargs["headers"] = self.get_fetch_headers(
            method,
            kwargs.get("headers", {}),
            kwargs.get("cookies", {}),
        )
        if "timeout" in kwargs:
            fetch_kwargs["timeout"] = kwargs["timeout"]

        if body:
            fetch_kwargs["data"] = self.get_fetch_body(fetch_kwargs["headers"], body)

        res = self._fetch(method, fetch_url, **fetch_kwargs)
        return res

    def _fetch(self, method, fetch_url, **kwargs):
        """Internal method called from self.fetch that performs the actual request

        If you wanted to switch out the backend to actually use requests then this
        should be the only method you would need to override

        :param method: str, the http method (eg, GET, POST)
        :param fetch_url: str, the full url requested
        :param **kwargs: mixed, any arguments to pass to the backend client
        :returns: HTTPResponse, a response instance
        """
        timeout = kwargs.pop("timeout", self.timeout)

        # this block actually performs the request
        req = self.get_fetch_request(method, fetch_url, **kwargs)
        res = self.get_fetch_response(req, timeout=timeout)

        return res

    def get_fetch_url(self, uri, query=None):
        """Combine the passed in uri and query with self.base_url to create the full
        url the request will actually request

        :param uri: str, usually like a relative path (eg /path) but can be a full
            url (eg scheme://host.ext/path)
        :param query: dict, the key/val that you want to attach to the url after the
            question mark
        :returns: str, the full url (eg scheme://host.ext/path?key=val&...)
        """
        if not isinstance(uri, basestring):
            # allow ["foo", "bar"] to be converted to "/foo/bar"
            pout.v(uri)
            uri = "/".join(uri)

        if re.match(r"^\S+://\S", uri):
            ret_url = uri

        else:
            base_url = self.base_url
            base_url = base_url.rstrip('/')

            uri = uri.lstrip('/')
            ret_url = "/".join([base_url, uri])

        query_str = ''
        if '?' in ret_url:
            i = ret_url.index('?')
            query_str = ret_url[i+1:]
            ret_url = ret_url[0:i]

        query_str = self.get_fetch_query(query_str, query)
        if query_str:
            ret_url = '{}?{}'.format(ret_url, query_str)

        return ret_url

    def get_fetch_query(self, query_str, query):
        """get the query string (eg ?key=val&...)

        :param query_str: str, a query string, if not empty then query will be 
            added onto it
        :param query: dict, key/val that will be added to query_str and returned
        :returns: str, the full query string
        """
        all_query = getattr(self, "query", {})
        if not all_query: all_query = {}
        if query:
            all_query.update(query)

        if all_query:
            more_query_str = urlencode(all_query, doseq=True)
            if query_str:
                query_str += '&{}'.format(more_query_str)
            else:
                query_str = more_query_str

        return query_str

    def get_fetch_user_agent_name(self):
        """Returns the client name that the user agent will use

        :returns: str, the client name
        """
        from . import __version__ # avoid circular dependency
        return "{}.{}/{}".format(
            self.__module__.split(".", maxsplit=1)[0],
            self.__class__.__name__,
            __version__
        )

    def get_fetch_user_agent(self):
        """create a default user agent that looks very similar to a web browser's
        user-agent string

        :returns: str, the full user agent that will be passed up to the server
            in the User-Agent header
        """
        ua = environ.USER_AGENT

        if not ua:

            osname = ""
            machine = platform.machine()
            ps = platform.system()
            if ps == "Darwin":
                osname = "Macintosh"
                if machine.startswith("x86"):
                    osname += " Intel"

                osname += " Mac OS X {}".format(platform.mac_ver()[0].replace(".", "_"))

            elif ps == "Linux":
                osname = "X11; Linux {}".format(machine)

            elif ps == "Windows":
                # TODO -- this is not fleshed out because I don't use windows
                osname = "Windows NT"
                if machine.startswith("x86"):
                    osname += "; Win64; x64"

            else:
                osname = "Unknown OS {}".format(machine)

            ua = "Mozilla/5.0 ({}) AppleWebKit/537.36 (KHTML, like Gecko) {} Safari/537.36".format(
                osname,
                self.get_fetch_user_agent_name(),
            )

        return ua

    def get_fetch_headers(self, method, headers, http_cookies):
        """merge class headers with passed in headers

        you can see what headers browsers are sending: http://httpbin.org/headers

        More info:
            - https://www.whatismybrowser.com/guides/the-latest-user-agent/chrome

        why does this want to look similar to a browser?
            - https://www.zenrows.com/blog/stealth-web-scraping-in-python-avoid-blocking-like-a-ninja
            - https://www.scrapehero.com/how-to-fake-and-rotate-user-agents-using-python-3/

        :param method: string, (eg, GET or POST), this is passed in so you can customize
            headers based on the method that you are calling
        :param headers: dict, all the headers passed into the fetch method
        :param http_cookies: dict, all the cookies
        :returns: passed in headers merged with global class headers
        """
        fetch_headers = HTTPHeaders({
            "Accept": ",".join([
                "text/html",
                "application/xhtml+xml",
                "application/xml;q=0.9",
                "image/avif",
                "image/webp",
                "image/apng",
                "*/*;q=0.8",
                "application/signed-exchange;v=b3;q=0.9", 
            ]),
            # https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Accept-Encoding
            # Indicates the identity function (that is, without modification or compression)
            "Accept-Encoding": "identity", #"gzip, deflate", 
            # https://stackoverflow.com/a/29020782/5006
            # could use LANG environment variable
            "Accept-Language": "*", #"en-US,en;q=0.9",
            "Dnt": "1", 
            "Upgrade-Insecure-Requests": "1", 
            "User-Agent": self.get_fetch_user_agent(),
        })

        if self.headers:
            fetch_headers.update(self.headers)

        if headers:
            fetch_headers.update(headers)

        if http_cookies:
            cl = []
            for k, v in http_cookies.items():
                c = cookies.SimpleCookie()
                c[k] = v
                cl.append(c[k].OutputString())
            if cl:
                fetch_headers["Cookie"] =  ", ".join(cl)

        return fetch_headers

    def get_fetch_body(self, headers, body):
        """Get the body that will be sent up to the server

        :param headers: HTTPHeaders, the full set of headers being sent to the server,
            that means these headers have been returned from get_fetch_headers
        :param body: mixed, the raw body that will be normalized and returned
        :returns: str, the body ready to be sent up to the server
        """
        if self.is_json(headers):
            ret = json.dumps(body)
        else:
            ret = urlencode(body, doseq=True)
        return ret if is_py2 else ret.encode(environ.ENCODING)

    def get_fetch_request(self, method, *args, **kwargs):
        """Create a request that can be passed to get_fetch_response to actually
        make the request

        This is used in self._fetch

        :param method: str, the http method (eg GET, POST)
        :param *args: mixed, any positional arguments you need
        :param **kwargs: mixed, any keyword arguments you need
        :returns: Request instance, a request object that can be passed to get_fetch_response
        """
        req = Request(*args, **kwargs) # compat * import
        # https://stackoverflow.com/a/111988
        req.get_method = lambda: method.upper()
        return req

    def get_fetch_response(self, req, timeout):
        """Given a Request instance make a call and return the response

        This is used in self._fetch

        https://docs.python.org/3/library/urllib.request.html#urllib.request.urlopen

        :param req: Request instance, the request instance created by self.get_fetch_request
        :returns: HTTPResponse instance, this looks like a requests Response object
        """
        try:
            res = urlopen(req, timeout=timeout)
            ret = HTTPResponse(
                res.code,
                res.read(),
                res.headers,
                self,
                res
            )

        except HTTPError as e:
            ret = HTTPResponse(
                e.code,
                # an HTTPError can also function as a non-exceptional file-like
                # return value (the same thing that urlopen() returns).
                # If you don't read the error it will leave a dangling socket
                e.read(),
                {},
                self,
                e
            )

        except URLError as e:
            ret = HTTPResponse(
                0,
                e.reason,
                {},
                self,
                e
            )

        return ret

    def is_json(self, headers):
        """return true if content_type is a json content type"""
        ret = False
        ct = headers.get(
            "Content-Type",
            headers.get("content-type", "")
        ).lower()
        if ct:
            ret = ct.lower().rfind("json") >= 0
        return ret


class UserAgent(NormalizeString):
    """Parse a request User-Agent header value

    https://github.com/Jaymon/datatypes/issues/55

    This has the following attributes:

        * client_application
        * client_version
        * client_device
    """
    @classmethod
    def after_create(cls, instance, **kwargs):
        for k, v in cls.parse_user_agent(instance).items():
            setattr(instance, k, v)

        return instance

    @classmethod
    def parse_user_agent(cls, user_agent):
        """parses any user agent string to the best of its ability and tries not
        to error out"""
        d = {}

        regex = r"^([^/]+)" # 1 - get everything to first slash
        regex += r"\/" # ignore the slash
        regex += r"(\d[\d.]*)" # 2 - capture the numeric version or build
        regex += r"\s+\(" # ignore whitespace before parens group
        regex += r"([^\)]+)" # 3 - capture the full paren body
        regex += r"\)\s*" # ignore the paren and any space if it is there
        regex += r"(.*)$" # 4 - everything else (most common in browsers)
        m = re.match(regex, user_agent)
        if m:
            application = m.group(1)
            version = m.group(2)
            system = m.group(3)
            system_bits = re.split(r"\s*;\s*", system)
            tail = m.group(4)

            # common
            d['client_application'] = application
            d['client_version'] = version
            d['client_device'] = system_bits[0]

            if application.startswith("Mozilla"):
                for browser in ["Chrome", "Safari", "Firefox"]:
                    browser_m = re.search(
                        r"{}\/(\d[\d.]*)".format(browser),
                        tail
                    )
                    if browser_m:
                        d['client_application'] = browser
                        d['client_version'] = browser_m.group(1)
                        break

        return d
