#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import concurrent.futures
import sway
import config as Config
from bar import Display
import modules
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, GLib  # noqa


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    config = Config.load()

    try:
        for name, info in config['modules'].items():
            executor.submit(
                modules.cache, name, info['command'], info['interval'])
    except KeyError:
        pass

    executor.submit(sway.cache)

    display = Display(config)
    display.hook()
    display.draw_all()
    Gtk.main()


if __name__ == "__main__":
    main()
