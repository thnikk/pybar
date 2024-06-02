#!/usr/bin/python3 -u
"""
Description: Main GTK bar class that spawns the bar
Author: thnikk
"""
import gi
import os
from subprocess import run, CalledProcessError
import json
import time
from . import common as c
from . import module
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib  # noqa


class Display:
    """ Display class """
    def __init__(self, config):
        self.display = Gdk.Display.get_default()
        self.display.connect("monitor-added", self.added)
        self.display.connect("monitor-removed", self.removed)
        self.wm = self.get_wm()
        self.config = config
        self.bars = {}
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()

    def get_wm(self):
        try:
            run(['swaymsg', '-q'], check=True)
            return 'sway'
        except CalledProcessError:
            return 'hyprland'

    def get_plugs(self):
        """ Get plugs from swaymsg """
        if self.wm == 'sway':
            return [
                output['name'] for output in
                json.loads(run(
                    ["swaymsg", "-t", "get_outputs"],
                    check=True, capture_output=True
                ).stdout.decode('utf-8'))
                if output['active']
            ]
        else:
            return [
                output['name'] for output in
                json.loads(run(
                    ['hyprctl', '-j', 'monitors'],
                    check=True, capture_output=True
                ).stdout.decode('utf-8'))
                if not output['disabled']
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
        plug = self.plugs[index]
        if 'outputs' in list(self.config):
            if plug not in self.config['outputs']:
                return
        self.bars[plug].window.destroy()
        self.bars.pop(plug)

    def added(self, display, monitor):
        """ Draw a new bar when a monitor is added """
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()
        self.draw_bar(monitor)

    def draw_bar(self, monitor):
        """ Draw a bar on a monitor """
        try_count = 0
        while True:
            try:
                index = self.monitors.index(monitor)
                plug = self.plugs[index]
                break
            except IndexError:
                if try_count >= 3:
                    return
                time.sleep(1)
                try_count += 1
        if 'outputs' in list(self.config):
            if plug not in self.config['outputs']:
                return
        bar = Bar(self, monitor, spacing=5)
        bar.populate()
        css_path = "/".join(__file__.split('/')[:-1]) + '/style.css'
        bar.css(css_path)
        try:
            bar.css(self.config['style'])
        except KeyError:
            pass
        bar.start()
        self.bars[plug] = bar

    def draw_all(self):
        """ Initialize all monitors """
        for monitor in self.monitors:
            self.draw_bar(monitor)


class Bar:
    """ Bar class"""
    def __init__(self, display, monitor, spacing=0):
        self.window = Gtk.Window()
        self.display = display
        self.config = display.config
        try:
            self.position = display.config['position']
        except KeyError:
            self.position = 'bottom'
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
                loaded_module = module.module(self, name, self.config)
                if loaded_module:
                    section.add(loaded_module)

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

        pos = {
            "bottom": GtkLayerShell.Edge.BOTTOM,
            "top": GtkLayerShell.Edge.TOP
        }

        try:
            position = pos[self.position]
        except KeyError:
            position = pos['bottom']

        # Anchor and stretch to bottom of the screen
        GtkLayerShell.set_anchor(self.window, position, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.RIGHT, 1)

        # Set margin to make bar more readable for testing
        try:
            margin = self.config['margin']
        except KeyError:
            margin = 10

        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.LEFT, margin)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.RIGHT, margin)
        GtkLayerShell.set_margin(self.window, position, margin)

        # Set namespace based on config
        if 'namespace' in list(self.config):
            GtkLayerShell.set_namespace(self.window, self.config['namespace'])
        else:
            GtkLayerShell.set_namespace(self.window, 'pybar')

        GtkLayerShell.set_monitor(self.window, self.monitor)

        # Reserve part of screen
        GtkLayerShell.auto_exclusive_zone_enable(self.window)

        self.window.show_all()
