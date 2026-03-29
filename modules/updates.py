#!/usr/bin/python3 -u
"""
Description: Package updates module refactored for unified state
Author: thnikk
"""
import weakref
import subprocess
import concurrent.futures
import shutil
from subprocess import Popen
import common as c
import gi
gi.require_version('Gtk', '4.0')  # noqa


class Updates(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 300,
            'label': 'Update Interval',
            'description': 'Seconds between update checks',
            'min': 60,
            'max': 3600
        },
        'terminal': {
            'type': 'string',
            'default': 'kitty',
            'label': 'Terminal',
            'description': (
                'Terminal emulator for running updates. '
                'Include flags if needed (e.g. "ghostty -e").'
            )
        },
        'alerts': {
            'type': 'list',
            'default': [],
            'label': 'Alerts',
            'description': 'List of packages to prioritize in package list'
        },
        'aur_helper': {
            'type': 'choice',
            'default': 'paru',
            'label': 'AUR Helper',
            'description': (
                'AUR helper used to check and install updates. '
                'Auto-detected if not set.'
            ),
            'choices': ['paru', 'yay']
        }
    }

    # Pixel height of a single package row, used to size scroll boxes.
    ITEM_HEIGHT = 45

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

    def get_output(
        self, command, seperator, values, empty_error, alerts
    ) -> list:
        """ Get formatted command output """
        try:
            result = subprocess.run(command, capture_output=True)
            # Treat the empty_error exit code as "no updates", not a
            # failure. Any other non-zero code means the command failed.
            if result.returncode not in (0, empty_error):
                output = []
            else:
                output = result.stdout.decode('utf-8').splitlines()
        except FileNotFoundError:
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

    def fetch_data(self):
        """ Fetch updates data """
        alerts = self.config.get(
            'alerts', ["linux", "discord", "qemu", "libvirt"])
        terminal = self.config.get('terminal', 'kitty')

        # Detect which supported helpers are installed.
        supported = ['paru', 'yay']
        installed = [h for h in supported if shutil.which(h)]

        # Use the configured value if set, otherwise auto-detect.
        # If only one helper is installed, use it. If both are installed,
        # fall back to paru. If none are found, fall back to paru so the
        # command fails gracefully via FileNotFoundError in get_output.
        configured = self.config.get('aur_helper')
        if configured in supported:
            aur_helper = configured
        elif len(installed) == 1:
            aur_helper = installed[0]
        else:
            aur_helper = 'paru'

        # Copy manager_config and substitute the configured AUR helper.
        # The class-level dict is never modified.
        manager_config = dict(self.manager_config)
        manager_config["AUR"] = {
            **manager_config["AUR"],
            "command": [aur_helper, "-Qum"],
            "update_command": f"{aur_helper} -Syua",
        }

        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=len(manager_config))
        package_managers = {name: {} for name in manager_config}

        for name, info in manager_config.items():
            thread = pool.submit(
                self.get_output, info["command"], info["seperator"],
                info["values"], info["empty_error"], alerts)
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

    def update_packages(self, _btn, data, widget):
        widget.get_popover().popdown()
        commands = [
            info['command']
            for manager, info in data['managers'].items()
            if info['packages']
        ] + [
            'echo "Packages updated, press enter to close terminal."',
            'read x']
        process = Popen(
            data['terminal'].split() + ['sh', '-c', '; '.join(commands)]
        )

        # Monitor process completion in a thread
        def monitor_completion():
            process.wait()  # Block until terminal closes
            c.print_debug(
                "Update terminal closed, forcing refresh",
                color='green'
            )
            import module
            module.force_update(self.name)

        import threading
        monitor_thread = threading.Thread(
            target=monitor_completion, daemon=True
        )
        monitor_thread.start()

    def click_link(self, _btn, url):
        Popen(['xdg-open', url])

    def calc_visible_counts(self, counts, min_items=4, total_slots=12):
        """ Compute per-manager visible item counts dynamically.

        Each manager gets at least min(count, min_items) slots. Remaining
        slots are distributed evenly among unsatisfied managers; when the
        remainder is odd, the topmost unsatisfied manager gets the extra.
        """
        alloc = [min(c, min_items) for c in counts]
        remaining = total_slots - sum(alloc)

        while remaining > 0:
            # Managers that still have packages beyond their allocation
            unsatisfied = [
                i for i, c in enumerate(counts) if alloc[i] < c
            ]
            if not unsatisfied:
                break
            per = remaining // len(unsatisfied)
            leftover = remaining % len(unsatisfied)
            for i in unsatisfied:
                alloc[i] += per
            # Topmost unsatisfied manager gets the extra slot
            if leftover:
                alloc[unsatisfied[0]] += leftover
            remaining = 0

        return alloc

    def build_popover(self, widget, data):
        """ Build popover for updates """
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Updates', style='heading'))

        urls = {
            "Pacman": "https://archlinux.org/packages/",
            "AUR": "https://aur.archlinux.org/packages/",
            "Flatpak": "https://flathub.org/apps/search?q=",
        }

        content_box = c.box('v', spacing=20)
        # Expand to put update button at the bottom of the widget
        content_box.set_vexpand(True)

        # Only consider managers that have packages, preserving
        # manager_config order (which is also the widget display order).
        active_managers = [
            (manager, info)
            for manager, info in data['managers'].items()
            if info['packages']
        ]
        counts = [len(info['packages']) for _, info in active_managers]
        visible_counts = self.calc_visible_counts(counts)

        for (manager, info), visible in zip(active_managers, visible_counts):
            packages = info['packages']
            manager_box = c.box('v', spacing=10)
            heading = c.label(
                f"{manager} ({len(packages)} updates)",
                style='title', ha='start')
            manager_box.append(heading)
            packages_box = c.box('v')

            for package in packages:
                package_box = c.box('h', style='inner-box', spacing=20)
                package_label = c.button(
                    package[0], style='minimal', length=20)
                if manager in urls:
                    package_label.connect(
                        'clicked', self.click_link,
                        f'{urls[manager]}{package[0]}')
                package_box.append(package_label)
                package_box.append(
                    c.label(
                        package[1], style='green-fg', ha='end', he=True,
                        length=10))
                packages_box.append(package_box)
                if package != packages[-1]:
                    packages_box.append(c.sep('h'))

            # Height is driven by the computed visible count so that
            # managers with fewer updates leave room for others.
            vsgb = c.VScrollGradientBox(
                packages_box, gradient_size=60,
                max_height=visible * self.ITEM_HEIGHT)
            c.add_style(vsgb, 'box')
            manager_box.append(vsgb)
            content_box.append(manager_box)

        main_box.append(content_box)

        if data['total']:
            update_button = c.button(' Update all', style='normal')
            update_button.connect(
                'clicked', self.update_packages, data, widget)
            main_box.append(update_button)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_visible(False)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            widget.set_visible(False)
            return
        total = data.get('total', 0)
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(total))

        if not widget.get_active():
            # Optimization: Don't rebuild popover if data hasn't changed
            compare_data = data.copy()
            compare_data.pop('timestamp', None)

            if getattr(widget, 'last_popover_data', None) == compare_data:
                return

            widget.last_popover_data = compare_data
            widget.set_widget(self.build_popover(widget, data))


module_map = {
    'updates': Updates
}
