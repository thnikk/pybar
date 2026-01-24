#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import threading
import argparse
import traceback
import sys
import config as Config
from bar import Display
import common as c
import module
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


def on_activate(app, config):
    try:
        display = Display(config, app)
        # Draw all bars
        display.draw_all()
    except Exception:
        traceback.print_exc()
        sys.exit(1)


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

    # Start module threads
    for name in unique:
        # Load the module config if it exists
        module_config = config['modules'].get(name, {})

        # Set the interval if it's not specified
        if 'interval' not in module_config:
            module_config['interval'] = 5

        # Start the worker thread for this module
        module.start_worker(name, module_config)

    # Create display object
    app = Gtk.Application(application_id='org.thnikk.pybar')
    app.connect('activate', lambda app: on_activate(app, config))
    app.run()


if __name__ == "__main__":
    main()
