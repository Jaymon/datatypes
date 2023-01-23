# -*- coding: utf-8 -*-
# This module was moved from decorators on 1-19-2023 and .descriptor.method was
# added

from .base import (
    Decorator,
    InstanceDecorator,
    ClassDecorator,
    FuncDecorator,
)
from .descriptor import (
    property,
    classproperty,
    method,
    instancemethod,
    classmethod,
    staticmethod,
)
from .misc import (
    once,
    deprecated,
)

