#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from datetime import datetime
import gi
import common as c
from calendar_widget import calendar_widget
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib


def pop():
    """ thing """
    popover = Gtk.Popover()
    popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
    popover.set_position(Gtk.PositionType.TOP)
    popover.set_transitions_enabled(False)
    widget = calendar_widget()
    widget.show_all()
    popover.add(widget)
    popover.set_position(Gtk.PositionType.TOP)
    return popover


def module():
    """ Clock module """
    label = Gtk.MenuButton(popover=pop())
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')

    def get_time():
        label.set_label(datetime.now().strftime(' %I:%M:%S'))
        return True

    if get_time():
        GLib.timeout_add(1000, get_time)
        return label
