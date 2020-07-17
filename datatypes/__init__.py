# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import logging

from .string import (
    String, Unicode,
    ByteString,
    Base64,
    HTMLCleaner,
)
from .integer import (
    Shorten,
    Integer,
)
from .collections import (
    Pool,
    KeyQueue,
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
    Filepath,
    Dirpath,
    TempFilepath, Filetemp,
    TempDirpath, Dirtemp,
    SitePackagesDirpath,
)


__version__ = "0.0.8"


# get rid of "No handler found" warnings (cribbed from requests)
logging.getLogger(__name__).addHandler(logging.NullHandler())

