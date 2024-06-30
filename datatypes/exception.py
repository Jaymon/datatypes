# -*- coding: utf-8 -*-

from subprocess import (
    CalledProcessError,
)


class CalledProcessError(CalledProcessError, RuntimeError):
    """Raised by Command when the return code is unexpected, this is extended
    so RuntimeError can also be checked since this was a common way for me to
    raise return code errors in the past"""
    pass

