#!/usr/bin/python3 -u
"""
Description: Load module and popover widgets
Author: thnikk
"""
from subprocess import run, CalledProcessError
import json
import os
import time
from datetime import datetime
import gi
import common as c
import widgets
from modules import workspaces
from modules import clock
from modules import battery
from modules import volume
from modules import power
from modules import backlight
from modules import test
from modules import toggle
from modules import privacy
from modules import hass_2
from modules import mpc
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def cache(name, config, cache_dir='~/.cache/pybar'):
    """ Save command output to cache file """
    while True:
        # Create cache dir if it doesn't exist
        cache_dir = os.path.expanduser(cache_dir)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        # Expand user for all parts of command
        command = [os.path.expanduser(arg) for arg in config['command']]
        # Try to get the output of the command
        try:
            output = run(
                command, check=True, capture_output=True
            ).stdout.decode()
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
        time.sleep(config['interval'])


def module(bar, name, config):
    """ Waybar module """
    cacheless = {
        'clock': clock.module,
        'workspaces': workspaces.module,
        'volume': volume.module,
        'backlight': backlight.module,
        'battery': battery.module,
        'power': power.module,
        'test': test.module,
        'toggle': toggle.module,
        'privacy': privacy.module,
        'hass_2': hass_2.module,
        'mpc': mpc.module
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
        "power_supply": widgets.power_supply,
    }

    if "cache" not in list(config):
        config['cache'] = '~/.cache/pybar'

    try:
        module_config = config['modules'][name]
    except KeyError:
        module_config = {}

    module_type = module_config['type'] if 'type' in module_config else None

    if module_type and module_type in list(cacheless):
        return cacheless[module_type](bar, module_config)

    if not module_type and name in list(cacheless):
        return cacheless[name](bar, module_config)

    module = c.Module(0, 1)
    module.set_position(bar.position)
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
        except (json.decoder.JSONDecodeError, FileNotFoundError):
            return True

        if output['text'] != module.cache.text:
            if output['text']:
                module.text.set_label(output['text'])
                module.text.set_visible(True)
                module.set_visible(True)
            else:
                module.set_visible(False)
            module.cache.text = output['text']

        if 'tooltip' in output and output['tooltip'] != module.cache.tooltip:
            if output['tooltip']:
                module.set_tooltip_text(str(output['tooltip']))
                module.cache.tooltip = output['tooltip']

        if 'widget' in output:
            if (
                output['widget'] != module.cache.widget
                and not module.get_active()
            ):
                if 'type' in module_config:
                    widget = module_config['type']
                else:
                    widget = name
                if widget in list(all_widgets):
                    module.set_widget(
                        all_widgets[widget](
                            widget, module, output['widget']))
                else:
                    module.set_widget(
                        widgets.generic_widget(
                            widget, module, output['widget']))
                module.cache.widget = output['widget']

        # Override class and set to gray if module is stale
        module.reset_style()
        if 'interval' in module_config and 'timestamp' in output:
            if (
                datetime.now() -
                datetime.fromtimestamp(output['timestamp'])
            ).seconds > module_config['interval'] * 2:
                c.add_style(module, 'gray')

        # Set class
        if 'indicator' in config and config['indicator']:
            if 'class' in list(output):
                c.add_style(module.indicator, output['class'])
        else:
            if 'class' in list(output):
                c.add_style(module, output['class'])

        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return module
