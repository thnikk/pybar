#!/usr/bin/python3 -u
"""
Description: Backlight module
Author: thnikk
"""
import gi
import time
import sys
import os
import common as c
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


class Backlight(c.BaseModule):
    SCHEMA = {
        'device': {
            'type': 'string',
            'default': '',
            'label': 'Backlight Device',
            'description': 'Device name (e.g., intel_backlight). Leave empty for auto.'
        },
        'interval': {
            'type': 'integer',
            'default': 5,
            'label': 'Update Interval',
            'description': 'Seconds between brightness checks',
            'min': 1,
            'max': 60
        }
    }

    def get_brightness_info(self, device=None):
        base_dir = "/sys/class/backlight"
        base_path = None

        if device:
            path = os.path.join(base_dir, device)
            if os.path.exists(path):
                base_path = path

        if not base_path:
            # Check commonly used backlight devices
            common_devices = ["intel_backlight", "acpi_video0"]
            for dev in common_devices:
                path = os.path.join(base_dir, dev)
                if os.path.exists(path):
                    base_path = path
                    break

        if not base_path and os.path.exists(base_dir):
            # Fallback to first available device
            try:
                devices = os.listdir(base_dir)
                if devices:
                    base_path = os.path.join(base_dir, devices[0])
            except OSError:
                pass

        if not base_path:
            c.print_debug(
                f"No backlight device found in {base_dir}", color='red')
            return {}

        info = {}
        try:
            for item in ["brightness", "max_brightness"]:
                with open(f'{base_path}/{item}', 'r', encoding='utf-8') as file:
                    info[item] = int(file.read().strip())
            info['path'] = base_path
            return info
        except Exception as e:
            c.print_debug(f"Error reading backlight info: {e}", color='red')
            return {}

    def fetch_data(self):
        """ Get backlight data """
        return self.get_brightness_info(self.config.get('device'))

    def set_backlight(self, widget, path):
        """ Action for backlight slider """
        try:
            with open(f'{path}/brightness', 'w', encoding='utf-8') as file:
                file.write(str(round(widget.get_value())))
        except PermissionError:
            c.print_debug(
                "Permission denied to write to brightness file", color='red')

    def widget_content(self, cache):
        """ Backlight widget content """
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Backlight', style='heading'))

        outer_box = c.box('h', style='box')
        outer_box.set_hexpand(True)
        outer_box.append(c.label('', style='inner-box'))

        level = c.slider(cache['brightness'], 10, cache['max_brightness'])
        level.set_hexpand(True)
        level.set_margin_end(10)
        level.connect('value-changed', self.set_backlight, cache['path'])

        outer_box.append(level)
        main_box.append(outer_box)
        return main_box

    def create_widget(self, bar):
        """ Backlight module """
        m = c.Module()
        m.set_position(bar.position)
        c.add_style(m, 'module-fixed')
        m.set_icon('')
        m.set_label('...')  # Set initial loading state
        m.set_visible(True)  # Ensure visible from start

        def scroll_action(_controller, _dx, dy):
            """ Scroll action """
            info = self.get_brightness_info(self.config.get('device'))
            if not info:
                return
            max_b, b = info['max_brightness'], info['brightness']

            # dy < 0 is scroll up (increase), dy > 0 is scroll down (decrease)
            if dy < 0:
                b = round(b + (max_b * 0.01))
            elif dy > 0:
                b = round(b - (max_b * 0.01))

            # Max/min values
            b = round(max(min(b, max_b), max_b * 0.01))

            try:
                with open(
                        f"{info['path']}/brightness", 'w',
                        encoding='utf-8') as file:
                    file.write(f'{b}')
            except PermissionError:
                pass

            # Trigger an immediate local update for better responsiveness
            info['brightness'] = b
            self.update_ui(m, info)

        # Add scroll controller
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect("scroll", scroll_action)
        m.add_controller(scroll_controller)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Update backlight UI """
        if not data:
            widget.set_label("No Dev")
            widget.set_visible(True)
            return

        if not widget.get_active():
            widget.set_widget(self.widget_content(data))

        percentage = round((data['brightness'] / data['max_brightness']) * 100)
        widget.set_label(f'{percentage}%')
        widget.set_visible(True)


module_map = {
    'backlight': Backlight
}
