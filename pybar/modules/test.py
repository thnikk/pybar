#!/usr/bin/python3 -u
"""
Description: Test module
Author: thnikkk
"""
from .. import common as c
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def module(bar, config=None):
    module = c.Module()
    module.set_position(bar.position)
    module.icon.set_label('')
    module.text.set_label('0')

    widget = c.Widget()
    widget.heading('Test')
    widget.draw()
    module.set_popover(widget)

    def click_action(module, event):
        c.print_debug(event.button)

    def scroll_action(module, event):
        c.print_debug(event.direction)

    module.connect('button-press-event', click_action)
    module.connect('scroll-event', scroll_action)

    def update():
        num = int(module.text.get_label()) + 1
        module.text.set_label(str(num))
        return True

    if update():
        GLib.timeout_add(1000, update)
        return module
