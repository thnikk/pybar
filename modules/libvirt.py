#!/usr/bin/python3 -u
"""
Description: VM module refactored for unified state
Author: thnikk
"""
import glob
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class VM(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 10,
            'label': 'Update Interval',
            'description': 'How often to check for running VMs (seconds)',
            'min': 5,
            'max': 60
        }
    }

    def fetch_data(self):
        try:
            domains = [
                p.split("/")[-1].rstrip(".xml")
                for p in glob.glob("/var/run/libvirt/qemu/*.xml")]
            return {
                "text": f" {len(domains)}" if domains else "",
                "domains": domains
            }
        except Exception:
            return {}

    def build_popover(self, data):
        box = c.box('v', spacing=20, style='small-widget')
        box.append(c.label('Running VMs', style='heading'))

        ibox = c.box('v', style='box')
        for i, d in enumerate(data.get('domains', [])):
            ibox.append(c.label(d, style='inner-box', ha='start'))
            if i < len(data['domains']) - 1:
                ibox.append(c.sep('h'))

        box.append(ibox)
        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_visible(False)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))
        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'libvirt': VM
}
alias_map = {
    'vm': VM
}
