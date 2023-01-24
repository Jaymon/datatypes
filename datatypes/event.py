# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import logging
from collections import defaultdict

from .compat import *
from .utils import Singleton


logger = logging.getLogger(__name__)


class BroadcastEvent(object):
    """An instance of this class is passed as the first argument to any callback
    when an event is broadcast"""
    def __init__(self, event_name, **kwargs):
        self.event_name = event_name
        self.event_callbacks = []
        self.event_keys = list(kwargs.keys())

        for k, v in kwargs.items():
            setattr(self, k, v)


class Event(Singleton):
    """Singleton. The main interface for interacting with events

    you add events with .bind() and run events using either .broadcast() or .push()

    Moved from bang.event.Events on 1-18-2023

    :Example:
        @event("EVENT_NAME")
        def callback(event):
            # every callback takes an event and callback instance
            pass

        event.broadcast("EVENT_NAME", foo=1)
        # in the callback foo will be accessible through event.foo
    """
    broadcast_class = BroadcastEvent

    def __init__(self):
        self.reset()

    def reset(self):
        # this will hold any callbacks bound to an event_name through .bind
        self.bound = defaultdict(list)

        # this will hold Event instances under event_name keys that have been
        # broadcast through the .push() method
        self.pushed = defaultdict(list)
        self.onced = defaultdict(list)

    def push(self, event_name, **kwargs):
        """Similar to broadcast but if any new callbacks are bound to the event_name
        those will be run on the binding so it can pick up straggler bind calls

        .push() is used primarily for configure events to make order of events a
        little less important while configuring everything, after configuration,
        most events should be done using .broadcast()

        :param event_name: string, the event name whose callbacks should be ran
        :param **kwargs: key=val values that will be accessible in the Event instance
            passed to the callbacks
        :returns: an Event instance
        """
        event = self.broadcast(event_name, **kwargs)
        self.pushed[event_name].append(event)
        return event

    def once(self, event_name, **kwargs):
        """Similar to broadcast but all the bound events for event_name will only
        be ran once and only once

        trigger might be an ok name for this also

        :param event_name: string, the event name whose callbacks should be ran
        :param **kwargs: key=val values that will be accessible in the Event instance
            passed to the callbacks
        :returns: an Event instance
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
        :param **kwargs: key=val values that will be accessible in the Event instance
            passed to the callbacks
        :returns: an Event instance
        """
        event_kwargs = {}
        event_kwargs.update(getattr(self, "event_kwargs", {}))
        event_kwargs.update(kwargs)

        event = self.broadcast_class(event_name, **event_kwargs)
        callbacks = self.bound.get(event_name, [])
        if len(callbacks) > 0:
            logger.info("Event [{}] broadcasting to {} callbacks".format(event_name, len(callbacks)))

            for callback in callbacks:
                self.run(event, callback)

        else:
            logger.debug("Event [{}] ignored".format(event_name))

        return event

    def run(self, event, callback):
        """Runs callback with the event instance

        :param event: Event instance, the event instance that holds all the information
            and keyword arguments that were passed to the broadcast method
        :param callback: callable, the callback that will be ran
        :returns: the same Event instance, because the event is returned, callbacks
            can add attributes to the event that can then be accessed after all
            callbacks have been ran
        """
        event_name = event.event_name

        logger.debug("Event [{}] running {} callback".format(event_name, callback))
        callback(event, **getattr(self, "callback_kwargs", {}))
        event.event_callbacks.append(callback)

        return event

    def bind(self, event_name, callback):
        """binds callback to event_name

        :param event_name: string, the event name
        :param callback: callable, typically, the callback should accept (event, *args, **kwargs)
        """
        self.bound[event_name].append(callback)

        logger.debug("Event [{}] bound to {} callback".format(event_name, callback))

        # event has been pushed previously so go ahead and run this callback 
        # We do this because we primarily use events to configure everything and
        # sometimes there is a chicken/egg problem where code will push an event
        # before the block that will handle that event is bound, but we need that
        # callback to be run when it is bound even though it's missed the original
        # broadcast, so any events that use the push method will be run when new
        # callbacks are added
        if event_name in self.pushed:
            logger.info("Event [{}] pushing {} previous events to {} callback".format(
                event_name,
                len(self.pushed[event_name]),
                callback,
            ))
            for event in self.pushed[event_name]:
                self.run(event, callback)

    def bind_event_params(self, **kwargs):
        """Anything you pass into this will be passed to every event

        :Example:
            event = Event()
            event.bind_event_params(foo=1)

            @event("<EVENT-NAME>")
            def event_handler(event):
                print(event.foo) # 1
        """
        self.event_kwargs = kwargs

    def bind_callback_params(self, **kwargs):
        """Anything you pass into this will be passed directly to all callbacks, 
        so you need to be very careful with this since all callbacks will need to
        account for these

        :Example:
            event = Event()
            event.bind_callback_params(foo=1)

            @event("<EVENT-NAME>")
            def event_handler(event, foo):
                print(foo) # 1
        """
        self.callback_kwargs = kwargs

    def __call__(self, *event_names):
        """decorator that wraps the bind() method to make it easier to bind functions
        to an event

        :Example:
            event = Event()

            @event("event_name")
            def callback(event):
                pass
        """
        def wrap(callback):
            for en in event_names:
                self.bind(en, callback)

            return callback

        return wrap

