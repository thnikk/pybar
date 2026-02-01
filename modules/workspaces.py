#!/usr/bin/python3 -u
"""
Description: Properly threaded workspace module refactored for unified state
Author: thnikk
"""
from subprocess import Popen, PIPE, STDOUT, DEVNULL, run, CalledProcessError
import socket
import json
import os
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa


class Workspaces(c.BaseModule):
    SCHEMA = {
        'icons': {
            'type': 'dict',
            'key_type': 'string',
            'value_type': 'string',
            'default': {},
            'label': 'Workspace Icons',
            'description': (
                'Map workspace numbers to custom icons')
        },
        'always_show_number': {
            'type': 'boolean',
            'default': False,
            'label': 'Always Show Number',
            'description': 'Show workspace number alongside icon'
        },
        'colorize_by_monitor': {
            'type': 'boolean',
            'default': False,
            'label': 'Colorize by Monitor',
            'description': (
                'Color workspaces based on which monitor they are on')
        }
    }

    def get_wm(self):
        try:
            run(['swaymsg', '-t', 'get_version'], capture_output=False,
                check=True, stdout=DEVNULL, stderr=DEVNULL)
            return 'sway'
        except CalledProcessError:
            return 'hypr'

    def get_workspaces_data(self, wm):
        """ Get current workspace info """
        if wm == 'sway':
            try:
                raw = json.loads(run(
                    ['swaymsg', '-t', 'get_workspaces'],
                    check=True, capture_output=True).stdout.decode('utf-8'))
                workspaces = [workspace['name'] for workspace in raw]
                workspaces.sort()
                focused = next((
                    workspace['name'] for workspace in raw
                    if workspace['focused']), None)
                monitors = sorted(
                    set(w['output'] for w in raw),
                    key=lambda x: x.lower())
                monitor_map = {
                    w['name']: str(monitors.index(w['output']) + 1)
                    for w in raw}
                return {
                    'workspaces': workspaces,
                    'focused': focused,
                    'monitors': monitor_map}
            except Exception:
                return None
        else:
            try:
                raw = json.loads(run(
                    ['hyprctl', '-j', 'workspaces'],
                    check=True, capture_output=True).stdout.decode('utf-8'))
                workspaces = [w['name'] for w in raw]
                focused = json.loads(run(
                    ['hyprctl', '-j', 'activeworkspace'],
                    check=True, capture_output=True
                ).stdout.decode('utf-8'))['name']
                monitors = sorted(
                    set(w['monitor'] for w in raw),
                    key=lambda x: x.lower())
                monitor_map = {
                    w['name']: str(monitors.index(w['monitor']) + 1)
                    for w in raw}
                return {
                    "workspaces": workspaces,
                    "focused": focused,
                    "monitors": monitor_map}
            except Exception:
                return None

    def run_worker(self):
        """ Worker thread for workspaces """
        wm = self.get_wm()

        def update():
            data = self.get_workspaces_data(wm)
            if data:
                c.state_manager.update(self.name, data)

        update()

        if wm == 'sway':
            while True:
                with Popen(
                        ['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'],
                        stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
                    if p.stdout:
                        for _line in p.stdout:
                            update()
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                try:
                    sock.connect(
                        f"{os.getenv('XDG_RUNTIME_DIR')}/hypr/"
                        f"{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/"
                        ".socket2.sock")
                    while True:
                        data = sock.recv(1024).decode('utf-8')
                        if 'focus' in data or 'workspace' in data:
                            update()
                except Exception:
                    pass

    def switch_workspace(self, n):
        if self.get_wm() == 'sway':
            run(['swaymsg', 'workspace', 'number', str(n)],
                stdout=DEVNULL, stderr=DEVNULL, check=False)
        else:
            run(['hyprctl', 'dispatch', 'workspace', str(n)],
                stdout=DEVNULL, stderr=DEVNULL, check=False)

    def create_widget(self, bar):
        """ Create workspaces widget """
        box = c.box('h', style='workspaces')
        box.set_halign(Gtk.Align.CENTER)
        box.buttons = []
        box.indicators = []

        for n in range(1, 11):
            label = self.config.get('icons', {}).get(
                str(n),
                self.config.get('icons', {}).get(
                    'default', str(n)))
            if (label != str(n) and
                    self.config.get('always_show_number', False)):
                label = f"{n} {label}"
            button = c.button(label=None, style='workspace')
            button.set_visible(False)
            button.connect(
                'clicked', lambda _b, wn=n: self.switch_workspace(wn))
            box.buttons.append(button)
            box.append(button)

            overlay = Gtk.Overlay()
            button.set_child(overlay)

            label_widget = Gtk.Label(label=label)
            overlay.set_child(label_widget)

            indicator = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            indicator.get_style_context().add_class('indicator')
            indicator.set_halign(Gtk.Align.FILL)
            indicator.set_valign(Gtk.Align.END)
            box.indicators.append(indicator)
            overlay.add_overlay(indicator)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(box, data))
        return box

    def update_ui(self, widget, data):
        """ Update workspaces UI """
        workspaces = data.get('workspaces', [])
        focused = data.get('focused')
        monitor_map = data.get('monitors', {})
        colorize = self.config.get('colorize_by_monitor', False)

        for n, (button, indicator) in enumerate(
                zip(widget.buttons, widget.indicators)):
            name = str(n + 1)
            if name in workspaces:
                button.set_visible(True)
            else:
                button.set_visible(False)

            for m in range(1, 11):
                c.del_style(indicator, f'monitor-{m}')

            if colorize and name in monitor_map:
                c.add_style(indicator, f'monitor-{monitor_map[name]}')

            if name == focused:
                c.add_style(button, 'focused')
            else:
                c.del_style(button, 'focused')


module_map = {
    'workspaces': Workspaces
}
