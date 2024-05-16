#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import concurrent.futures
import argparse
import config as Config
from bar import Display
import common as c
import module
import cache
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('-C', '--config', type=str, default='~/.config/pybar',
                        help="Configuration path")
    return parser.parse_args()


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
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
            executor.submit(
                module.cache, name,
                module_config['command'],
                module_config['interval'],
                config['cache']
            )
        # Otherwise, load a built-in module
        else:
            executor.submit(cache.cache, name, module_config, config['cache'])

    # Create display object
    display = Display(config)
    # Draw all bars
    display.draw_all()
    # Start main GTK thread
    Gtk.main()


if __name__ == "__main__":
    main()
