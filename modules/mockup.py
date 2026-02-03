#!/usr/bin/python3 -u
"""
Description: Mockup module to demonstrate new heading style
Author: Antigravity
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Mockup(c.BaseModule):
    def __init__(self, name, config):
        super().__init__(name, config)
        self.interval = 0  # No need to update

    def fetch_data(self):
        return {"title": "System Status"}

    def build_popover(self, data):
        # Set spacing=0 to ensure heading and content are touching
        main_box = c.box('v', spacing=0)

        # Heading section (uses the light grey background of the popover)
        main_box.append(
            c.label(data['title'], style='mockup-heading', ha='center'))

        # Content section (dark grey, touches the sides and bottom)
        content_box = c.box('v', spacing=10, style='mockup-content')
        content_box.set_vexpand(True)

        graph_box = c.box('v', style='box')
        graph_box.set_overflow(Gtk.Overflow.HIDDEN)
        graph = c.Graph([10, 20, 30, 40, 20, 50])
        graph_box.append(graph)
        content_box.append(graph_box)

        # Add some mock content
        cpu_box = c.box('h', spacing=10)
        cpu_box.append(c.label(' CPU Usage', ha='start', he=True))
        cpu_box.append(c.label('12%', style='blue-fg'))
        content_box.append(cpu_box)

        mem_box = c.box('h', spacing=10)
        mem_box.append(c.label(' Memory', ha='start', he=True))
        mem_box.append(c.label('4.2GB / 16GB', style='green-fg'))
        content_box.append(mem_box)

        content_box.append(c.sep('h'))

        update_box = c.box('h', spacing=10)
        update_box.append(c.label(' Updates available', ha='start', he=True))
        update_box.append(c.label('5', style='red-fg'))
        content_box.append(update_box)

        main_box.append(content_box)
        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')
        m.set_label('Mockup')

        # Add the custom class to the popover
        popover = m.get_popover()
        if popover:
            popover.add_css_class('mockup-widget')

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return

        if not widget.get_active():
            widget.set_widget(self.build_popover(data))

        popover = widget.get_popover()
        if popover and not popover.has_css_class('mockup-widget'):
            popover.add_css_class('mockup-widget')


module_map = {
    'mockup': Mockup
}
