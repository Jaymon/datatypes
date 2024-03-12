# -*- coding: utf-8 -*-
import functools
import inspect
import re


from ..compat import *
from .. import logging


logger = logging.getLogger(__name__)


class Decorator(logging.LogMixin):
    """A decorator class that you can be extended that allows you to do normal
    decorators with no arguments, or a decorator with arguments

    May be invoked as a simple, argument-less decorator (eg, `@decorator`) or
    with arguments customizing its behavior (eg,`@decorator(*args, **kwargs)`).

    To create your own decorators, just extend this class and override the
    decorate_func() method to decorate functions/methods and/or the
    decorate_class() method to decorate classes.

    based off of the task decorator in Fabric
    https://github.com/fabric/fabric/blob/master/fabric/decorators.py#L15

    with modifications inspired by --
    https://wiki.python.org/moin/PythonDecoratorLibrary#Class_method_decorator_using_instance
    https://wiki.python.org/moin/PythonDecoratorLibrary#Creating_decorator_with_optional_arguments

    other links --
    http://pythonconquerstheuniverse.wordpress.com/2012/04/29/python-decorators/
    http://stackoverflow.com/questions/739654/
    http://stackoverflow.com/questions/666216/decorator-classes-in-python
    """
    wrapped_call = ""
    """will hold either __new__ or __call__ depending on which of those contains
    the arg to wrap with the decorator as inferred by this class"""

    @classmethod
    def get_logger_instance(cls, *args, **kwargs):
        return logger

    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls)

        instance.decorator_args = args
        instance.decorator_kwargs = kwargs

        if instance.is_possible_wrap_call(*args, **kwargs):
            #functools.update_wrapper(instance, args[0], updated=())
            if instance.is_class(args[0]):
                instance.update_class_wrapper(instance, args[0])

                instance.log("__new__ returning wrapped class")
                try:
                    instance.wrapped_call = "__new__"
                    # here we do some magic stuff to return the class back in
                    # case this is a class decorator, we do this so we don't
                    # wrap the class, thus causing things like isinstance()
                    # checks to fail or the class variables being hidden
                    instance = instance.decorate_class(args[0])

                except NotImplementedError:
                    instance.log(
                        "Classes are not supported with this decorator"
                    )
                    instance.wrapped_call = "__call__"

                except TypeError:
                    # there are a few reasons this might fail, for example, the
                    # decorator could expect some arguments, but if it does fail
                    # we'll just assume we should treat the passed in values as
                    # the decorators arguments
                    instance.log("__new__ failed ambiguous class wrap")
                    instance.wrapped_call = "__call__"

            else:
                instance.update_func_wrapper(instance, args[0])

        else:
            instance.log(
                "__new__ arguments are not wrappable, "
                "so __call__ is the wrap call"
            )
            instance.wrapped_call = "__call__"

        return instance

    def is_class(self, arg):
        return isinstance(arg, type)

    def is_function(self, arg):
        return inspect.isroutine(arg)

    def is_possible_wrap_call(self, *args, **kwargs):
        ret = False
        if len(args) == 1 and not kwargs:
            ret = self.is_wrappable(args[0])
        return ret

    def is_wrappable(self, arg):
        return self.is_function(arg) or self.is_class(arg)

    def update_func_wrapper(self, wrapper, wrapped):
        wrapper.__orig_module__ = wrapper.__module__
        wrapper.__orig_name__ = getattr(wrapper, "__name__", "<UNKNOWN>")
        wrapper.__orig_qualname__ = getattr(
            wrapper,
            "__qualname__",
            "<UNKNOWN>"
        )
        wrapper.__orig_doc__ = wrapper.__doc__
        wrapper.__orig_decorator__ = self

        # https://docs.python.org/3/library/functools.html#functools.update_wrapper
        functools.update_wrapper(wrapper, wrapped, updated=())

    def update_class_wrapper(self, wrapper, wrapped):

        wrapper.__orig_module__ = wrapper.__module__
        wrapper.__orig_doc__ = wrapper.__doc__
        wrapper.__orig_decorator__ = self

        if isinstance(wrapper, type):
            wrapper.__orig_name__ = wrapper.__name__
            wrapper.__orig_qualname__ = wrapper.__qualname__

        else:
            wrapper.__orig_name__ = wrapper.__class__.__name__
            wrapper.__orig_qualname__ = wrapper.__class__.__qualname__

        functools.update_wrapper(wrapper, wrapped, updated=())

