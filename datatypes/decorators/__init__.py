# -*- coding: utf-8 -*-
# This module was moved from decorators on 1-19-2023 and .descriptor.method was
# added
from .. import logging


# this module is really verbose so we're going to raise its default level to be
# a bit more quiet
logging.setdefault(__name__, "INFO")


from .base import (
    Decorator,
    InstanceDecorator,
    ClassDecorator,
    FuncDecorator,
)
from .descriptor import (
    property,
    cachedproperty,
    classproperty,
    method,
    instancemethod,
    classmethod,
    staticmethod,
)
from .misc import (
    cache,
    deprecated,
)

