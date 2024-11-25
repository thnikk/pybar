#!/usr/bin/python3 -u
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk # noqa


class Module(Gtk.MenuButton):
    def __init__(self, text):
        super().__init__()
        self.set_direction(Gtk.ArrowType.NONE)
        self.set_label(text)


class CachedModule():
    def __init__(self):
        self.cache = {}

    def module(self):
        self.module = Module()
        return self.module
