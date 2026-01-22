#!/usr/bin/python3 -u
"""
Description: Properly threaded workspace module
Author: thnikk
"""
from subprocess import Popen, PIPE, STDOUT, DEVNULL, run, CalledProcessError
import threading
import socket
import json
import os
import signal
import common as c
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, Pango, GObject, GLib  # noqa


class Workspaces(Gtk.Box):
    def __init__(self, config):
        super().__init__()
        self.alive = True
        self.pid = None
        c.add_style(self, 'workspaces')
        try:
            run(
                ['swaymsg', '-t', 'get_version'],
                capture_output=False, check=True,
                stdout=DEVNULL, stderr=DEVNULL)
            self.wm = 'sway'
        except CalledProcessError:
            self.wm = 'hypr'

        # Set up buttons
        self.buttons = []
        for n in range(1, 11):
            button = c.button(style='workspace')
            button.set_visible(False)
            try:
                button.set_label(config['icons'][str(n)])
            except KeyError:
                try:
                    button.set_label(config['icons']['default'])
                except KeyError:
                    button.set_label(str(n))
            button.connect('clicked', self.switch, n)
            self.buttons.append(button)
            self.append(button)

        # Initial update before waiting for listener updates
        self.update()

        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()
        self.connect('destroy', self.destroy)

    def destroy(self, _):
        """ Clean up thread """
        os.kill(self.pid, signal.SIGTERM)
        self.alive = False
        c.print_debug('thread killed')

    def switch(self, button, workspace):
        """ Click action """
        run(
            ['swaymsg', 'workspace', 'number', str(workspace)],
            stdout=DEVNULL, stderr=DEVNULL, check=False, capture_output=False)

    def listen(self):
        """ Listen for events and update the box when there's a new one """
        if self.wm == 'sway':
            while self.alive:
                with Popen(
                    ['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'],
                    stdin=PIPE, stdout=PIPE, stderr=STDOUT
                ) as p:
                    self.pid = p.pid
                    for line in p.stdout:
                        GLib.idle_add(self.update)
        else:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(
                    f"{os.getenv('XDG_RUNTIME_DIR')}/hypr/"
                    f"{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket2.sock")
                while True:
                    data = sock.recv(1024).decode('utf-8')
                    if 'focus' in data or 'workspace' in data:
                        GLib.idle_add(self.update)

    def get_workspaces(self):
        """ Get workspaces with swaymsg """
        if self.wm == 'sway':
            raw = json.loads(run(
                ['swaymsg', '-t', 'get_workspaces'],
                check=True, capture_output=True
            ).stdout.decode('utf-8'))
            workspaces = [workspace['name'] for workspace in raw]
            workspaces.sort()
            focused = [
                workspace['name'] for workspace in raw
                if workspace['focused']
            ][0]
            return {'workspaces': workspaces, 'focused': focused}
        else:
            return {
                "workspaces": [
                    workspace['name'] for workspace in
                    json.loads(
                        run(
                            ['hyprctl', '-j', 'workspaces'],
                            check=True, capture_output=True
                        ).stdout.decode('utf-8'))
                ],
                "focused": json.loads(
                    run(
                        ['hyprctl', '-j', 'activeworkspace'],
                        check=True, capture_output=True
                    ).stdout.decode('utf-8'))['name']
            }

    def update(self):
        """ Update the box with new workspace info """
        workspaces = self.get_workspaces()
        for n, button in enumerate(self.buttons):
            name = str(n+1)
            if name in workspaces['workspaces']:
                button.show()
            else:
                button.hide()
            if name == workspaces['focused']:
                c.add_style(button, 'focused')
            else:
                c.del_style(button, 'focused')


def module(bar, config=None):
    """ Sway module """

    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    module = Workspaces(config)

    return module
