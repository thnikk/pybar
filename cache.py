#!/usr/bin/python3 -u
"""
Description: Cache modules
Author: thnikk
"""
import os
import time
import json
from datetime import datetime
import traceback
import common as c
from modules_waybar import git
from modules_waybar import network
from modules_waybar import updates
from modules_waybar import xdrip
from modules_waybar import weather
from modules_waybar import vm
from modules_waybar import systemd
from modules_waybar import sales
from modules_waybar import hass
from modules_waybar import power_supply

functions = {
    "git": git.module,
    "network": network.module,
    "updates": updates.module,
    "xdrip": xdrip.module,
    "weather": weather.module,
    "vm": vm.module,
    "systemd": systemd.module,
    "sales": sales.module,
    "hass": hass.module,
    "power_supply": power_supply.module,
}

try:
    from modules_waybar import ups
    functions['ups'] = ups.module
except ModuleNotFoundError as e:
    c.print_debug(f'{e}', color='yellow', name='cache-builtin')
except BaseException:
    c.print_debug(
        "Library import failed with error:", color='red', name='cache-ups')
    print(traceback.print_exc())

try:
    from modules_waybar import resin
    functions['resin'] = resin.module
except ModuleNotFoundError as e:
    c.print_debug(f'{e}', color='yellow', name='cache-builtin')
except BaseException:
    c.print_debug(
        "Library import failed with error:", color='red', name='cache-resin')
    print(traceback.print_exc())


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
        try:
            output = functions[name](config)
        except BaseException:
            c.print_debug(
                "Caught exception:", name=f"cache-{name}", color='red')
            print(traceback.format_exc())
            output = None

        # Don't write to file if module returned nothing
        if output:
            output['timestamp'] = datetime.now().timestamp()
            with open(
                f'{cache_dir}/{name}.json', 'w', encoding='utf-8'
            ) as file:
                try:
                    file.write(json.dumps(output, indent=4))
                except json.decoder.JSONDecodeError:
                    c.print_debug(
                        'Failed to load module.', color='red', name=name)

        try:
            time.sleep(config['interval'])
        except KeyError:
            time.sleep(60)


def main():
    """ Main function """
    cache('privacy', {})


if __name__ == "__main__":
    main()
