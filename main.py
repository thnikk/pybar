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
from gi.repository import Gtk, Gio  # noqa


class StreamToLogger:
    """ Redirect a stream (stdout/stderr) to a logger """
    def __init__(self, logger, log_level, stream):
        self.logger = logger
        self.log_level = log_level
        self.stream = stream

    def write(self, buf):
        if buf.strip():
            for line in buf.rstrip().splitlines():
                self.logger.log(self.log_level, line.rstrip())
        self.stream.write(buf)

    def flush(self):
        self.stream.flush()


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

    # Redirect stdout and stderr to logger
    stdout_logger = logging.getLogger('STDOUT')
    stderr_logger = logging.getLogger('STDERR')
    sys.stdout = StreamToLogger(stdout_logger, logging.INFO, sys.stdout)
    sys.stderr = StreamToLogger(stderr_logger, logging.ERROR, sys.stderr)

    # Suppress verbose connection pool logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    return log_file


def on_activate(app, config):
    if hasattr(app, 'started') and app.started:
        return
    app.started = True

    # Get a set of all used modules
    unique = set(
        config['modules-left'] +
        config['modules-center'] +
        config['modules-right']
    )

    # Start module threads
    for name in unique:
        # Load the module config if it exists
        module_config = config['modules'].get(name, {})

        # Start the worker thread for this module
        module.start_worker(name, module_config)

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
    parser.add_argument('-n', '--new', action='store_true',
                        help="Allow multiple instances")
    parser.add_argument('-r', '--replace', action='store_true',
                        help="Replace existing instance")
    args, unknown = parser.parse_known_args()
    return args


def main():
    """ Main function """
    log_file = setup_logging()
    logging.info(f"Starting pybar, logging to {log_file}")

    # Register bundled fonts
    fonts_dir = c.get_resource_path('fonts')
    if os.path.exists(fonts_dir):
        c.register_fonts(fonts_dir)

    args = parse_args()
    config = Config.load(args.config)
    c.state_manager.update('config', config)

    # Set the cache directory if it's not specified in the config
    if "cache" not in list(config):
        config["cache"] = '~/.cache/pybar'

    # Create display object
    flags = Gio.ApplicationFlags.ALLOW_REPLACEMENT
    if args.new:
        flags |= Gio.ApplicationFlags.NON_UNIQUE
    if args.replace:
        flags |= Gio.ApplicationFlags.REPLACE

    app = Gtk.Application(
        application_id='org.thnikk.pybar',
        flags=flags
    )
    app.config_path = args.config  # Store config path for settings window
    app.connect('activate', lambda app: on_activate(app, config))
    
    # Use an empty list for argv to prevent GTK from parsing custom args
    app.run([])


if __name__ == "__main__":
    main()
