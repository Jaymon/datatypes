# -*- coding: utf-8 -*-

from datatypes.compat import *
from datatypes.event import Event
from . import TestCase


class EventTest(TestCase):
    def test_push_and_bind(self):
        ev = Event()

        @ev("push_and_bind")
        def push1(event):
            event.text += "1"

        r1 = ev.push("push_and_bind", text="1")

        @ev("push_and_bind")
        def push2(event):
            event.text += "2"

        r2 = ev.push("push_and_bind", text="2")

        @ev("push_and_bind")
        def push3(event):
            event.text += "3"

        self.assertEqual("1123", r1.text)
        self.assertEqual("2123", r2.text)

    def test_broadcast(self):
        ev = Event()

        r = ev.broadcast("foo", count=0)
        self.assertEqual(0, r.count)

        def cb1(event):
            event.count += 1
        ev.bind("foo", cb1)

        r = ev.broadcast("foo", count=0)
        self.assertEqual(1, r.count)

        r = ev.broadcast("foo", count=r.count)
        self.assertEqual(2, r.count)

    def test_once(self):
        ev = Event()

        @ev("once")
        def once1(event):
            pass

        @ev("once")
        def once2(event):
            pass

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("once1" in logs)
        self.assertTrue("once2" in logs)

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("ignored" in logs)

        @ev("once")
        def once3(event):
            pass

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertFalse("once1" in logs)
        self.assertFalse("once2" in logs)
        self.assertTrue("once3" in logs)

        with self.assertLogs(level="DEBUG") as c:
            ev.once("once")
        logs = "\n".join(c[1])
        self.assertTrue("ignored" in logs)

