#!/usr/bin/python3 -u
"""
Description: Debug module to open GTK Inspector
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


def create_widget(bar, config):
    """ Create debug widget """
    button = Gtk.Button()
    button.get_style_context().add_class('module')

    icon_text = config.get('icon', '')
    label = c.label(icon_text)
    button.set_child(label)

    def open_inspector(btn):
        Gtk.Window.set_interactive_debugging(True)

    button.connect('clicked', open_inspector)
    return button
