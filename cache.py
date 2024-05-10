#!/usr/bin/python3 -u
"""
Description: Cache modules
Author: thnikk
"""
import os
import time
import json
import common as c
from modules_waybar import git
from modules_waybar import network
from modules_waybar import sales
from modules_waybar import updates
from modules_waybar import xdrip
from modules_waybar import weather
from modules_waybar import vm
from modules_waybar import ups
from modules_waybar import privacy


def cache(name, config):
    """ Save command output to cache file """
    functions = {
        "git": git.module,
        "network": network.module,
        "sales": sales.module,
        "updates": updates.module,
        "xdrip": xdrip.module,
        "weather": weather.module,
        "vm": vm.module,
        "ups": ups.module,
        "privacy": privacy.module,
    }

    # Skip if name isn't in functions
    if name not in list(functions):
        return

    while True:
        cache_dir = os.path.expanduser('~/.cache/pybar')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        output = functions[name](config)
        with open(
            os.path.expanduser(f'{cache_dir}/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            try:
                file.write(json.dumps(output, indent=4))
            except json.decoder.JSONDecodeError:
                c.print_debug('Failed to load module.', color='red', name=name)
                pass
        try:
            time.sleep(config['interval'])
        except KeyError:
            time.sleep(60)


def main():
    """ Main function """
    cache('privacy', {})


if __name__ == "__main__":
    main()
