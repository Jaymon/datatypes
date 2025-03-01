# -*- coding: utf-8 -*-
import os
import tempfile

from .base import Environ


###############################################################################
# Actual environment configuration that is used throughout the package
###############################################################################
environ = Environ("DATATYPES_")

environ.setdefault("ENCODING", "UTF-8")
"""For things that need encoding, this will be the default encoding if nothing
else is passed in"""


environ.setdefault("ENCODING_ERRORS", "replace")
"""For things that need encoding, this will handle any errors"""


# 2021-1-15 - we place our cache by default into another directory because I
# have problems running some commands like touch on the base temp directory on
# MacOS on Python3, no idea why but I couldn't get around it
environ.setdefault(
    "CACHE_DIR",
    os.path.join(tempfile.gettempdir(), environ.namespace.lower().rstrip("_"))
)
"""the default caching directory for things that need a cache folder"""


environ.setdefault("USER_AGENT", "")

