#!/usr/bin/python3 -u
"""
Description: Power module with list, grid, and wide-row menu styles
Author: thnikk
"""
import weakref
import common as c
from subprocess import Popen, run
import threading
import select
import time
import evdev
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib  # noqa


# Button definitions: (label, icon, command-key, danger, short)
# danger=True tints the icon red. short=True reduces cell padding.
# command-key maps to _get_commands().
_BUTTONS = [
    ("Lock",            "\uf023", "lock",     False, False),
    ("Log Out",         "\uf2f5", "logout",   False, False),
    ("Blank",           "\uf26c", "blank",    False, True),
    ("Suspend",         "\uf186", "suspend",  False, False),
    ("Reboot",          "\uf021", "reboot",   False, False),
    ("Reboot to UEFI",  "\uf2db", "uefi",     False, False),
    ("Shut Down",       "\uf011", "poweroff", True,  False),
]


class Power(c.BaseModule):
    SCHEMA = {
        'style': {
            'type': 'choice',
            'default': 'grid',
            'choices': ['grid', 'list', 'wide'],
            'label': 'Menu Style',
            'description': (
                'Visual layout of the power menu: '
                '"grid" (icon grid), "list" (compact list), '
                'or "wide" (rows with descriptions)'
            )
        },
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

    def __init__(self, name, config):
        super().__init__(name, config)
        self.blanking_active = False

    def fetch_data(self):
        """ Power module has no polled data; follow the pattern anyway """
        return {"icon": "\uf011"}

    def _get_commands(self):
        """ Build command map based on detected window manager """
        is_hyprland = getattr(self, 'wm', 'sway') == 'hyprland'
        lock_cmd = (
            self.config.get('hyprland_lock', 'hyprlock') if is_hyprland
            else self.config.get('sway_lock', 'swaylock')
        )
        logout_cmd = (
            ["hyprctl", "dispatch", "exit"] if is_hyprland
            else ["swaymsg", "exit"]
        )
        return {
            "lock":     lock_cmd,
            "logout":   logout_cmd,
            "blank":    "blank",
            "suspend":  ["systemctl", "suspend"],
            "reboot":   ["systemctl", "reboot"],
            "uefi":     ["systemctl", "reboot", "--firmware-setup"],
            "poweroff": ["systemctl", "poweroff"],
        }

    def power_action(self, _btn, command):
        """ Dismiss popover then execute power command """
        import shlex
        module = self._module_ref() if hasattr(self, '_module_ref') else None
        if module:
            popover = module.get_popover()
            if popover:
                popover.popdown()

        if command == "blank":
            self.blank_displays()
            return

        if isinstance(command, str):
            command = shlex.split(command)
        Popen(command)

    def blank_displays(self):
        """ Turn off displays and wake on next input event """
        if self.blanking_active:
            return
        self.blanking_active = True

        is_hyprland = getattr(self, 'wm', 'sway') == 'hyprland'
        off_cmd = (
            ["hyprctl", "dispatch", "dpms", "off"] if is_hyprland
            else ["swaymsg", "output * dpms off"]
        )
        on_cmd = (
            ["hyprctl", "dispatch", "dpms", "on"] if is_hyprland
            else ["swaymsg", "output * dpms on"]
        )

        def listener():
            devices = []
            try:
                for path in evdev.list_devices():
                    try:
                        dev = evdev.InputDevice(path)
                        caps = dev.capabilities()
                        # EV_KEY (1), EV_REL (2), EV_ABS (3)
                        if 1 in caps or 2 in caps or 3 in caps:
                            devices.append(dev)
                        else:
                            dev.close()
                    except (PermissionError, OSError):
                        continue

                if not devices:
                    run([
                        "notify-send", "Pybar Power Module",
                        "No input devices found or permission denied."
                    ])
                    return

                run(off_cmd)
                time.sleep(1)  # Grace period to avoid instant wake

                while True:
                    r, _, _ = select.select(devices, [], [])
                    if r:
                        break

                run(on_cmd)

            except PermissionError:
                run([
                    "notify-send", "Pybar Power Module",
                    "Permission denied accessing /dev/input. "
                    "Add user to 'input' group."
                ])
            except Exception as e:
                run([
                    "notify-send", "Pybar Power Module",
                    f"Error: {str(e)}"
                ])
            finally:
                for dev in devices:
                    dev.close()
                self.blanking_active = False

        threading.Thread(target=listener, daemon=True).start()

    # ── Layout builders ──────────────────────────────────────────────

    def _make_btn(self, command):
        """ Return a connected Gtk.Button for the given command key """
        btn = Gtk.Button()
        btn.set_cursor_from_name("pointer")
        btn.connect('clicked', self.power_action, command)
        return btn

    def _build_list(self, commands):
        """
        Compact stacked list: label on left, icon on right.
        Matches the existing 'box' / 'power-item' CSS classes.
        """
        outer = c.box('v', style='box')
        outer.set_overflow(Gtk.Overflow.HIDDEN)

        items = list(_BUTTONS)
        for i, (label, icon, key, danger, _short) in enumerate(items):
            btn = self._make_btn(commands[key])
            btn.get_style_context().add_class('power-item')

            icon_style = (
                'power-list-icon-danger' if danger
                else 'power-list-icon'
            )
            row = c.box('h', spacing=30)
            row.append(c.label(label, ha='start', he=True))
            row.append(c.label(icon, style=icon_style))
            btn.set_child(row)

            # Round only the first and last corners
            if i == 0:
                btn.get_style_context().add_class('rounded-top')
            if i == len(items) - 1:
                btn.get_style_context().add_class('rounded-bottom')

            outer.append(btn)
            if i < len(items) - 1:
                outer.append(c.sep('h'))

        return outer

    def _build_grid(self, commands):
        """
        3-column icon grid. Reboot and UEFI share one split cell:
        top half = reboot, bottom half = UEFI (smaller inline icon).
        """
        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(8)
        grid.set_row_homogeneous(False)
        grid.set_column_homogeneous(True)

        # Plain cells: everything except reboot, uefi, and poweroff
        plain = [b for b in _BUTTONS if b[2] not in ('reboot', 'uefi', 'poweroff')]

        col, row = 0, 0
        for label, icon, key, danger, short in plain:
            cell = self._grid_cell(label, icon, commands[key], danger, short)
            grid.attach(cell, col, row, 1, 1)
            col += 1
            if col > 2:
                col = 0
                row += 1

        # Split reboot/UEFI cell at current position
        split = self._grid_split_cell(commands)
        grid.attach(split, col, row, 1, 1)
        col += 1
        if col > 2:
            col = 0
            row += 1

        # Shut Down always last
        sd = next(b for b in _BUTTONS if b[2] == 'poweroff')
        shutdown_cell = self._grid_cell(
            sd[0], sd[1], commands[sd[2]], sd[3], sd[4]
        )
        grid.attach(shutdown_cell, col, row, 1, 1)

        return grid

    def _grid_cell(self, label_text, icon, command, danger=False, short=False):
        """ Single grid cell: icon above label, vertically centered """
        btn = self._make_btn(command)
        btn.get_style_context().add_class('power-grid-cell')
        if short:
            btn.get_style_context().add_class('power-grid-cell-short')

        icon_style = 'power-grid-icon-danger' if danger else 'power-grid-icon'
        inner = c.box('v', spacing=7)
        inner.set_valign(Gtk.Align.CENTER)
        inner.set_halign(Gtk.Align.CENTER)
        inner.append(c.label(icon, style=icon_style))
        lbl = c.label(label_text, style='power-grid-label', wrap=4)
        lbl.set_justify(Gtk.Justification.CENTER)
        inner.append(lbl)
        btn.set_child(inner)
        return btn

    def _grid_split_cell(self, commands):
        """
        Vertically split cell: top = Reboot, bottom = UEFI.
        UEFI half uses a smaller inline icon beside the label.
        """
        # Outer box clips to rounded corners
        outer = c.box('v')
        outer.get_style_context().add_class('power-grid-split')
        outer.set_overflow(Gtk.Overflow.HIDDEN)

        # Top half — Reboot (full icon + label, centered)
        reboot_btn = self._make_btn(commands['reboot'])
        reboot_btn.get_style_context().add_class('power-split-half')
        reboot_inner = c.box('v', spacing=5)
        reboot_inner.set_valign(Gtk.Align.CENTER)
        reboot_inner.set_halign(Gtk.Align.CENTER)
        reboot_inner.append(c.label("\uf021", style='power-grid-icon'))
        reboot_lbl = c.label("Reboot", style='power-grid-label')
        reboot_lbl.set_justify(Gtk.Justification.CENTER)
        reboot_inner.append(reboot_lbl)
        reboot_btn.set_child(reboot_inner)
        outer.append(reboot_btn)

        outer.append(c.sep('h'))

        # Bottom half — UEFI (small inline icon + label, centered)
        uefi_btn = self._make_btn(commands['uefi'])
        uefi_btn.get_style_context().add_class('power-split-half')
        uefi_inner = c.box('h', spacing=5)
        uefi_inner.set_valign(Gtk.Align.CENTER)
        uefi_inner.set_halign(Gtk.Align.CENTER)
        uefi_inner.append(c.label("\uf2db", style='power-split-icon-sm'))
        uefi_inner.append(c.label("UEFI", style='power-grid-label'))
        uefi_btn.set_child(uefi_inner)
        outer.append(uefi_btn)

        return outer

    def _build_wide(self, commands):
        """
        Wide rows: icon tile on left, name + subtitle on right.
        A separator divides session actions from power actions.
        """
        outer = c.box('v', spacing=4)

        # Session actions (no separator before)
        session_keys = {'lock', 'logout', 'blank'}
        # Power actions (preceded by separator)
        power_keys = {'suspend', 'reboot', 'uefi', 'poweroff'}

        is_hyprland = getattr(self, 'wm', 'sway') == 'hyprland'
        lock_subtitle = (
            self.config.get('hyprland_lock', 'hyprlock') if is_hyprland
            else self.config.get('sway_lock', 'swaylock')
        )
        subtitles = {
            "lock":     lock_subtitle,
            "logout":   "exit compositor",
            "blank":    "DPMS off",
            "suspend":  "systemctl suspend",
            "reboot":   "systemctl reboot",
            "uefi":     "--firmware-setup",
            "poweroff": "systemctl poweroff",
        }

        sep_added = False
        for label_text, icon, key, danger, _short in _BUTTONS:
            if key in power_keys and not sep_added:
                outer.append(c.sep('h'))
                sep_added = True

            btn = self._make_btn(commands[key])
            btn.get_style_context().add_class('power-wide-item')
            btn.set_halign(Gtk.Align.FILL)

            row = c.box('h', spacing=14)
            row.set_valign(Gtk.Align.CENTER)
            row.set_halign(Gtk.Align.START)

            # Icon tile
            icon_style = (
                'power-wide-icon-danger' if danger
                else 'power-wide-icon'
            )
            tile = c.box('v')
            tile.get_style_context().add_class('power-wide-tile')
            tile.set_valign(Gtk.Align.CENTER)
            tile.set_halign(Gtk.Align.CENTER)
            tile.set_size_request(34, 34)
            icon_lbl = c.label(icon, style=icon_style)
            icon_lbl.set_vexpand(True)
            icon_lbl.set_hexpand(True)
            icon_lbl.set_valign(Gtk.Align.CENTER)
            icon_lbl.set_halign(Gtk.Align.CENTER)
            tile.append(icon_lbl)
            row.append(tile)

            # Text column
            text_col = c.box('v', spacing=1)
            text_col.set_valign(Gtk.Align.CENTER)
            name_lbl = c.label(label_text, style='power-wide-name')
            name_lbl.set_halign(Gtk.Align.START)
            text_col.append(name_lbl)
            text_col.append(
                c.label(subtitles[key], style='power-wide-desc')
            )
            row.append(text_col)

            btn.set_child(row)
            outer.append(btn)

        return outer

    # ── Public interface ─────────────────────────────────────────────

    def build_popover(self):
        """ Build popover content for the configured style """
        commands = self._get_commands()
        style = self.config.get('style', 'grid')

        builders = {
            'list': self._build_list,
            'grid': self._build_grid,
            'wide': self._build_wide,
        }
        builder = builders.get(style, self._build_grid)

        main_box = c.box('v', spacing=10)
        main_box.append(builder(commands))
        return main_box

    def create_widget(self, bar):
        """ Create power module widget """
        m = c.Module(True, False)
        m.set_position(bar.position)
        m.set_icon('\uf011')
        m.set_visible(True)
        # Weak reference avoids keeping the widget alive past its time
        self._module_ref = weakref.ref(m)
        self.bar = bar
        self.wm = bar.display.wm
        m.set_widget(self.build_popover())

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Power UI is static; just ensure visibility """
        widget.set_visible(True)


module_map = {
    'power_menu': Power
}
alias_map = {
    'power': Power
}
