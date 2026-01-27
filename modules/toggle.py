#!/usr/bin/python3 -u
"""
Description: Toggle module refactored for unified state
Author: thnikkk
"""
import common as c
from subprocess import Popen, DEVNULL
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Toggle(c.BaseModule):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.proc = None

    def fetch_data(self):
        """ Fetch toggle data (is the process alive?) """
        alive = False
        if self.proc:
            if self.proc.poll() is None:
                alive = True
            else:
                self.proc = None

        return {
            "alive": alive,
            "icon": self.config.get('icon', '')
        }

    def on_state_set(self, _s, state):
        command = self.config.get('program', ['tail', '-f', '/dev/null'])
        if state:
            if not self.proc or self.proc.poll() is not None:
                self.proc = Popen(command, stdout=DEVNULL, stderr=DEVNULL)
        else:
            if self.proc:
                self.proc.terminate()
        return False  # Don't inhibit signal

    def create_widget(self, bar):
        """ Create toggle widget """
        icon = self.config.get('icon', '')

        box = c.box('h', style='module', spacing=5)
        box.append(c.label(icon))

        switch_box = c.box('v')
        sw = Gtk.Switch.new()
        c.add_style(sw, 'switch')
        switch_box.append(sw)
        box.append(switch_box)

        sw.connect('state-set', self.on_state_set)
        box.sw = sw

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(box, data))
        return box

    def update_ui(self, widget, data):
        """ Update toggle UI """
        if not data:
            return
        # Block signals during update to avoid loops
        widget.sw.set_state(data.get('alive', False))


module_map = {
    'toggle': Toggle
}