#         wrapper.__name__ = wrapped.__name__
#         wrapper.__module__ = wrapped.__module__
#         wrapper.__doc__ = wrapped.__doc__
#         wrapper.__wrapped__ = wrapped

    def wrap(self, wrapped, *decorator_args, **decorator_kwargs):
        if self.is_function(wrapped):
            self.log("Calling decorate_func()")
            ret = self.decorate_func(
                wrapped,
                *decorator_args,
                **decorator_kwargs
            )

            self.update_func_wrapper(ret, wrapped)

        elif self.is_class(wrapped):
            self.log("Calling decorate_class()")
            ret = self.decorate_class(
                wrapped,
                *decorator_args,
                **decorator_kwargs
            )

            self.update_class_wrapper(ret, wrapped)

        else:
            raise ValueError("wrapped is not a class or a function")

        return ret

    def __get__(self, instance, instance_class):
        """
        having this method here turns the class into a descriptor used when
        there is no (...) on the decorator, this is only called when the
        decorator is on a method, it won't be called when the decorator is on a
        non class method (ie, just a normal function), it also won't fire when
        the decorated method is a classmethod
        """
        self.log("__new__ was the wrap call because __get__ called")

        # we now know the __new__ call was a wrap_call and there are no
        # decorator arguments
        wrapped = self.decorator_args[0]
        inner_wrapper = self.decorate_func(wrapped)
        self.update_func_wrapper(inner_wrapper, wrapped)
        self.wrapped_call = "__new__"

        if inspect.iscoroutinefunction(inner_wrapper):
            async def outer_wrapper(*args, **kwargs):
                if instance is None:
                    return await inner_wrapper(*args, **kwargs)

                else:
                    return await inner_wrapper(instance, *args, **kwargs)

        else:
            def outer_wrapper(*args, **kwargs):
                if instance is None:
                    return inner_wrapper(*args, **kwargs)
                else:
                    return inner_wrapper(instance, *args, **kwargs)

        self.update_func_wrapper(outer_wrapper, inner_wrapper)

        return outer_wrapper

    def __call__(self, *args, **kwargs):
        """call is used when there are (...) on the decorator or when there are
        no (...) and the actual wrapped thing (function/method/class) is called
        """
        invoke = False
        ambiguous = False
        decorator_args = ()
        decorator_kwargs = {}

        if self.wrapped_call == "__call__":
            self.log("__call__ is the wrap call")
            decorator_args = self.decorator_args
            decorator_kwargs = self.decorator_kwargs
            wrapped = args[0]

        elif self.wrapped_call == "__new__":
            self.log("__new__ is the wrap call")
            decorator_args = ()
            decorator_kwargs = {}
            wrapped = self.decorator_args[0]
            invoke = True

        else:
            if self.is_possible_wrap_call(*args, **kwargs):
                self.log("__call__ could be a wrap call")

                decorator_args = self.decorator_args
                decorator_kwargs = self.decorator_kwargs
                self.wrapped_call = "__call__"

                is_possible = self.is_possible_wrap_call(
                    *self.decorator_args,
                    **self.decorator_kwargs
                )
                if is_possible:
                    self.log("__new__ could be a wrap call also")

                    # this is the tough one, we have some possibilities:
                    # 1. the __new__ call contained a callback or class passed
                    #    to the decorator 
                    # 2. the decorator had nothing (eg, @dec) and the wrapped
                    #    arg takes only a function or callback as its one
                    #    argument
                    #
                    # I'm going to assume that the function/class was passed
                    # into the decorator so the __new__ call contained decorator
                    # arguments
                    wrapped = args[0]
                    ambiguous = True

                    self.log("choosing __call__ as wrapped call over __new__")

                else:
                    self.log("choosing __call__ as wrapped call")
                    wrapped = args[0]

            else:
                self.log(
                    "__call__ arguments are not wrappable, "
                    "so __new__ is the wrap call"
                )
                wrapped = self.decorator_args[0]
                invoke = True
                self.wrapped_call = "__new__"

        try:
            ret = self.wrap(wrapped, *decorator_args, **decorator_kwargs)

        except NotImplementedError as e:
            if ambiguous:
                # we guessed wrong
                self.log(
                    "Unsupported guess, swapping __call__ and __new__ arguments"
                )
                self.wrapped_call = "__new__"
                ret = self(*args, **kwargs)

            else:
                raise

        if invoke:
            self.log("Invoking decorated value")
            try:
                ret = ret(*args, **kwargs)

            except (TypeError, NotImplementedError) as e:
                # we guessed wrong
                if ambiguous:
                    self.log(
                        "Failed ambiguous wrap, "
                        "swapping __call__ and __new__ arguments"
                    )
                    self.wrapped_call = "__new__"
                    ret = self(*args, **kwargs)

                else:
                    raise

        return ret

