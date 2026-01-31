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


class Power(c.BaseModule):
    SCHEMA = {
        'lock': {
            'type': 'string',
            'default': 'swaylock',
            'label': 'Lock Command',
            'description': 'Command to lock the screen'
        },
        'log_out': {
            'type': 'string',
            'default': 'swaymsg exit',
            'label': 'Log Out Command',
            'description': 'Command to log out'
        }
    }

    def fetch_data(self):
        """ Power module doesn't really have data but we follow the pattern """
        return {"icon": ""}

    def power_action(self, _btn, command):
        """ Action for power menu buttons """
        run(command, check=False, capture_output=False)

    def build_popover(self):
        """ Build power menu popover """
        main_box = c.box('v', spacing=30)

        buttons = {
            "Lock  ": self.config.get("lock", ["swaylock"]),
            "Log out  ": self.config.get("log_out", ["swaymsg", "exit"]),
            "Suspend  ": ["systemctl", "suspend"],
            "Reboot  ": ["systemctl", "reboot"],
            "Reboot to UEFI  ": ["systemctl", "reboot", "--firmware-setup"],
            "Shut down  ": ["systemctl", "poweroff"],
        }

        power_box = c.box('v', style='box')
        power_box.set_overflow(Gtk.Overflow.HIDDEN)

        for icon, command in buttons.items():
            btn = c.button(label=icon, ha='fill', style='power-item')
            btn.get_child().set_halign(Gtk.Align.END)
            btn.set_cursor_from_name("pointer")
            btn.connect('clicked', self.power_action, command)

            if icon == list(buttons)[0]:
                btn.get_style_context().add_class('rounded-top')
            if icon == list(buttons)[-1]:
                btn.get_style_context().add_class('rounded-bottom')

            power_box.append(btn)
            if icon != list(buttons)[-1]:
                power_box.append(c.sep('h'))

        main_box.append(power_box)
        return main_box

    def create_widget(self, bar):
        """ Create power module widget """
        m = c.Module(True, False)
        m.set_position(bar.position)
        m.set_icon('')
        m.set_visible(True)
        m.set_widget(self.build_popover())

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        """ Power UI doesn't really change """
        widget.set_visible(True)


module_map = {
    'power': Power
}
