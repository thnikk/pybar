#!/usr/bin/python3 -u
"""
Description: Battery module
Author: thnikk
"""
import common as c
from glob import glob
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def fetch_data(config):
    """ Get battery data """
    info = {}
    full = 0
    now = 0
    for path in glob('/sys/class/power_supply/BAT*'):
        battery_info = {}
        for file in ["energy_now", "energy_full"]:
            try:
                with open(f"{path}/{file}", 'r', encoding='utf-8') as f:
                    value = int(f.read())
                    battery_info[file] = value
                    if file == 'energy_now':
                        now += value
                    elif file == 'energy_full':
                        full += value
            except FileNotFoundError:
                pass
        if battery_info:
            info[path.split('/')[-1]] = battery_info

    ac_online = 0
    try:
        with open('/sys/class/power_supply/AC/online', 'r', encoding='utf-8') as file:
            ac_online = int(file.read().strip())
    except FileNotFoundError:
        pass

    percentage = round((now/full)*100) if full > 0 else 0
    return {
        "percentage": percentage,
        "ac_online": ac_online,
        "devices": info
    }


def build_popover_content(data):
    """ Build popover for battery """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Battery', style='heading'))

    outer_box = c.box('v', spacing=10)
    outer_box.append(c.label('Devices', style='title', ha='start'))
    battery_box = c.box('v', style='box')

    devices = list(data.get('devices', {}).items())
    for i, (device, info) in enumerate(devices):
        device_box = c.box('h', style='inner-box', spacing=10)
        percentage = round((
            info['energy_now'] / info['energy_full']
        )*100) if info['energy_full'] > 0 else 0

        level = Gtk.LevelBar.new_for_interval(0, 100)
        level.set_min_value(0)
        level.set_max_value(100)
        level.set_value(percentage)

        device_box.append(c.label(device))
        level.set_hexpand(True)
        level.set_valign(Gtk.Align.CENTER)
        device_box.append(level)

        pct_label = c.label(f'{percentage}%')
        device_box.append(pct_label)
        battery_box.append(device_box)

        if i != len(devices) - 1:
            battery_box.append(c.sep('h'))
    outer_box.append(battery_box)
    main_box.append(outer_box)
    return main_box


def create_widget(bar, config):
    """ Battery module widget """
    module = c.Module()
    module.set_position(bar.position)
    c.add_style(module, 'module-fixed')
    module.set_icon('')
    module.popover_widgets = []
    return module


def update_ui(module, data):
    """ Update battery UI """
    icons = ['', '', '', '', '']
    percentage = data['percentage']
    icon_index = int(percentage // (100 / len(icons)))
    icon_index = min(icon_index, len(icons) - 1)

    module.set_visible(True)

    if data['ac_online']:
        module.set_icon('')
    else:
        module.set_icon(icons[icon_index])

    module.set_label(f'{percentage}%')

    # Update popover content
    if not module.get_active():
        module.set_widget(build_popover_content(data))
