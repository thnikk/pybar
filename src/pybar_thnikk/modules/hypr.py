#!/usr/bin/python3 -u
"""
Description: Hyprland workspaces
Author: thnikk
"""
import socket
import os
from subprocess import DEVNULL, run
import threading
import json
from .. import common as c
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GObject, GLib  # noqa


class Workspaces(Gtk.Box):
    def __init__(self, config):
        super().__init__()
        c.add_style(self, 'workspaces')

        # Set up buttons
        self.buttons = []
        for n in range(1, 11):
            button = c.button(style='workspace')
            button.set_no_show_all(True)
            try:
                button.set_label(config['icons'][str(n)])
            except KeyError:
                try:
                    button.set_label(config['icons']['default'])
                except KeyError:
                    button.set_label(str(n))
            button.connect('clicked', self.switch, n)
            self.buttons.append(button)
            self.add(button)

        # Initial update before waiting for listener updates
        self.update()

        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()

    def switch(self, button, workspace):
        """ Click action """
        run(
            ['swaymsg', 'workspace', 'number', str(workspace)],
            stdout=DEVNULL, stderr=DEVNULL, check=False, capture_output=False)

    def listen(self):
        """ Listen for events and update the box when there's a new one """
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(
                f"{os.getenv('XDG_RUNTIME_DIR')}/hypr/"
                f"{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket2.sock")
            while True:
                data = sock.recv(1024).decode('utf-8')
                if 'workspace' in data:
                    GLib.idle_add(self.update)

    def get_workspaces(self):
        """ Get workspaces """
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
    """ Hyprland module """

    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    module = Workspaces(config)

    return module
