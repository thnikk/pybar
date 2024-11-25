#!/usr/bin/python3 -u
"""
Description: Waybar module for package updates
Author: thnikk
"""
import subprocess
import concurrent.futures
import json
from datetime import datetime
import common as c

# You can add whatever package manager you want here with the appropriate
# command. Change the seperator and values to get the package and version from
# each line.
manager_config = {
    "Pacman": {
        "command": ["checkupdates"],
        "update_command": "sudo pacman -Syu",
        "seperator": ' ',
        "empty_error": 2,
        "values": [0, -1]
    },
    "AUR": {
        "command": ["paru", "-Qum"],
        "update_command": "paru -Syua",
        "seperator": ' ',
        "empty_error": 1,
        "values": [0, -1]
    },
    "Apt": {
        "command": ["apt", "list", "--upgradable"],
        "update_command": "sudo apt update && sudo apt upgrade",
        "seperator": ' ',
        "empty_error": 1,
        "values": [0, 1]
    },
    "Flatpak": {
        "command": ["flatpak", "remote-ls", "--updates"],
        "update_command": "flatpak update",
        "seperator": '\t',
        "empty_error": 0,
        "values": [0, 2]
    },
}


def get_output(command, seperator, values, empty_error, alerts) -> list:
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
            line.split(seperator)[value].split('/')[0]
            for value in values
        ]
        for line in output
        if len(line.split(seperator)) > 1
    ]
    return split_output


def get_total(package_managers) -> int:
    """ Get total number of updates """
    return sum(len(packages) for packages in package_managers.values())


def module(config={}) -> None:
    """ Module """

    if 'alerts' not in list(config):
        config['alerts'] = ["linux", "discord", "qemu", "libvirt"]
    if 'terminal' not in list(config):
        config['terminal'] = 'kitty'

    pool = concurrent.futures.ThreadPoolExecutor(
        max_workers=len(manager_config))
    # Initialize dictionary first to set the order based on the config
    package_managers = {name: {} for name in manager_config}
    # Get output for each package manager
    for name, info in manager_config.items():
        thread = pool.submit(
            get_output, info["command"], info["seperator"], info["values"],
            info["empty_error"], config["alerts"])
        package_managers[name]["packages"] = thread.result()
        package_managers[name]["command"] = info["update_command"]
    pool.shutdown(wait=True)

    # Create variable for output
    packages = [manager['packages'] for manager in package_managers.values()]
    num = 0
    for group in packages:
        num += len(group)

    if num:
        text = f" {num}"
    else:
        text = ""

    output = {
        "text": text,
        "widget": {
            "managers": package_managers,
            "terminal": config["terminal"]
        }
    }

    # Print for waybar
    module = c.Module()
    module.icon.set_label("")
    module.text.set_label(f"{num}")
    module.set_widget('Updates')

    for manager, packages in package_managers.items():
        if not packages["packages"]:
            continue
        manager_box = c.box('v', spacing=10)
        title = c.label(manager, he=True, ha='start')
        manager_box.append(title)
        package_box = c.box('v', style='split-container')
        for package in packages["packages"]:
            item_box = c.box('h', style='split-box')
            item_box.append(c.label(
                f"{package[0]}", he=True, ha='start'))
            item_box.append(c.label(f"{package[1]}"))
            package_box.append(item_box)
            if package != packages["packages"][-1]:
                package_box.append(c.sep('v'))
        manager_box.append(package_box)
        module.widget_content.append(manager_box)

    module.widget_content.append(
        c.label(' Update all', he=True, ha='center', style='button')
    )

    return module
