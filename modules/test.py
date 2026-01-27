#!/usr/bin/python3 -u
"""
Description: Test module refactored for unified state
Author: thnikkk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Test(c.BaseModule):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.counter = 0

    def fetch_data(self):
        self.counter += 1
        return {"text": str(self.counter), "val": self.counter}

    def build_popover(self, data):
        box = c.box('v', spacing=10, style='small-widget')
        box.append(c.label('Test Module', style='heading'))
        box.append(c.label(f"Counter: {data['val']}", style='title'))
        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'test': Test
}
