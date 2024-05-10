#!/usr/bin/python3 -u
"""
Description: Load module and popover widgets
Author: thnikk
"""
from subprocess import check_output, CalledProcessError
import json
import os
import time
import gi
import common as c
import widgets
from modules import sway
from modules import clock
from modules import battery
from modules import volume
from modules import power
from modules import backlight
from modules import test
# from modules_new import volume as volume_new
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def get_widget(name, info=None):
    """ Get widget box from appropriate widget """
    match name:
        case 'weather':
            return widgets.weather_widget(info)
        case 'genshin':
            return widgets.hoyo_widget(info, 'genshin')
        case 'hsr':
            return widgets.hoyo_widget(info, 'hsr')
        case 'updates':
            return widgets.updates_widget(info)
        case 'git':
            return widgets.git_widget(info)
        case 'ups':
            return widgets.ups_widget(info)
        case 'xdrip':
            return widgets.xdrip(info)
        case 'network':
            return widgets.network(info)
        case 'sales':
            return widgets.sales(info)
        case _:
            return widgets.generic_widget(name, info)


def cache(name, command, interval):
    """ Save command output to cache file """
    while True:
        cache_dir = os.path.expanduser('~/.cache/pybar')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        command = [os.path.expanduser(arg) for arg in command]
        with open(
            os.path.expanduser(f'{cache_dir}/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            try:
                file.write(check_output(command).decode())
            except CalledProcessError:
                c.print_debug('Failed to load module.', color='red', name=name)
                pass
        time.sleep(interval)


def module(name, config):
    """ Waybar module """
    builtin = {
        'clock': clock.module,
        'workspaces': sway.module,
        'volume': volume.module,
        'backlight': backlight.module,
        'battery': battery.module,
        'power': power.module,
        'test': test.module
    }

    if name in list(builtin):
        try:
            config = config['modules'][name]
        except KeyError:
            config = None
        return builtin[name](config)

    module = c.Module(0, 1)
    module.set_visible(False)
    module.set_no_show_all(True)

    def get_output():
        """ Create module using cache """
        # Load cache
        try:
            with open(
                os.path.expanduser(f'~/.cache/pybar/{name}.json'),
                'r', encoding='utf-8'
            ) as file:
                output = json.loads(file.read())
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            return True
        if module.text.get_label() == output['text']:
            return True

        # Set label
        if output['text']:
            module.set_visible(True)
            module.set_label(output['text'])
        else:
            if module.get_visible():
                module.set_visible(False)
                module.set_label('')
            return True

        # Set tooltip or popover
        try:
            if (
                module.get_tooltip_markup() != output['tooltip']
                and not module.get_active()
            ):
                try:
                    module.set_widget(get_widget(name, info=output['widget']))
                except KeyError:
                    pass
                module.set_tooltip_markup(output['tooltip'])
            try:
                output['widget']
                module.set_has_tooltip(False)
            except KeyError:
                pass
        except KeyError:
            pass

        # Set class
        try:
            if not output['class']:
                raise ValueError
            c.add_style(module, output['class'])
        except (KeyError, ValueError):
            for s in ['red', 'green', 'blue', 'orange', 'yellow']:
                module.get_style_context().remove_class(s)
        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return module
