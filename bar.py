#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import gi
import os
import common as c
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib


class Bar:
    """ Bar class"""
    def __init__(self, spacing=0):
        self.window = Gtk.Window()
        self.bar = c.box('h', style='bar', spacing=spacing)
        self.left = c.box('h', style='modules-left', spacing=spacing)
        self.center = c.box('h', style='modules-center', spacing=spacing)
        self.right = c.box('h', style='modules-right', spacing=spacing)
        self.bar.pack_start(self.left, 0, 0, 0)
        self.bar.set_center_widget(self.center)
        self.bar.pack_end(self.right, 0, 0, 0)
        self.window.add(self.bar)

    def css(self, file):
        """ Load CSS from file """
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(os.path.expanduser(file))
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def modules(self, modules):
        """ Add modules to bar """
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.get_style_context().add_class("bar")

        for index, position in enumerate(["left", "center", "right"]):
            section = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            section.get_style_context().add_class(position)
            for module in modules[index]:
                section.pack_start(module(), False, False, 0)
            main.pack_start(section, position == "center", False, 0)

        self.window.add(main)

    def start(self):
        """ Start bar """
        GtkLayerShell.init_for_window(self.window)

        # Anchor and stretch to bottom of the screen
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.BOTTOM, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.RIGHT, 1)

        # Set margin to make bar more readable for testing
        margin = 10
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.LEFT, margin)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.RIGHT, margin)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.BOTTOM, margin)

        GtkLayerShell.set_namespace(self.window, 'pybar')

        # Reserve part of screen
        GtkLayerShell.auto_exclusive_zone_enable(self.window)

        self.window.show_all()
        self.window.connect('destroy', Gtk.main_quit)
        Gtk.main()
