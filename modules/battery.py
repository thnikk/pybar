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


def widget(module, cache):
    """ Battery widget content """
    module.popover_widgets = []
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.add(c.label('Battery', style='heading'))

    outer_box = c.box('v', spacing=10)
    outer_box.add(c.label('Devices', style='title', ha='start'))
    battery_box = c.box('v', style='box')
    
    devices = list(cache.get('devices', {}).items())
    for i, (device, info) in enumerate(devices):
        device_box = c.box('h', style='inner-box', spacing=10)
        percentage = round((
            info['energy_now'] / info['energy_full']
        )*100) if info['energy_full'] > 0 else 0
        
        level = Gtk.LevelBar().new_for_interval(0, 100)
        level.set_min_value(0)
        level.set_max_value(100)
        level.set_value(percentage)
        
        device_box.append(c.label(device))
        level_box = c.box('v')
        level_box.append(level)
        device_box.append(level_box)
        
        pct_label = c.label(f'{percentage}%')
        device_box.append(pct_label)
        battery_box.add(device_box)
        
        module.popover_widgets.append({
            'name': device,
            'level': level,
            'label': pct_label
        })
        
        if i != len(devices) - 1:
            battery_box.add(c.sep('h'))
    outer_box.add(battery_box)
    main_box.add(outer_box)
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

    if data['ac_online']:
        module.set_icon('')
    else:
        module.set_icon(icons[icon_index])
    
    module.set_label(f'{percentage}%')
    
    if not module.get_active():
        module.set_widget(widget(module, data))
    else:
        # Live update
        devices = data.get('devices', {})
        for w in module.popover_widgets:
            if w['name'] in devices:
                info = devices[w['name']]
                p = round((info['energy_now'] / info['energy_full'])*100) if info['energy_full'] > 0 else 0
                w['level'].set_value(p)
                w['label'].set_text(f'{p}%')