#     def log(self, format_str, *format_args, **log_options):
#         """wrapper around the module's logger
# 
#         :param format_str: string, the message to log
#         :param *format_args: list, if format_str is a string containing {}, then
#             format_str.format(*format_args) is ran
#         :param **log_options: 
#             level -- something like logging.DEBUG
#             prefix -- will be prepended to format_str, defaults to
#                 [<CLASS_NAME>]
#             exc_info -- boolean, passed to the logger to log stack trace
#         """
#         if isinstance(format_str, Exception):
#             logger.exception(format_str, *format_args)
#         else:
#             log_level = log_options.pop('level', logging.DEBUG)
#             if log_level not in logging._levelToName:
#                 log_level = logging._nameToLevel.get(log_level.upper())
# 
#             if logger.isEnabledFor(log_level):
#                 log_prefix = log_options.pop(
#                     'prefix', "[{}]".format(self.__class__.__name__)
#                 )
#                 format_str = "{} {}".format(log_prefix, format_str)
#                 if format_args:
#                     logger.log(
#                         log_level,
#                         format_str.format(*format_args),
#                         **log_options
#                     )
# 
#                 else:
#                     logger.log(log_level, format_str, **log_options)


    def decorate_func(self, func, *decorator_args, **decorator_kwargs):
        """override this in a child class with your own logic, it must return a
        function that calls self.func

        :param func: callable, the function being decorated
        :param decorator_args: tuple, the arguments passed into the decorator
            (eg, @dec(1, 2))
        :param decorator_kwargs: dict, the named args passed into the decorator
            (eg, @dec(foo=1))
        :returns: the wrapped func with our decorator func
        """
        raise NotImplementedError(
            "decorator {} does not support function decoration".format(
                self.__class__.__name__
            )
        )

    def decorate_class(self, wrapped_class, *decorator_args, **decorator_kwargs):
        """override this in a child class with your own logic, it must return a
        function that returns klass or the like

        :param wrapped_class: type, the class object that is being decorated
        :param decorator_args: tuple, the arguments passed into the decorator
            (eg, @dec(1, 2))
        :param decorator_kwargs: dict, the named args passed into the decorator
            (eg, @dec(foo=1))
        :returns: the wrapped class
        """
        raise NotImplementedError(
            "decorator {} does not support class decoration".format(
                self.__class__.__name__
            )
        )


class InstanceDecorator(Decorator):
    """only decorate instances of a class"""
    def is_wrappable(self, arg):
        return self.is_class(arg)

    def decorate(self, instance, *decorator_args, **decorator_kwargs):
        """
        override this in a child class with your own logic, it must return an
        instance of a class

        :param instance: object, the class instance being decorated
        :param decorator_args: tuple, the arguments passed into the decorator
            (eg, @dec(1, 2))
        :param decorator_kwargs: dict, the named args passed into the decorator
            (eg, @dec(foo=1))
        """
        raise NotImplementedError("Define this method in your child class")

    def decorate_class(self, wrapped_class, *decorator_args, **decorator_kwargs):
        """where the magic happens, this wraps a class to call our decorate
        method in the init of the class
        """
        class ChildClass(wrapped_class):
            def __init__(slf, *args, **kwargs):
                super(ChildClass, slf).__init__(*args, **kwargs)
                self.decorate(
                    slf, *decorator_args, **decorator_kwargs
                )

        return ChildClass


class ClassDecorator(Decorator):
    """only decorate a class"""
    def is_wrappable(self, arg):
        return self.is_class(arg)

    def decorate(self, wrapped_class, *decorator_args, **decorator_kwargs):
        """
        override this in a child class with your own logic, it must return a
        class object

        :param wrapped_class: type, the class being decorated
        :param decorator_args: tuple, the arguments passed into the decorator
            (eg, @dec(1, 2))
        :param decorator_kwargs: dict, the named args passed into the decorator
            (eg, @dec(foo=1))
        :returns: type, the class object
        """
        raise NotImplementedError("Define this method in your child class")

    def decorate_class(self, wrapped_class, *args, **kwargs):
        return self.decorate(wrapped_class, *args, **kwargs)


class FuncDecorator(Decorator):
    """only decorate functions/methods"""
    def is_wrappable(self, arg):
        return self.is_function(arg)

    def decorate(self, func, *decorator_args, **decorator_kwargs):
        """
        override this in a child class with your own logic, it must return a
        function that calls self.func

        :param func: callable, the function being decorated
        :param decorator_args: tuple, the arguments passed into the decorator
            (eg, @dec(1, 2))
        :param decorator_kwargs: dict, the named args passed into the decorator
            (eg, @dec(foo=1))
        :returns: callable, the function that wraps func
        """
        raise NotImplementedError("Define this method in your child class")

    def decorate_func(self, func, *args, **kwargs):
        return self.decorate(func, *args, **kwargs)

