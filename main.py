#!/usr/bin/python3 -u
"""
Description: Loads the config and spawns the bar
Author: thnikk
"""
import concurrent.futures
import sway
import pulse
import config as Config
from bar import Display
import module
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk  # noqa


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    config = Config.load()

    unique = set(
        config['modules-left'] +
        config['modules-center'] +
        config['modules-right']
    )

    for name in unique:
        try:
            module_config = config['modules'][name]
            executor.submit(
                module.cache, name,
                module_config['command'],
                module_config['interval'])
        except KeyError:
            pass

    if 'workspaces' in unique:
        executor.submit(sway.cache)
    if 'volume' in unique:
        executor.submit(pulse.update)

    display = Display(config)
    display.hook()
    display.draw_all()
    Gtk.main()


if __name__ == "__main__":
    main()
