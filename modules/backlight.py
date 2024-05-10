#!/usr/bin/python3 -u
"""
Description: Backlight module
Author: thnikk
"""
import common as c
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def set_backlight(widget):
    """ Action for backlight slider """
    with open(
        '/sys/class/backlight/intel_backlight/brightness',
        'w', encoding='utf-8'
    ) as file:
        file.write(str(round(widget.get_value())))


def widget(cache):
    """ Backlight widget """
    main_box = c.box('h', style='small-widget')
    main_box.add(c.label('', style='inner-box'))
    level = c.slider(cache['brightness'], 10, cache['max_brightness'])
    level.connect('value-changed', set_backlight)
    main_box.pack_start(level, 1, 1, 0)
    return main_box


def module(config=None):
    """ Backlight module """
    module = c.Module()
    c.add_style(module, 'module-fixed')
    module.icon.set_label('')

    def scroll_action(button, event):
        """ Scroll action """
        info = get_brightness()
        if event.direction == Gdk.ScrollDirection.UP:
            if info['brightness'] < info['max_brightness']:
                info['brightness'] = round(
                    info['brightness'] + (info['max_brightness'] * 0.01))
            else:
                info['brighntess'] = info['max_brightness']
        elif event.direction == Gdk.ScrollDirection.DOWN:
            if info['brightness'] > (info['max_brightness'] * 0.01):
                info['brightness'] = round(
                    info['brightness'] - (info['max_brightness'] * 0.01))
            else:
                info['brighntess'] = round(info['max_brightness'] * 0.01)
        with open(
            "/sys/class/backlight/intel_backlight/brightness", 'w',
            encoding='utf-8'
        ) as file:
            file.write(f"{round(info['brightness'])}")
        update_module(info)
    module.connect('scroll-event', scroll_action)

    def get_brightness():
        base_path = "/sys/class/backlight/intel_backlight"
        if not os.path.exists(base_path):
            return False
        info = {}
        for item in ["brightness", "max_brightness"]:
            with open(f'{base_path}/{item}', 'r', encoding='utf-8') as file:
                info[item] = int(file.read())
        return info

    def update_module(info=None):
        if not info:
            info = get_brightness()
        if not module.get_active():
            module.set_widget(widget(info))
        percentage = round((info['brightness']/info['max_brightness'])*100)
        module.text.set_label(f'{percentage}%')
        return True

    if update_module(get_brightness()):
        GLib.timeout_add(1000, update_module)
        return module
