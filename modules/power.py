#!/usr/bin/python3 -u
"""
Description: Power module refactored for unified state
Author: thnikk
"""
import common as c
from subprocess import run
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def fetch_data(config):
    """ Power module doesn't really have data but we follow the pattern """
    return {"icon": ""}

def create_widget(bar, config):
    """ Create power module widget """
    module = c.Module(1, 0)
    module.set_position(bar.position)
    module.set_icon('')
    module.set_visible(True)
    module.set_widget(build_popover())
    return module

def update_ui(module, data):
    """ Power UI doesn't really change """
    module.set_visible(True)

def power_action(btn, command):
    """ Action for power menu buttons """
    run(command, check=False, capture_output=False)

def build_popover():
    """ Build power menu popover """
    main_box = c.box('v', spacing=30)
    
    buttons = {
        "Lock  ": ["swaylock"],
        "Log out  ": ["swaymsg", "exit"],
        "Suspend  ": ["systemctl", "suspend"],
        "Reboot  ": ["systemctl", "reboot"],
        "Reboot to UEFI  ": ["systemctl", "reboot", "--firmware-setup"],
        "Shut down  ": ["systemctl", "poweroff"],
    }

    power_box = c.box('v', style='box')
    for icon, command in buttons.items():
        btn = c.button(label=icon, ha='end', style='power-item')
        btn.connect('clicked', power_action, command)
        power_box.append(btn)
        if icon != list(buttons)[-1]:
            power_box.append(c.sep('h'))
            
    main_box.append(power_box)
    return main_box
