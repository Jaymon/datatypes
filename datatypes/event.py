# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from contextlib import contextmanager

from .compat import *


logger = logging.getLogger(__name__)


class Event(object):
    """An instance of this class is passed as the first argument to any
    callback when an event is broadcast"""
    def __init__(self, event, event_name, **kwargs):
        """
        :param event: Event, the instance that created this event
        :param event_name: str, the event's name
        """
        self.event = event
        self.event_name = event_name

        # each callback this event is broadcast to will be appended here, so
        # any callback can see the history of this instance
        self.event_callbacks = []

        # all the event keys of the passed in kwargs will be appended here
        self.event_keys = []

        for k, v in kwargs.items():
            self.event_keys.append(k)
            setattr(self, k, v)

    def __contains__(self, name):
        return name in self.event_keys

    def get(self, name, default=None):
        return getattr(self, name, default)


class Events(object):
    """The main interface for interacting with events

    you add events with .bind() and run events using either .broadcast() or
    .push()

    Moved from bang.event.Events on 1-18-2023

    :example:
        events = Events()

        # bind a callable to an event using the `.bind` method

        def callback1(bc_event):
            # every callback takes a BroadbacastEvent instance
            pass
        events.bind("EVENT_NAME", callback1)

        # bind a callable to an event using decorator syntax

        @events("EVENT_NAME")
        def callback2(bc_event):
            pass

        events.broadcast("EVENT_NAME", foo=1)
        # `foo` will be accessible in the bound callables through `event.foo`

        # bind param for one broadcast
        with events.bound_params(foo=1):
            events.broadcast("EVENT_NAME")

        # manipulate a value and get it back
        @events("EVENT_NAME")
        def callback3(event):
            event.bar += 1

        event = events.broadcast("EVENT_NAME", bar=1)
        print(event.bar) # 2
    """
    event_class = Event

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset this instance to its first initialized state

        This is called in `.__init__()` when a new instance is created and
        exists to make it easier for applications to have/test a
        singleton instance
        """
        # these are populated through .bind_event_params and will be present
        # in all events
        self.event_params = {}

        # this will hold any callbacks bound to an event_name through .bind
        self.bound = defaultdict(list)

        # this will hold Event instances under event_name keys that have been
        # broadcast through the .push() method
        self.pushed = defaultdict(list)

        # this will hold event instances under event_name keys taht have been
        # broadcast through the .once() method
        self.onced = defaultdict(list)

    def create_event(self, event_name, **kwargs):
        return self.event_class(
            self,
            event_name,
            **self.event_params,
            **kwargs
        )

    def push(self, event_name, **kwargs):
        """Similar to broadcast but if any new callbacks are bound to the
        event_name after the .push is called then those will be run on the
        binding also so it can pick up straggler bind calls

        .push() is used primarily for configure events to make order of events
        a little less important while configuring everything, after
        configuration, most events should be done using .broadcast()

        :param event_name: string, the event name whose callbacks should be ran
        :param **kwargs: key=val values that will be accessible in the Event
            instance passed to the callbacks
        :returns: BroadcastEvent, the ran Event instance
        """
        event = self.broadcast(event_name, **kwargs)
        self.pushed[event_name].append(event)
        return event

    def once(self, event_name, **kwargs):
        """Similar to broadcast but all the bound events for event_name will
        only be ran once and only once

        trigger might be an ok name for this also

        :param event_name: string, the event name whose callbacks should be ran
        :param **kwargs: key=val values that will be accessible in the Event
            instance passed to the callbacks
        :returns: BroadcastEvent, the ran Event instance
        """
        event = self.broadcast(event_name, **kwargs)

        # remove the callbacks from bound and add them to the once history so
        # they won't be ran again on subsequent calls
        callbacks = self.bound.pop(event_name, [])
        self.onced[event_name].extend(callbacks)

        return event

    def broadcast(self, event_name, **kwargs):
        """broadcast event_name to all bound callbacks

        :param event_name: string, the event name whose callbacks should be ran
        :param **kwargs: key=val values that will be accessible in the Event
            instance passed to the callbacks
        :returns: BroadcastEvent, the ran Event instance
        """
        event = self.create_event(event_name, **kwargs)
        callbacks = self.bound.get(event_name, [])
        if len(callbacks) > 0:
            logger.info("Event [{}] broadcasting to {} callbacks".format(
                event_name,
                len(callbacks)
            ))

            for callback in callbacks:
                self.emit(event, callback)

        else:
            logger.debug("Event [{}] ignored".format(event_name))

        return event

    def emit(self, event, callback):
        """Internal method used by .broadcast, etc.. Runs callback with the
        event instance

        :param event: BroadcastEvent instance, the event instance that holds
            all the information and keyword arguments that were passed to the
            broadcast method
        :param callback: callable, the callback that will be ran
        :returns: the same Event instance, because the event is returned,
            callbacks can add attributes to the event that can then be
            accessed after all callbacks have been ran
        """
        event_name = event.event_name

        logger.debug("Event [{}] running {} callback".format(
            event_name,
            callback
        ))
        callback(event)
        event.event_callbacks.append(callback)

    def bind(self, event_name, callback):
        """binds callback to event_name

        :param event_name: string, the event name
        :param callback: Callable[[BroadcastEvent], None], the
            callback to bind to event_name
        """
        self.bound[event_name].append(callback)

        logger.debug("Event [{}] bound to {} callback".format(
            event_name,
            callback
        ))

        # event has been pushed previously so go ahead and run this callback We
        # do this because we primarily use events to configure everything and
        # sometimes there is a chicken/egg problem where code will push an
        # event before the block that will handle that event is bound, but we
        # need that callback to be run when it is bound even though it's missed
        # the original broadcast, so any events that use the push method will
        # be run when new callbacks are added
        if event_name in self.pushed:
            logger.info(
                "Event [{}] pushing {} previous events to {} callback".format(
                    event_name,
                    len(self.pushed[event_name]),
                    callback,
                )
            )
            for event in self.pushed[event_name]:
                self.emit(event, callback)

    def bind_params(self, **kwargs):
        """Anything you pass into this will be passed to every event in
        this instance

        :example:
            events = Events()
            events.bind_event_params(foo=1)

            @events("<EVENT-NAME>")
            def event_handler(event):
                print(event.foo) # 1
        """
        self.event_params.update(kwargs)
    bind_event_params = bind_params # deprecated name

    @contextmanager
    def bound_params(self, **kwargs):
        """Temporar bind params to the events while in this context

        :example:
            events = Events()

            @events("<EVENT-NAME>")
            def event_handler(event):
                print(event.foo)

            with events.bound_params(foo=1):
                events.broadcast("<EVENT-NAME>") # event.foo=1

            events.broadcast("<EVENT-NAME>") # event.foo does not exist
        """
        try:
            self.bind_params(**kwargs)
            yield self

        finally:
            self.unbind_params(*kwargs.keys())

    def unbind_params(self, *keys):
        """Remove instance bound params from the global event params

        :argument *keys: str, one or more key names to remove
        """
        for key in keys:
            self.event_params.pop(key, None)

    def __call__(self, *event_names):
        """decorator that wraps the bind() method to make it easier to bind
        functions to an event

        :example:
            event = Events()

            @events("event_name")
            def callback(event):
                pass
        """
        # this isn't really a decorator, but decorators need to return a
        # callable that takes the wrapped callable, so this does that and
        # the wrap function gets called right away and binds the wrapped
        # callable to the event names and then returns the raw callable so it
        # doesn't actually wrap the callback
        def bind_to_callable(callback):
            for en in event_names:
                self.bind(en, callback)

            return callback

        return bind_to_callable

