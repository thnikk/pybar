#!/usr/bin/python3 -u
from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

from modules import sway
from modules import updates
from modules import clock
from modules import pulse
from modules import weather
from modules import power_menu
from modules import test
import common as c
import threading
import time
import json
import os
import gi # noqa
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk # noqa
from gi.repository import Gtk4LayerShell as LayerShell # noqa


class Display():
    def __init__(self):
        self.display = Gdk.Display.get_default()
        self.display.connect("seat-added", self.added)
        self.display.connect("seat-removed", self.removed)
        self.monitors = self.get_monitors()

    def get_monitors(self):
        return {
            monitor.get_connector(): monitor
            for monitor in self.display.get_monitors()
        }

    def added(self, display, monitor):
        print('added')
        self.monitors[monitor.get_connector()] = monitor

    def removed(self, display, monitor):
        print('removed')
        self.monitors.pop(monitor.get_connector(), None)


class Bar():
    def __init__(self, app, monitor):
        self.app = app
        self.monitor = monitor

    def css(self, path):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(path)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def on_activate(self, _):
        self.window = Gtk.Window(application=self.app)

        LayerShell.init_for_window(self.window)
        LayerShell.set_monitor(self.window, self.monitor)
        # LayerShell.set_layer(self.window, LayerShell.Layer.OVERLAY)
        LayerShell.set_namespace(self.window, 'pybar-gtk4')
        # LayerShell.set_keyboard_mode(
        #     self.window,
        #     LayerShell.KeyboardMode.ON_DEMAND)

        LayerShell.set_anchor(self.window, LayerShell.Edge.BOTTOM, True)
        LayerShell.set_anchor(self.window, LayerShell.Edge.LEFT, True)
        LayerShell.set_anchor(self.window, LayerShell.Edge.RIGHT, True)

        LayerShell.set_margin(self.window, LayerShell.Edge.LEFT, 10)
        LayerShell.set_margin(self.window, LayerShell.Edge.RIGHT, 10)
        LayerShell.set_margin(self.window, LayerShell.Edge.BOTTOM, 10)
        LayerShell.set_keyboard_mode(
            self.window, LayerShell.KeyboardMode.NONE)
        LayerShell.set_layer(self.window, LayerShell.Layer.TOP)
        LayerShell.auto_exclusive_zone_enable(self.window)

        bar_box = Gtk.CenterBox.new()
        bar_box.add_css_class('bar')

        left_box = c.box('h', spacing=5)
        center_box = c.box('h', spacing=5)
        right_box = c.box('h', spacing=5)

        left_box.append(sway.module())
        # center_box.append(updates.module())
        # center_box.append(test.module())
        # right_box.append(weather.module())
        right_box.append(pulse.module())
        right_box.append(clock.module())
        right_box.append(test.module())
        right_box.append(power_menu.module())

        bar_box.set_start_widget(left_box)
        bar_box.set_center_widget(center_box)
        bar_box.set_end_widget(right_box)

        self.window.set_child(bar_box)
        self.window.present()

    def start(self):
        self.app.connect('activate', self.on_activate)


def main():
    display = Display()

    with open(
        os.path.expanduser('~/.config/pybar-gtk4/config.json'), 'r'
    ) as file:
        config = json.loads(file.read())

    while True:
        try:
            app = Adw.Application(application_id='com.github.pybar')
            settings = Gtk.Settings.get_default()
            settings.props.gtk_application_prefer_dark_theme = True
            bar = Bar(app, display.monitors[config['output']])
            bar.css('style.css')
            bar.start()
            app.run(None)
        except KeyError:
            pass
        time.sleep(1)


if __name__ == "__main__":
    main()
