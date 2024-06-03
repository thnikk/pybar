#!/usr/bin/python3 -u
"""
Description: Toggle module
Author: thnikkk
"""
import common as c
from subprocess import run
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def module(bar, config=None):
    module = c.box('h', spacing=5)
    c.add_style(module, 'module')
    module.add(c.label(''))
    # Put switch in vbox to prevent vertical expansion
    switch_box = c.box('v')
    switch = Gtk.Switch.new()
    c.add_style(switch, 'switch')
    switch_box.pack_start(switch, 1, 0, 0)
    module.add(switch_box)

    def update():
        return True

    if update():
        GLib.timeout_add(1000, update)
        return module
