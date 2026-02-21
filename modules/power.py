#!/usr/bin/python3 -u
"""
Description: Power module refactored for unified state
Author: thnikk
"""
import common as c
from subprocess import Popen
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Power(c.BaseModule):
    SCHEMA = {
        'sway_lock': {
            'type': 'string',
            'default': 'swaylock',
            'label': 'Sway Lock Command',
            'description': 'Command to lock the screen in Sway'
        },
        'hyprland_lock': {
            'type': 'string',
            'default': 'hyprlock',
            'label': 'Hyprland Lock Command',
            'description': 'Command to lock the screen in Hyprland'
        }
    }

    def fetch_data(self):
        """ Power module doesn't really have data but we follow the pattern """
        return {"icon": ""}

    def power_action(self, _btn, command):
        """ Action for power menu buttons """
        import shlex
        self.module.get_popover().popdown()  # Dismiss before action
        if isinstance(command, str):
            command = shlex.split(command)
        Popen(command)

    def build_popover(self):
        """ Build power menu popover """
        main_box = c.box('v', spacing=30)

        is_hyprland = getattr(self, 'wm', 'sway') == 'hyprland'

        lock_cmd = self.config.get('hyprland_lock', ["hyprlock"]) if is_hyprland else self.config.get('sway_lock', ["swaylock"])
        logout_cmd = ["hyprctl", "dispatch", "exit"] if is_hyprland else ["swaymsg", "exit"]
        blank_cmd = [
            "swayidle", "-w",
            "timeout", "3", 'hyprctl dispatch dpms off',
            "resume", 'hyprctl dispatch dpms on && pkill swayidle'
        ] if is_hyprland else [
            "swayidle", "-w",
            "timeout", "3", 'swaymsg "output * power off"',
            "resume", 'swaymsg "output * power on" && pkill swayidle'
        ]

        buttons = {
            "Lock  ": lock_cmd,
            "Log out  ": logout_cmd,
            "Blank Displays ": blank_cmd,
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
        self.module = m
        self.bar = bar
        self.wm = bar.display.wm
        m.set_widget(self.build_popover())

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Power UI doesn't really change """
        widget.set_visible(True)


module_map = {
    'power': Power
}
