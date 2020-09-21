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
    Sentinal,
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


__version__ = "0.0.20"


# get rid of "No handler found" warnings (cribbed from requests)
logging.getLogger(__name__).addHandler(logging.NullHandler())

