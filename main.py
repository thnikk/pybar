#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import concurrent.futures
import argparse
import sway
import pulse
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

    unique = set(
        config['modules-left'] +
        config['modules-center'] +
        config['modules-right']
    )

    for name in unique:
        if name in list(config['modules']):
            module_config = config['modules'][name]
        else:
            module_config = {}
        if 'interval' not in list(module_config):
            module_config['interval'] = 60
        if 'command' in list(module_config):
            c.print_debug(
                f'Starting thread for {name}', 'cache-waybar',
                color='green')
            executor.submit(
                module.cache, name,
                module_config['command'],
                module_config['interval'])
        else:
            executor.submit(cache.cache, name, module_config)

    if 'workspaces' in unique:
        executor.submit(sway.cache)
    if 'volume' in unique:
        executor.submit(pulse.update)

    display = Display(config)
    display.draw_all()
    Gtk.main()


if __name__ == "__main__":
    main()
