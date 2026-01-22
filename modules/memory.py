#!/usr/bin/python3 -u
"""
Description: Memory widget
Author: thnikk
"""
import common as c
import psutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def module(bar, config=None):
    """ Memory module """
    module = c.Module()
    module.set_position(bar.position)
    module.icon.set_label('')

    def get_memory():
        total = int(psutil.virtual_memory().total / (1024.0 ** 3))
        used = int(psutil.virtual_memory().used / (1024.0 ** 3))
        new = f"{used}"
        last = module.text.get_label()
        if new != last:
            module.text.set_label(new)
        return True

    if get_memory():
        GLib.timeout_add(1000, get_memory)
        return module
