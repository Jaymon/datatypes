# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import logging

from .string import (
    String,
    ByteString,
    Base64,
    HTMLCleaner,
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
    NormalizeDict,
    idict,
    AppendList,
    OrderedList,
    Trie,
)
from .csv import (
    CSV,
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
from .headers import (
    Headers,
    Environ,
)
from .token import (
    # we don't import Token and SubToken because their names are too generic for
    # toplevel, if you need them import them directly from the submodule
    StreamTokenizer,
    Tokenizer,
)


__version__ = "0.1.2"


# get rid of "No handler found" warnings (cribbed from requests)
logging.getLogger(__name__).addHandler(logging.NullHandler())

