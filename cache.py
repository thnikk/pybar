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
from modules_waybar import updates
from modules_waybar import xdrip
from modules_waybar import weather
from modules_waybar import vm
from modules_waybar import privacy
from modules_waybar import systemd

functions = {
    "git": git.module,
    "network": network.module,
    "updates": updates.module,
    "xdrip": xdrip.module,
    "weather": weather.module,
    "vm": vm.module,
    "privacy": privacy.module,
    "systemd": systemd.module,
}

try:
    from modules_waybar import sales
    functions['sales'] = sales.module
except ModuleNotFoundError as e:
    c.print_debug(f'{e}', color='yellow', name='cache-builtin')
try:
    from modules_waybar import ups
    functions['ups'] = ups.module
except ModuleNotFoundError as e:
    c.print_debug(f'{e}', color='yellow', name='cache-builtin')
try:
    from modules_waybar import resin
    functions['resin'] = resin.module
except ModuleNotFoundError as e:
    c.print_debug(f'{e}', color='yellow', name='cache-builtin')


def cache(name, config, cache_dir='~/.cache/pybar'):
    """ Save command output to cache file """

    # Skip if name isn't in functions
    if name not in list(functions):
        return

    c.print_debug(
        f'Starting thread for {name}', 'cache-builtin', color='green')

    while True:
        cache_dir = os.path.expanduser(cache_dir)
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        output = functions[name](config)

        # Don't write to file if module returned nothing
        if not output:
            continue

        with open(f'{cache_dir}/{name}.json', 'w', encoding='utf-8') as file:
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
