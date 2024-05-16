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
from modules import sway_new
from modules import clock
from modules import battery
from modules import volume
from modules import volume_new
from modules import power
from modules import backlight
from modules import test
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def cache(name, command, interval, cache_dir='~/.cache/pybar'):
    """ Save command output to cache file """
    while True:
        # Create cache dir if it doesn't exist
        cache_dir = os.path.expanduser(cache_dir)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        # Expand user for all parts of command
        command = [os.path.expanduser(arg) for arg in command]
        # Try to get the output of the command
        try:
            output = check_output(command).decode()
        # Print a message if it fails to load
        except CalledProcessError:
            c.print_debug('Failed to load module.', color='red', name=name)
            pass
        # Save the output to a file
        with open(
            os.path.expanduser(f'{cache_dir}/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            file.write(output)
        # Wait for the interval specified in the module config
        time.sleep(interval)


def module(name, config):
    """ Waybar module """
    builtin = {
        'clock': clock.module,
        'workspaces': sway.module,
        'sway_new': sway_new.module,
        'volume': volume.module,
        'volume_new': volume_new.module,
        'backlight': backlight.module,
        'battery': battery.module,
        'power': power.module,
        'test': test.module
    }

    all_widgets = {
        "weather": widgets.weather,
        "genshin": widgets.hoyo,
        "hsr": widgets.hoyo,
        "resin": widgets.hoyo,
        "updates": widgets.updates,
        "git": widgets.git,
        "ups": widgets.ups,
        "xdrip": widgets.xdrip,
        "network": widgets.network,
        "sales": widgets.sales,
    }

    if "cache" not in list(config):
        config['cache'] = '~/.cache/pybar'

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
                os.path.expanduser(f'{config["cache"]}/{name}.json'),
                'r', encoding='utf-8'
            ) as file:
                output = json.loads(file.read())
        except json.decoder.JSONDecodeError as e:
            c.print_debug(e.args, name=f'module-{name}', color='red')
            return True
        except FileNotFoundError:
            c.print_debug("Cache does not exist for module.",
                          name=f'module-{name}', color='red')
            return True

        # I don't know why this would ever be a string
        if isinstance(output, str):
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
                    module.set_widget(
                        all_widgets[name](
                            name, module, output['widget']))
                except KeyError:
                    module.set_widget(
                        widgets.generic_widget(
                            name, module, output['widget']))
                module.set_tooltip_markup(str(output['tooltip']))
            try:
                output['widget']
                module.set_has_tooltip(False)
            except KeyError:
                pass
        except KeyError:
            pass

        # print(name, module.get_style_context().list_classes())

        # Set class
        try:
            if not output['class']:
                raise ValueError
            c.add_style(module, output['class'])
        except (KeyError, ValueError):
            for s in ['red', 'green', 'blue', 'orange', 'yellow', 'gray']:
                module.get_style_context().remove_class(s)
        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return module
