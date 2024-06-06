#!/usr/bin/python3 -u
"""
Description: Toggle module
Author: thnikkk
"""
import common as c
from subprocess import Popen, DEVNULL
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


class switch(Gtk.Box):
    def __init__(self, icon, command):
        super().__init__()
        self.proc = None
        self.icon = icon
        self.command = command
        self.set_spacing(5)
        c.add_style(self, 'module')
        self.add(c.label(icon))

        switch_box = c.box('v')
        self.switch = Gtk.Switch.new()
        c.add_style(self.switch, 'switch')
        switch_box.pack_start(self.switch, 1, 0, 0)
        self.add(switch_box)
        self.switch.connect('state_set', self.click_action)

    def click_action(self, switch, state):
        """ Launch or kill program """
        if state:
            self.proc = Popen(self.command, stdout=DEVNULL, stderr=DEVNULL)
        else:
            self.proc.terminate()


def module(bar, config=None):
    if not config:
        config = {}
    if 'icon' in list(config):
        icon = config['icon']
    else:
        icon = ''
    if 'program' in list(config):
        command = config['program']
    else:
        command = ['tail', '-f', '/dev/null']
    module = switch(icon, command)

    def update():
        try:
            if module.proc.poll() is not None:
                module.switch.set_state(False)
                module.proc = None
        except AttributeError:
            pass
        return True

    if update():
        GLib.timeout_add(500, update)
        return module
