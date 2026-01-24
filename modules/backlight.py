#!/usr/bin/python3 -u
"""
Description: Backlight module
Author: thnikk
"""
import common as c
import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def get_brightness_info():
    base_path = "/sys/class/backlight/intel_backlight"
    if not os.path.exists(base_path):
        # Try generic if intel doesn't exist
        base_path = "/sys/class/backlight/acpi_video0"
        if not os.path.exists(base_path):
            return None
    info = {}
    for item in ["brightness", "max_brightness"]:
        with open(f'{base_path}/{item}', 'r', encoding='utf-8') as file:
            info[item] = int(file.read())
    info['path'] = base_path
    return info


def fetch_data(config):
    """ Get backlight data """
    return get_brightness_info()


def set_backlight(widget, path):
    """ Action for backlight slider """
    try:
        with open(f'{path}/brightness', 'w', encoding='utf-8') as file:
            file.write(str(round(widget.get_value())))
    except PermissionError:
        c.print_debug("Permission denied to write to brightness file", color='red')


def widget_content(cache):
    """ Backlight widget content """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Backlight', style='heading'))
    
    outer_box = c.box('h', style='box')
    outer_box.add(c.label('', style='inner-box'))
    level = c.slider(cache['brightness'], 10, cache['max_brightness'])
    level.connect('value-changed', set_backlight, cache['path'])
    outer_box.append(level)
    main_box.append(outer_box)
    return main_box


def create_widget(bar, config):
    """ Backlight module """
    module = c.Module()
    module.set_position(bar.position)
    c.add_style(module, 'module-fixed')
    module.icon.set_label('')

    def scroll_action(button, event):
        """ Scroll action """
        smooth, x, y = event.get_scroll_deltas()
        smooth_dir = x + (y * -1)
        info = get_brightness_info()
        if not info:
            return
        m, b = info['max_brightness'], info['brightness']

        if (
            event.direction == Gdk.ScrollDirection.UP or
            event.direction == Gdk.ScrollDirection.RIGHT or
            (smooth and smooth_dir > 0)
        ):
            b = round(b + (m * 0.01))
        elif (
            event.direction == Gdk.ScrollDirection.DOWN or
            event.direction == Gdk.ScrollDirection.LEFT or
            (smooth and smooth_dir < 0)
        ):
            b = round(b - (m * 0.01))

        # Max/min values
        b = round(max(min(b, m), m * 0.01))

        try:
            with open(f"{info['path']}/brightness", 'w', encoding='utf-8') as file:
                file.write(f'{b}')
        except PermissionError:
            pass
        
        # Trigger an immediate local update for better responsiveness
        info['brightness'] = b
        update_ui(module, info)
        
    module.connect('scroll-event', scroll_action)
    return module


def update_ui(module, data):
    """ Update backlight UI """
    if not data:
        module.set_visible(False)
        return
    
    if not module.get_active():
        module.set_widget(widget_content(data))
        
    percentage = round((data['brightness']/data['max_brightness'])*100)
    module.text.set_label(f'{percentage}%')
    module.set_visible(True)
