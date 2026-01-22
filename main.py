#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import threading
import argparse
import config as Config
from bar import Display
import common as c
import module
import cache
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


def on_activate(app, config):
    display = Display(config, app)
    # Draw all bars
    display.draw_all()


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument('-C', '--config', type=str, default='~/.config/pybar',
                        help="Configuration path")
    args, unknown = parser.parse_known_args()
    return args


def main():
    """ Main function """
    args = parse_args()
    config = Config.load(args.config)

    # Get a set of all used modules
    unique = set(
        config['modules-left'] +
        config['modules-center'] +
        config['modules-right']
    )

    # Set the cache directory if it's not specified in the config
    if "cache" not in list(config):
        config["cache"] = '~/.cache/pybar'

    # Start module threads to cache module output
    for name in unique:
        # Load the module config if it exists
        if name in list(config['modules']):
            module_config = config['modules'][name]
        else:
            module_config = {}

        # Set the interval if it's not specified
        if 'interval' not in list(module_config):
            module_config['interval'] = 60

        # Load waybar-style modules if a command is given
        if 'command' in list(module_config):
            c.print_debug(
                f'Starting thread for {name}', 'cache-waybar',
                color='green')
            thread = threading.Thread(
                target=module.cache, args=(
                    module_config['command'],
                    module_config['interval'],
                    config['cache']))
            thread.daemon = True
            thread.start()
        # Otherwise, load a built-in module
        else:
            thread = threading.Thread(
                target=cache.cache, args=(
                    name, module_config, config['cache']))
            thread.daemon = True
            thread.start()

    # Create display object
    app = Gtk.Application(application_id='org.thnikk.pybar')
    app.connect('activate', lambda app: on_activate(app, config))
    app.run()


if __name__ == "__main__":
    main()
