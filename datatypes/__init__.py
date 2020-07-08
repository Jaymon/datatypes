# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import logging

from .string import (
    String,
    Unicode, # alias for String
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
    PriorityQueue,
    NormalizeDict,
    idict,
    AppendList,
)
from .csv import (
    CSV,
)


__version__ = "0.0.4"


# get rid of "No handler found" warnings (cribbed from requests)
logging.getLogger(__name__).addHandler(logging.NullHandler())

