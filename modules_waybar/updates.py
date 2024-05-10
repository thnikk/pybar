#!/usr/bin/python3 -u
"""
Description: Waybar module for package updates
Author: thnikk
"""
import subprocess
import concurrent.futures
import json
import time
import os
from modules_waybar.common import print_debug, Cache, ellipse
import modules_waybar.tooltip as tt

# You can add whatever package manager you want here with the appropriate
# command. Change the separator and values to get the package and version from
# each line.
manager_config = {
    "Pacman": {
        "command": ["checkupdates"],
        "separator": ' ',
        "empty_error": 2,
        "values": [0, -1]
    },
    "AUR": {
        "command": ["paru", "-Qum"],
        "separator": ' ',
        "empty_error": 1,
        "values": [0, -1]
    },
    "Flatpak": {
        "command": ["flatpak", "remote-ls", "--updates"],
        "separator": '\t',
        "empty_error": 0,
        "values": [0, 2]
    },
}

# Alert for these packages
alerts = ["linux", "discord", "qemu", "libvirt"]


def get_output(command, separator, values, empty_error) -> list:
    """ Get formatted command output """
    # Get line-separated output
    while True:
        try:
            output = subprocess.run(
                command, check=True, capture_output=True
            ).stdout.decode('utf-8').splitlines()
        except subprocess.CalledProcessError as error:
            # Use cache if no updates or command isn't found
            if error.returncode != empty_error and error.returncode != 127:
                # Print errors to stderr
                print_debug(
                    f"[{error.returncode}] "
                    f"{vars(error)['stderr'].decode('utf-8').rstrip()}")
                raise ValueError from error
            # Otherwise set empty output
            output = []
        break
    # Find lines containing alerts
    move = []
    for alert in alerts:
        for line in output:
            if alert in line:
                move.append(line)
    # And move them to the front of the list
    for line in move:
        output.remove(line)
        output.insert(0, line)
    # Split each line into [package, version]
    split_output = [
        [
            line.split(separator)[value] for value in values
        ] for line in output
    ]
    return split_output


def get_tooltip(package_managers) -> str:
    """ Generate tooltip string """
    tooltip = []
    for name, packages in package_managers.items():
        # Skip if no packages
        if len(packages) == 0:
            continue
        # Add an extra list element to create a newline
        if tooltip and packages:
            tooltip.append('')
        # Create package list
        tooltip += [tt.heading(name)] + [
            f"{ellipse(package): <20} {tt.span(version[:10], 'green')}"
            for package, version in packages
        ][:30]
    return "\n".join(tooltip)


def get_total(package_managers) -> int:
    """ Get total number of updates """
    return sum(len(packages) for packages in package_managers.values())


def module(config) -> None:
    """ Module """
    cache = Cache(os.path.expanduser('~/.cache/updates.json'))
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=len(manager_config))
    try:
        # Initialize dictionary first to set the order based on the config
        package_managers = {name: [] for name in manager_config}
        # Get output for each package manager
        for name, info in manager_config.items():
            thread = pool.submit(
                get_output, info["command"], info["separator"], info["values"],
                info["empty_error"])
            package_managers[name] = thread.result()
        pool.shutdown(wait=True)
        cache.save(package_managers)
    except ValueError:
        time.sleep(5)
        print_debug('Loading data from cache file.')
        package_managers = cache.load()

    # Create variable for output
    total = get_total(package_managers)
    if total:
        text = f" {total}"
    else:
        text = ""

    output = {
        "text": text,
        "tooltip": get_tooltip(package_managers),
        "widget": package_managers
    }
    # Print for waybar
    return output


def main():
    """ Main function """
    print(json.dumps(module({}), indent=4))


if __name__ == "__main__":
    main()
