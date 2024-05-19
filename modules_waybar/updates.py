#!/usr/bin/python3 -u
"""
Description: Waybar module for package updates
Author: thnikk
"""
import subprocess
import concurrent.futures
import json
import time
from datetime import datetime
import os

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
    "Apt": {
        "command": ["apt", "list", "--upgradable"],
        "separator": ' ',
        "empty_error": 1,
        "values": [0, 1]
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
        except (subprocess.CalledProcessError, FileNotFoundError):
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


def get_total(package_managers) -> int:
    """ Get total number of updates """
    return sum(len(packages) for packages in package_managers.values())


def module(config) -> None:
    """ Module """
    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=len(manager_config))
    # Initialize dictionary first to set the order based on the config
    package_managers = {name: [] for name in manager_config}
    # Get output for each package manager
    for name, info in manager_config.items():
        thread = pool.submit(
            get_output, info["command"], info["separator"], info["values"],
            info["empty_error"])
        package_managers[name] = thread.result()
    pool.shutdown(wait=True)

    # Create variable for output
    total = get_total(package_managers)
    if total:
        text = f" {total}"
    else:
        text = ""

    output = {
        "text": text,
        "tooltip": datetime.now().timestamp(),
        "widget": package_managers
    }
    # Print for waybar
    return output


def main():
    """ Main function """
    print(json.dumps(module({}), indent=4))


if __name__ == "__main__":
    main()
