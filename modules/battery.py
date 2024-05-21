#!/usr/bin/python3 -u
"""
Description: Battery module
Author: thnikk
"""
import common as c
from glob import glob
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def widget(cache):
    """ Battery widget """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.add(c.label('Battery', style='heading'))

    outer_box = c.box('v', spacing=10)
    outer_box.add(c.label('Devices', style='title', ha='start'))
    battery_box = c.box('v', style='box')
    for device, info in cache.items():
        device_box = c.box('h', style='inner-box')
        percentage = str(round((
            info['energy_now'] / info['energy_full']
        )*100))
        device_box.pack_start(c.label(device), 0, 0, 0)
        device_box.pack_end(c.label(f'{percentage}%'), 0, 0, 0)
        battery_box.add(device_box)
        if device != list(cache)[-1]:
            battery_box.add(c.sep('h'))
    outer_box.add(battery_box)

    main_box.add(outer_box)

    return main_box


def module(config=None):
    """ Battery module """
    module = c.Module()
    c.add_style(module, 'module-fixed')
    module.icon.set_text('')
    icons = ['', '', '', '', '']

    def get_ac():
        """ Get AC status """
        with open(
            '/sys/class/power_supply/AC/online', 'r', encoding='utf-8'
        ) as file:
            return int(file.read().strip())

    def get_percent():
        """ Get combined battery percentage"""
        info = {}
        full = 0
        now = 0
        for path in glob('/sys/class/power_supply/BAT*'):
            battery_info = {}
            for file in ["energy_now", "energy_full"]:
                with open(f"{path}/{file}", 'r', encoding='utf-8') as f:
                    value = int(f.read())
                    battery_info[file] = value
                    if file == 'energy_now':
                        now += value
                    elif file == 'energy_full':
                        full += value
            info[path.split('/')[-1]] = battery_info
        if not module.get_active():
            module.set_widget(widget(info))
        percentage = round((now/full)*100)
        icon_index = int(percentage // (100 / len(icons)))
        if get_ac():
            module.icon.set_label('')
        else:
            try:
                module.icon.set_label(icons[icon_index])
            except IndexError:
                module.icon.set_label(icons[-1])
        module.text.set_label(f'{percentage}%')
        return True
    if get_percent():
        GLib.timeout_add(10000, get_percent)
        return module
