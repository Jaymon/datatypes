# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from . import logging
from .string import (
    String,
    ByteString,
    Base64,
    HTMLCleaner,
    HTMLParser,
    HTML,
    NamingConvention,
)
from .number import (
    Shorten,
    Integer,
    Hex,
    Binary,
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
    HTMLTokenizer,
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
)


__version__ = "0.8.0"


# get rid of "No handler found" warnings (cribbed from requests)
# DEPRECATED 7-15-2022, doesn't seem to be needed in python3
logging.getLogger(__name__).addHandler(logging.NullHandler())

