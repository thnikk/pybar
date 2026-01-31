#!/usr/bin/python3 -u
"""
Description: Main GTK bar class that spawns the bar
Author: thnikk
"""
# For GTK4 Layer Shell to get linked before libwayland-client we must explicitly load it before importing with gi
from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

import gi
import os
from subprocess import run, CalledProcessError
import json
import time
import common as c
import module
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, GLib  # noqa


class Display:
    """ Display class """
    def __init__(self, config, app):
        self.app = app
        self.display = Gdk.Display.get_default()
        monitors = self.display.get_monitors()
        monitors.connect("items-changed", self.on_monitors_changed)
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
        monitors = self.display.get_monitors()
        return [monitors.get_item(i) for i in range(monitors.get_n_items())]

    def on_monitors_changed(self, model, position, removed, added):
        """ Handle monitor changes by redrawing all bars """
        # Destroy existing bars
        for bar in self.bars.values():
            bar.window.destroy()
        self.bars.clear()
        # Redraw all
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()
        self.draw_all()

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
        bar = Bar(self, monitor)
        bar.populate()
        css_path = c.get_resource_path('style.css')
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
    def __init__(self, display, monitor):
        self.window = Gtk.Window()
        self.window.set_application(display.app)
        self.display = display
        self.config = display.config
        self.spacing = self.config['spacing'] if 'spacing' in self.config \
            else 5
        try:
            self.position = display.config['position']
        except KeyError:
            self.position = 'bottom'
        self.bar = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        self.bar.get_style_context().add_class('bar')
        self.left = c.box('h', style='modules-left', spacing=self.spacing)
        self.center = c.box('h', style='modules-center', spacing=self.spacing)
        self.right = c.box('h', style='modules-right', spacing=self.spacing)
        self.bar.set_start_widget(self.left)
        self.bar.set_center_widget(self.center)
        self.bar.set_end_widget(self.right)
        self.window.set_child(self.bar)
        self.monitor = monitor

        # Add right-click handler for settings
        right_click = Gtk.GestureClick()
        right_click.set_button(3)  # Right click
        right_click.connect('pressed', self._on_right_click)
        self.bar.add_controller(right_click)

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
                    section.append(loaded_module)

    def _on_right_click(self, gesture, n_press, x, y):
        """ Handle right-click on bar to show context menu """
        # Check if the click is on a module widget (not blank bar area)
        # Get the widget at the click coordinates
        widget = self.bar.pick(x, y, Gtk.PickFlags.DEFAULT)

        # Only show menu if clicking on the bar itself or section boxes
        # (not on module widgets which have their own right-click handlers)
        if widget is not None:
            # Walk up the widget tree to check if we're on a module
            current = widget
            while current is not None:
                style_context = current.get_style_context()
                # Check if this is a module widget
                if (style_context.has_class('module') or
                        style_context.has_class('workspaces') or
                        style_context.has_class('tray-module')):
                    # Click is on a module, don't show bar context menu
                    return
                # Check if we've reached the bar/section level
                if (current == self.bar or
                        current == self.left or
                        current == self.center or
                        current == self.right):
                    break
                current = current.get_parent()

        # Create popover menu
        popover = Gtk.Popover()
        popover.set_position(Gtk.PositionType.TOP)
        popover.set_autohide(True)

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Settings button
        settings_btn = Gtk.Button(label='Settings')
        settings_btn.get_style_context().add_class('flat')
        settings_btn.connect('clicked', self._open_settings, popover)
        menu_box.append(settings_btn)

        # Reload button
        reload_btn = Gtk.Button(label='Reload')
        reload_btn.get_style_context().add_class('flat')
        reload_btn.connect('clicked', self._reload_bar, popover)
        menu_box.append(reload_btn)

        popover.set_child(menu_box)

        # Position the popover at click location
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_parent(self.bar)
        popover.popup()

    def _open_settings(self, btn, popover):
        """ Open settings window """
        popover.popdown()
        from settings import launch_settings_window
        config_path = self.display.app.config_path
        launch_settings_window(config_path)

    def _reload_bar(self, btn, popover):
        """ Reload the bar configuration """
        popover.popdown()
        # Trigger a config reload
        import config as Config
        new_config = Config.load(self.display.app.config_path)
        c.state_manager.update('config', new_config)
        c.state_manager.update('config_reload', True)

    def css(self, file):
        """ Load CSS from file """
        try:
            css_provider = Gtk.CssProvider()
            css_provider.load_from_path(os.path.expanduser(file))
            display = Gdk.Display.get_default()
            Gtk.StyleContext.add_provider_for_display(
                display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
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
            if position == "center":
                section.set_hexpand(True)
            for item in modules[index]:
                section.append(item())
            main.append(section)

        self.window.set_child(main)

    def start(self):
        """ Start bar """
        Gtk4LayerShell.init_for_window(self.window)

        pos = {
            "bottom": Gtk4LayerShell.Edge.BOTTOM,
            "top": Gtk4LayerShell.Edge.TOP
        }

        try:
            position = pos[self.position]
        except KeyError:
            position = pos['bottom']

        # Anchor and stretch to bottom of the screen
        Gtk4LayerShell.set_anchor(self.window, position, 1)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, 1)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.RIGHT, 1)

        # Set margin to make bar more readable for testing
        try:
            margin = self.config['margin']
        except KeyError:
            margin = 10

        Gtk4LayerShell.set_margin(
            self.window, Gtk4LayerShell.Edge.LEFT, margin)
        Gtk4LayerShell.set_margin(
            self.window, Gtk4LayerShell.Edge.RIGHT, margin)
        Gtk4LayerShell.set_margin(self.window, position, margin)

        # Set namespace based on config
        if 'namespace' in list(self.config):
            Gtk4LayerShell.set_namespace(self.window, self.config['namespace'])
        else:
            Gtk4LayerShell.set_namespace(self.window, 'pybar')

        Gtk4LayerShell.set_monitor(self.window, self.monitor)

        # Reserve part of screen
        Gtk4LayerShell.auto_exclusive_zone_enable(self.window)

        self.window.present()
