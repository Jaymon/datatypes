# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from . import logging
from .logging import (
    LogMixin,
)
from .string import (
    String,
    ByteString,
    Base64,
    NamingConvention,
    EnglishWord,
)
from .html import (
    HTMLCleaner,
    HTMLParser,
    HTML,
    HTMLTokenizer,
)
from .number import (
    Shorten,
    Integer,
    Hex,
    Binary,
    Exponential,
)
from .collections import (
    Pool,
    PriorityQueue,
    Dict,
    NormalizeDict,
    idict, IDict, Idict, iDict,
    AppendList,
    OrderedList,
    Trie,
    Namespace,
    ContextNamespace,
    HotSet,
    Stack,
)
from .csv import (
    CSV,
    TempCSV,
)
from .enum import (
    Enum,
)
from .path import (
    Path,
    Filepath,
    Dirpath,
    Imagepath,
    TempFilepath, Filetemp,
    TempDirpath, Dirtemp,
    Cachepath,
    Sentinel,
    UrlFilepath,
    SitePackagesDirpath,
)
from .environ import (
    Environ,
)
from .url import (
    Url,
    Host,
)
from .copy import (
    Deepcopy,
)
from .datetime import (
    Datetime,
)
from .http import (
    HTTPHeaders,
    HTTPEnviron,
    HTTPClient,
)
from .token import (
    # we don't import Token because it's too generic for toplevel, if you need it
    # then import it directly from the submodule
    StreamTokenizer,
    Tokenizer,
)
from .email import (
    Email,
)
from .parse import (
    ArgvParser,
    ArgParser,
)
from .utils import (
    cball,
    cbany,
    make_dict,
    make_list,
    Singleton,
)
from .profile import (
    Profiler,
    AggregateProfiler,
    AggregateProfiler as AProfiler
)
from .reflection import (
    OrderedSubclasses,
    Extend,
    ReflectModule,
    ReflectClass,
)
from .event import (
    Event,
)
from .decorators import (
    Decorator,
    InstanceDecorator,
    ClassDecorator,
    FuncDecorator,
    property,
    classproperty,
    method,
    instancemethod,
    classmethod,
    staticmethod,
    once,
    deprecated,
)
from .server import (
    PathServer,
    CallbackServer,
    WSGIServer,
)


__version__ = "0.9.4"


# get rid of "No handler found" warnings (cribbed from requests)
# DEPRECATED 7-15-2022, doesn't seem to be needed in python3
logging.getLogger(__name__).addHandler(logging.NullHandler())

