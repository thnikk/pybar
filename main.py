#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import concurrent.futures
import argparse
import common as c
from bar import Bar
import clock
import sway
import waybar
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GLib


def load_config():
    """ Load config from file """
    config_path = os.path.expanduser('~/.config/pybar/')
    if not os.path.exists(config_path):
        return {"modules-right": [], "modules-center": [], "modules-left": []}
    with open(
        os.path.expanduser('~/.config/pybar/config.json'),
        'r', encoding='utf=8'
    ) as file:
        return json.loads(file.read())


def parse_args() -> argparse.ArgumentParser:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=int, default=None)
    return parser.parse_args()


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    args = parse_args()
    config = load_config()

    try:
        for name, info in config['modules'].items():
            executor.submit(
                waybar.cache, name, info['command'], info['interval'])
    except KeyError:
        pass

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

    pybar = Bar(args.output, spacing=5)
    pybar.css('style.css')
    for module in modules_left:
        pybar.left.pack_end(module, 0, 0, 0)
    for module in modules_center:
        pybar.center.pack_start(module, 0, 0, 0)
    for module in modules_right:
        pybar.right.pack_start(module, 0, 0, 0)

    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
