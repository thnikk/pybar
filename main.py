#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import common as c
import clock
import sway
import waybar
import concurrent.futures
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GLib


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()

    waybar_modules = {
        "genshin": {
            "command": [
                "~/.venv/hoyo-stats/bin/python",
                "~/.local/bin/bar/hoyo-stats.py", "-g", "genshin"],
            "interval": 300
        },
        "hsr": {
            "command": [
                "~/.venv/hoyo-stats/bin/python",
                "~/.local/bin/bar/hoyo-stats.py", "-g", "hsr"],
            "interval": 300
        },
        "weather": {
            "command": ["~/.local/bin/bar/weather-new.py", "94002", "-n"],
            "interval": 300
        },
        "ups": {
            "command": [
                "~/.local/bin/bar/ups.py", "0764", "0501", '-o', '160'],
            "interval": 3
        },
        "updates": {
            "command": ["~/.local/bin/bar/updates.py"],
            "interval": 300
        },
        "git": {
            "command": [
                "~/.local/bin/bar/git-updates.py",
                '~/Development/Git/waybar-modules'],
            "interval": 300
        },
    }

    for name, info in waybar_modules.items():
        executor.submit(
            waybar.cache, name, info['command'], info['interval'])

    modules_right = [
        waybar.module(name) for name in [
            'git', 'updates', 'ups', 'weather', 'genshin', 'hsr'
        ]
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
