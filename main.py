#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
from ctypes import CDLL
try:
    CDLL('libgtk4-layer-shell.so')
except Exception:
    pass

import threading
import argparse
import traceback
import sys
import os
import logging
import config as Config
from bar import Display
import common as c
import module
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk  # noqa


def setup_logging():
    """ Setup logging to file and stderr """
    log_dir = os.path.expanduser('~/.cache/pybar')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, 'pybar.log')

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler(sys.stderr)
        ]
    )
    # Suppress verbose connection pool logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return log_file


def on_activate(app, config):
    try:
        app.display = Display(config, app)
        # Draw all bars
        app.display.draw_all()
    except Exception:
        logging.error("Failed to activate application", exc_info=True)
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
    log_file = setup_logging()
    logging.info(f"Starting pybar, logging to {log_file}")
    
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
