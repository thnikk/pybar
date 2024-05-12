#!/usr/bin/python3 -u
"""
Description: Main GTK bar class that spawns the bar
Author: thnikk
"""
import gi
import os
from subprocess import check_output
import json
import common as c
import module
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib  # noqa


class Display:
    """ Display class """
    def __init__(self, config):
        self.display = Gdk.Display.get_default()
        self.display.connect("monitor-added", self.added)
        self.display.connect("monitor-removed", self.removed)
        self.config = config
        self.bars = []
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()

    def get_plugs(self):
        """ Get plugs from swaymsg """
        return [
            output['name'] for output in
            json.loads(
                check_output(["swaymsg", "-t", "get_outputs"]).decode('utf-8'))
            if output['active'] is True
        ]

    def get_monitors(self):
        """ Get monitor objects from gdk """
        return [
            self.display.get_monitor(n)
            for n in range(self.display.get_n_monitors())
        ]

    def removed(self, display, monitor):
        """ Remove bar from bar list when a monitor is removed """
        index = self.monitors.index(monitor)
        if self.bars[index]:
            self.bars[index].window.destroy()
        self.bars.remove(self.bars[index])

    def added(self, display, monitor):
        """ Draw a new bar when a monitor is added """
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()
        self.draw_bar(monitor)

    def draw_bar(self, monitor):
        """ Draw a bar on a monitor """
        index = self.monitors.index(monitor)
        if 'outputs' in list(self.config):
            if self.plugs[index] not in self.config['outputs']:
                self.bars.append(None)
                return
        bar = Bar(self.config, monitor, spacing=5)
        bar.populate()
        css_path = "/".join(__file__.split('/')[:-1]) + '/style.css'
        bar.css(css_path)
        # bar.css('style.css')
        bar.css('~/.config/pybar/style.css')
        bar.start()
        self.bars.append(bar)

    def draw_all(self):
        """ Initialize all monitors """
        for monitor in self.monitors:
            self.draw_bar(monitor)


class Bar:
    """ Bar class"""
    def __init__(self, config, monitor, spacing=0):
        self.window = Gtk.Window()
        self.config = config
        self.bar = c.box('h', style='bar', spacing=spacing)
        self.left = c.box('h', style='modules-left', spacing=spacing)
        self.center = c.box('h', style='modules-center', spacing=spacing)
        self.right = c.box('h', style='modules-right', spacing=spacing)
        self.bar.pack_start(self.left, 0, 0, 0)
        self.bar.set_center_widget(self.center)
        self.bar.pack_end(self.right, 0, 0, 0)
        self.window.add(self.bar)
        self.monitor = monitor

    def populate(self):
        """ Populate bar with modules """
        for section_name, section in {
            "modules-left": self.left,
            "modules-center": self.center,
            "modules-right": self.right,
        }.items():
            for name in self.config[section_name]:
                section.add(module.module(name, self.config))

    def css(self, file):
        """ Load CSS from file """
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(os.path.expanduser(file))
            screen = Gdk.Screen.get_default()
            style_context = Gtk.StyleContext()
            style_context.add_provider_for_screen(
                screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        except GLib.GError as e:
            filename = f"/{'/'.join(e.message.split('/')[1:]).split(':')[0]}"
            if '.config/pybar' not in filename:
                c.print_debug(
                    f"Failed to load CSS from {filename}",
                    name='pybar', color="red")
            pass

    def modules(self, modules):
        """ Add modules to bar """
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.get_style_context().add_class("bar")

        for index, position in enumerate(["left", "center", "right"]):
            section = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            section.get_style_context().add_class(position)
            for item in modules[index]:
                section.pack_start(item(), False, False, 0)
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
        GtkLayerShell.set_monitor(self.window, self.monitor)

        # Reserve part of screen
        GtkLayerShell.auto_exclusive_zone_enable(self.window)

        self.window.show_all()
