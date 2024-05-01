#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import concurrent.futures
import common as c
from bar import Bar
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

    modules_center = [
        waybar.module(name) for name in config["modules-center"]
    ]

    try:
        icons = config["workspaces"]
    except KeyError:
        icons = {}
    modules_left = [
        waybar.module(name) for name in config["modules-left"]
    ] + [
        sway.module(icons)
    ]

    pybar = Bar(spacing=5)
    pybar.css('style.css')
    for module in modules_left:
        pybar.left.pack_end(module, 0, 0, 0)
    for module in modules_center:
        pybar.center.pack_start(module, 0, 0, 0)
    for module in modules_right:
        pybar.right.pack_start(module, 0, 0, 0)

    # default = Gdk.Display.get_default()
    # for num in range(Gdk.Display.get_n_monitors(default)):
    #     monitor = Gdk.Display.get_monitor(default, num)
    #     GtkLayerShell.set_monitor(pybar.window, monitor)
    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
