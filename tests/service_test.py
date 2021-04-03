# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from datatypes.compat import *
from datatypes.service import (
    Service,
    Systemd
)

from . import TestCase, testdata


class SystemdTest(TestCase):
    def test_format(self):
        s = Systemd("foo")
        c, kw = s.format_cmd("start")

        self.assertEqual("sudo systemctl start foo", " ".join(c))

    def test_status(self):
        s = Systemd("foo")
        active = [
            'foo.service - "foo"',
            'Loaded: loaded (/etc/systemd/system/foo.service; enabled; vendor preset: enabled)',
            'Active: active (running) since Wed YYYY-MM-DD HH:MM:SS UTC; N days ago',
            'Main PID: NNNNN (name)',
            'Status: "foo is ready"',
            '    Tasks: 3 (limit: 2362)',
            'CGroup: /system.slice/foo.service',
        ]
        s = testdata.patch(s, status=lambda *_, **__: "\n".join(active))
        self.assertTrue(s.is_running())

        s = Systemd("foo")
        inactive = [
            'foo.service - "foo"',
            'Loaded: loaded (/etc/systemd/system/foo.service; enabled; vendor preset: enabled)',
            'Active: inactive (dead)',
        ]
        s = testdata.patch(s, status=lambda *_, **__: "\n".join(inactive))
        self.assertFalse(s.is_running())

    def test_exists(self):
        s = Systemd("foo")
        s.path # just make sure there aren't any syntax errors


class ServiceTest(TestCase):
    def test_infer(self):
        systemd_class = testdata.patch(
            Systemd,
            exists=lambda *_, **__: True
        )
        service_class = testdata.patch(
            Service,
            service_classes=lambda *_, **__: [systemd_class]
        )
        s = service_class("foo")
        self.assertEqual(systemd_class, s.__class__)

    def test_fail(self):
        with self.assertRaises(RuntimeError):
            s = Service("aksdfjldaksfdfjklsfkjlakhds")

    def test_service_classes(self):
        service_classes = list(Service.service_classes())
        self.assertTrue(Systemd in service_classes)

