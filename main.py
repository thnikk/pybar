#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import os
import sys
import argparse
import logging

def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser(exit_on_error=False)
    parser.add_argument('-C', '--config', type=str, default='~/.config/pybar',
                        help="Configuration path")
    parser.add_argument('-n', '--new', action='store_true',
                        help="Allow multiple instances")
    parser.add_argument('-r', '--replace', action='store_true',
                        help="Replace existing instance")
    parser.add_argument('-s', '--settings', action='store_true',
                        help="Launch settings window")
    parser.add_argument('-l', '--log-level', type=str, default='WARNING',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Set the application logging level")
    parser.add_argument('-g', '--gtk-log-level', type=str, default='WARNING',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help="Set the GTK/GLib logging level")
    args, unknown = parser.parse_known_args()
    return args

# Parse early to set environment variables and log level
args = parse_args()

# Set GTK debug env var if GTK debug is requested
if args.gtk_log_level.upper() == 'DEBUG':
    os.environ['G_MESSAGES_DEBUG'] = 'all'

from ctypes import CDLL
try:
    CDLL('libgtk4-layer-shell.so')
except Exception:
    pass

import threading
import traceback
import config as Config
from bar import Display
import common as c
import module
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gio, Adw, GLib  # noqa


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


def setup_logging(app_level=logging.WARNING, gtk_level=logging.WARNING):
    """ Setup logging to file and stderr """
    log_dir = os.path.expanduser('~/.cache/pybar')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    log_file = os.path.join(log_dir, 'pybar.log')

    # Root level must be the minimum to catch all requested logs
    root_level = min(app_level, gtk_level)

    # Configure logging
    logging.basicConfig(
        level=root_level,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),
            logging.StreamHandler(sys.stderr)
        ]
    )

    # Redirect stdout and stderr to logger
    stdout_logger = logging.getLogger('STDOUT')
    stderr_logger = logging.getLogger('STDERR')
    stdout_logger.setLevel(app_level)
    stderr_logger.setLevel(app_level)

    sys.stdout = StreamToLogger(stdout_logger, logging.INFO, sys.stdout)
    sys.stderr = StreamToLogger(stderr_logger, logging.ERROR, sys.stderr)

    # Set default level for all app loggers (those not starting with GLib domains)
    # This is a bit tricky with basicConfig, but we can set the levels of specific loggers later
    # For now, we'll rely on the fact that most modules use their own names.

    # Suppress verbose connection pool logging
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Redirect GLib/GTK logs to Python logging
    def glib_log_handler(domain, level, message, user_data):
        levels = {
            GLib.LogLevelFlags.LEVEL_DEBUG: logging.DEBUG,
            GLib.LogLevelFlags.LEVEL_INFO: logging.INFO,
            GLib.LogLevelFlags.LEVEL_MESSAGE: logging.INFO,
            GLib.LogLevelFlags.LEVEL_WARNING: logging.WARNING,
            GLib.LogLevelFlags.LEVEL_CRITICAL: logging.ERROR,
            GLib.LogLevelFlags.LEVEL_ERROR: logging.CRITICAL,
        }
        py_level = levels.get(level & GLib.LogLevelFlags.LEVEL_MASK, logging.INFO)
        
        # Only log if it meets the gtk_level requirement
        if py_level >= gtk_level:
            logging.getLogger(domain or "GLib").log(py_level, message)

    # Connect the handler for common GTK/GLib domains
    for domain in [None, "Gtk", "Gdk", "GLib", "Gio", "Adw"]:
        GLib.log_set_handler(domain, GLib.LogLevelFlags.LEVEL_MASK | GLib.LogLevelFlags.FLAG_FATAL | GLib.LogLevelFlags.FLAG_RECURSION, glib_log_handler, None)

    return log_file


def on_activate(app, config, debug_gc=True):
    if hasattr(app, 'started') and app.started:
        return
    app.started = True

    # Hold application to prevent exit when no monitors are connected
    app.hold()

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
        app.display = Display(config, app, debug_gc=debug_gc)
        # Draw all bars
        app.display.draw_all()
    except Exception:
        logging.error("Failed to activate application", exc_info=True)
        sys.exit(1)


def launch_settings(config_path):
    """Launch settings window"""
    from settings.window import SettingsApplication
    app = SettingsApplication(config_path)
    app.run([])


def main():
    """ Main function """
    # Handle settings mode
    if args.settings:
        launch_settings(os.path.expanduser(args.config))
        return

    # log_level was parsed early
    app_log_level = getattr(logging, args.log_level.upper(), logging.WARNING)
    gtk_log_level = getattr(logging, args.gtk_log_level.upper(), logging.WARNING)
    log_file = setup_logging(app_log_level, gtk_log_level)
    logging.info(f"Starting pybar, logging to {log_file}")

    # Register bundled fonts
    fonts_dir = c.get_resource_path('fonts')
    if os.path.exists(fonts_dir):
        c.register_fonts(fonts_dir)

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
    app.connect('activate', lambda app: on_activate(app, config, True))

    # Use an empty list for argv to prevent GTK from parsing custom args
    app.run([])


if __name__ == "__main__":
    main()
