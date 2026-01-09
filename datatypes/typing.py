"""
Typing hints in one place, I keep having to remember where certain annotations
are located to import them, hopefully I'll be able to use this as a source
of truth

https://github.com/python/typeshed - Typeshed contains external type
annotations for the Python standard library and Python builtins

https://docs.python.org/3/library/typing.html#user-defined-generic-types
Good overview on how to define custom classes so they can accept annotations
and use those annotations throughout the class to make sure they expect the
correct type
"""

# https://docs.python.org/3/library/typing.html
from typing import (
    TypeVar,
    NewType, # https://docs.python.org/3/library/typing.html#typing.NewType
    TypeVarTuple, # https://docs.python.org/3/library/typing.html#typing.TypeVarTuple

    T, # https://docs.python.org/3/library/typing.html#generics
    Generic, # https://docs.python.org/3/library/typing.html#typing.Generic
    Any,
    LiteralString,
    Literal,
    NoReturn, Never,

    # represents current enclosed class
    #https://docs.python.org/3/library/typing.html#typing.Self
    Self,
    Protocol,

    Union,
    Optional,
    ClassVar,
    Final, # https://docs.python.org/3/library/typing.html#typing.Final

    # Dict with typing info for keys/values
    # https://docs.python.org/3/library/typing.html#typing.TypedDict
    TypedDict,
    Required,
    NotRequired,
    #ReadOnly, # py 3.13+ https://docs.python.org/3/library/typing.html#typing.ReadOnly

    # tuple version of TypedDict
    NamedTuple, # https://docs.python.org/3/library/typing.html#typing.NamedTuple

    Annotated, # https://docs.python.org/3/library/typing.html#typing.Annotated
    #TypeIs, # https://docs.python.org/3/library/typing.html#typing.TypeIs
    TypeGuard,

    # https://docs.python.org/3/library/typing.html#abcs-and-protocols-for-working-with-i-o
    IO,
    TextIO,
    BinaryIO,
)


# https://docs.python.org/3/library/types.html
from types import (
    NoneType,
    FunctionType,
    LambdaType,
    GeneratorType,
    CoroutineType,
    AsyncGeneratorType,
    MethodType,
    EllipsisType,
    UnionType,
    FrameType,
    CodeType,
    ModuleType,
)


# https://docs.python.org/3/library/contextlib.html
#
# You should use these instead of the typing versions, as described in:
# https://docs.python.org/3/library/typing.html#aliases-to-contextlib-abcs
from contextlib import (
    AbstractContextManager,
    AbstractAsyncContextManager,
    ContextDecorator,
    AsyncContextDecorator,
)


# https://docs.python.org/3/library/typing.html#abcs-and-protocols-for-working-with-i-o
# from typing import (
#     IO,
#     TextIO,
#     BinaryIO,
# )

# https://docs.python.org/3/library/io.html
# from io import (
#     IOBase,
#     TextIOBase,
# )


# https://docs.python.org/3/library/collections.abc.html
from collections.abc import (
    Container,
    Hashable,
    Iterable, # use this for things that just need to be iterated from 0...N
    Iterator,
    Reversible,
    Generator, # https://docs.python.org/3/library/typing.html#annotating-generators-and-coroutines
    AsyncIterable,
    AsyncIterator,
    AsyncGenerator,
    Sized,
    Callable, # callbacks, first arg is arguments, second is return type
    Collection,
    Sequence,
    MutableSequence,
    Set,
    MutableSet,
    Mapping, # base class for dict-like behavior
    MutableMapping,
    Awaitable,
    Coroutine,
    Buffer,
)

