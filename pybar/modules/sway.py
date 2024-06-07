#!/usr/bin/python3 -u
"""
Description: Properly threaded workspace module
Author: thnikk
"""
from subprocess import Popen, PIPE, STDOUT, DEVNULL, run
import threading
import json
import os
import signal
from .. import common as c
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GObject, GLib  # noqa


class Workspaces(Gtk.Box):
    def __init__(self, config):
        super().__init__()
        self.alive = True
        self.pid = None
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
        while self.alive:
            with Popen(['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'],
                       stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
                self.pid = p.pid
                for line in p.stdout:
                    GLib.idle_add(self.update)

    def get_workspaces(self):
        """ Get workspaces with swaymsg """
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
