#!/usr/bin/python3 -u
"""
Description: Power module
Author: thnikk
"""
import common as c
from subprocess import run


def module(bar, config=None):
    """ Power module """
    module = c.Module(1, 0)
    module.set_position(bar.position)
    module.icon.set_label('')

    def power_action(button, command, widget):
        """ Action for power menu buttons """
        widget.popdown()
        run(command, check=False, capture_output=False)

    buttons = {
        "Lock  ": ["swaylock"],
        "Log out  ": ["swaymsg", "exit"],
        "Suspend  ": ["systemctl", "suspend"],
        "Reboot  ": ["systemctl", "reboot"],
        "Reboot to UEFI  ": ["systemctl", "reboot", "--firmware-setup"],
        "Shut down  ": ["systemctl", "poweroff"],
    }

    widget = c.Widget()
    power_box = c.box('v', style='box')
    for icon, command in buttons.items():
        button = c.button(label=icon, ha='end', style='power-item')
        button.connect('clicked', power_action, command, widget)
        power_box.append(button)
        if icon != list(buttons)[-1]:
            power_box.append(c.sep('h'))

    widget.box.append(power_box)
    widget.draw()
    module.set_popover(widget)

    return module
