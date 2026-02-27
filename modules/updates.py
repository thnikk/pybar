#!/usr/bin/python3 -u
"""
Description: Package updates module refactored for unified state
Author: thnikk
"""
import weakref
import subprocess
import concurrent.futures
from subprocess import Popen
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


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
            'description': 'Terminal emulator for running updates'
        },
        'alerts': {
            'type': 'list',
            'default': [],
            'label': 'Alerts',
            'description': 'List of packages to prioritize in package list'
        }
    }

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
        self, command, seperator, values, _empty_error, alerts
    ) -> list:
        """ Get formatted command output """
        try:
            output = subprocess.run(
                command, check=True,
                capture_output=True).stdout.decode('utf-8').splitlines()
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

    def fetch_data(self):
        """ Fetch updates data """
        alerts = self.config.get(
            'alerts', ["linux", "discord", "qemu", "libvirt"])
        terminal = self.config.get('terminal', 'kitty')

        pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=len(self.manager_config))
        package_managers = {name: {} for name in self.manager_config}

        for name, info in self.manager_config.items():
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
        process = Popen([data['terminal'], 'sh', '-c', '; '.join(commands)])

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

        for manager, info in data['managers'].items():
            packages = info['packages']
            if not packages:
                continue
            manager_box = c.box('v', spacing=10)
            heading = c.label(
                f"{manager} ({len(packages)} updates)",
                style='title', ha='start')
            manager_box.append(heading)
            packages_box = c.box('v', style='box')

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

            manager_box.append(packages_box)
            content_box.append(manager_box)

        scroll_box = c.scroll(height=400, style='scroll')
        scroll_box.set_overflow(Gtk.Overflow.HIDDEN)
        scroll_box.set_child(content_box)
        main_box.append(scroll_box)

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
