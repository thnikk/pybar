#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import concurrent.futures
import common as c
import clock
import sway
import waybar
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GLib


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()

    with open(
        os.path.expanduser('~/.config/pybar/config.json'),
        'r', encoding='utf=8'
    ) as file:
        config = json.loads(file.read())

    for name, info in config['modules'].items():
        executor.submit(
            waybar.cache, name, info['command'], info['interval'])

    modules_right = [
        waybar.module(name) for name in config["modules-right"]
    ] + [
        clock.module()
    ]

    pybar = c.Bar(spacing=5)
    pybar.css('style.css')
    pybar.left.add(sway.module())
    for module in modules_right:
        pybar.right.pack_start(module, 0, 0, 0)

    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
