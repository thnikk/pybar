#!/usr/bin/python3 -u
"""
Description: Package updates module refactored for unified state
Author: thnikk
"""
import subprocess
import concurrent.futures
from subprocess import Popen
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

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
    try:
        output = subprocess.run(command, check=True, capture_output=True).stdout.decode('utf-8').splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        output = []
        
    move = []
    for alert in alerts:
        for line in output:
            if alert in line:
                move.append(line)
    for line in move:
        output.remove(line)
        output.insert(0, line)
        
    split_output = [
        [line.split(seperator)[value].split('/')[0] for value in values]
        for line in output if len(line.split(seperator)) > 1
    ]
    return split_output

def fetch_data(config):
    """ Fetch updates data """
    alerts = config.get('alerts', ["linux", "discord", "qemu", "libvirt"])
    terminal = config.get('terminal', 'kitty')
    
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=len(manager_config))
    package_managers = {name: {} for name in manager_config}
    
    for name, info in manager_config.items():
        thread = pool.submit(get_output, info["command"], info["seperator"], info["values"], info["empty_error"], alerts)
        package_managers[name]["packages"] = thread.result()
        package_managers[name]["command"] = info["update_command"]
    pool.shutdown(wait=True)
    
    total = sum(len(m['packages']) for m in package_managers.values())
    
    return {
        "total": total,
        "managers": package_managers,
        "terminal": terminal,
        "text": f" {total}" if total else ""
    }

def create_widget(bar, config):
    """ Create updates widget """
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    """ Update updates UI """
    if not data:
        module.set_visible(False)
        return
    total = data['total']
    module.set_label(data['text'])
    module.set_visible(bool(total))
    
    if not module.get_active():
        module.set_widget(build_popover(module, data))

def build_popover(module, data):
    """ Build popover for updates """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Updates', style='heading'))

    urls = {
        "Pacman": "https://archlinux.org/packages/",
        "AUR": "https://aur.archlinux.org/packages/",
        "Flatpak": "https://flathub.org/apps/search?q=",
    }

    commands = [
        info['command']
        for manager, info in data['managers'].items()
        if info['packages']
    ] + ['echo "Packages updated, press enter to close terminal."', 'read x']

    def update_packages(btn):
        module.get_popover().popdown()
        Popen([data['terminal'], 'sh', '-c', '; '.join(commands)])

    def click_link(btn, url):
        Popen(['xdg-open', url])

    content_box = c.box('v', spacing=20)

    for manager, info in data['managers'].items():
        packages = info['packages']
        if not packages:
            continue
        manager_box = c.box('v', spacing=10)
        heading = c.label(f"{manager} ({len(packages)} updates)", style='title', ha='start')
        manager_box.append(heading)
        packages_box = c.box('v', style='box')
        
        for package in packages:
            package_box = c.box('h', style='inner-box', spacing=20)
            package_label = c.button(package[0], style='minimal', length=25)
            if manager in urls:
                package_label.connect('clicked', click_link, f'{urls[manager]}{package[0]}')
            package_box.append(package_label)
            package_box.append(c.label(package[1], style='green-fg', ha='end', he=True, length=15))
            packages_box.append(package_box)
            if package != packages[-1]:
                packages_box.append(c.sep('h'))

        manager_box.append(packages_box)
        content_box.append(manager_box)

    scroll_box = c.scroll(height=400)
    scroll_box.set_child(content_box)
    main_box.append(scroll_box)

    if data['total']:
        update_button = c.button(' Update all', style='normal')
        update_button.connect('clicked', update_packages)
        main_box.append(update_button)

    return main_box
