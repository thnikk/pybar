#!/usr/bin/python3 -u
"""
Description: Transmission module refactored for unified state
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

try:
    from transmission_rpc import Client
except ImportError:
    Client = None


class Transmission(c.BaseModule):
    SCHEMA = {
        'host': {
            'type': 'string',
            'default': 'localhost',
            'label': 'Host',
            'description': 'Transmission RPC host'
        },
        'port': {
            'type': 'integer',
            'default': 9091,
            'label': 'Port',
            'description': 'Transmission RPC port',
            'min': 1,
            'max': 65535
        },
        'interval': {
            'type': 'integer',
            'default': 30,
            'label': 'Update Interval',
            'description': 'How often to check torrent status (seconds)',
            'min': 10,
            'max': 300
        }
    }

    def fetch_data(self):
        if not Client:
            return {}

        try:
            client = Client(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 9091)
            )
            torrents = client.get_torrents()

            down_list = []
            up_list = []
            for t in torrents:
                if t.status == 'downloading':
                    down_list.append(f'{t.name} {int(t.progress)}%')
                elif t.status == 'seeding':
                    up_list.append(t.name)

            text_parts = []
            if down_list:
                text_parts.append(f" {len(down_list)}")
            if up_list:
                text_parts.append(f" {len(up_list)}")

            return {
                "text": "  ".join(text_parts),
                "downloading": down_list,
                "uploading": up_list
            }
        except Exception:
            return {}

    def build_popover(self, data):
        box = c.box('v', spacing=20, style='small-widget')
        box.append(c.label('Transmission', style='heading'))

        sections = [
            ("Downloading", data.get('downloading', [])),
            ("Seeding", data.get('uploading', []))
        ]
        for title, items in sections:
            if not items:
                continue
            sec = c.box('v', spacing=10)
            sec.append(c.label(title, style='title', ha='start'))
            ibox = c.box('v', style='box')
            for i, item in enumerate(items):
                ibox.append(c.label(item, style='inner-box', ha='start'))
                if i < len(items) - 1:
                    ibox.append(c.sep('h'))
            sec.append(ibox)
            box.append(sec)

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
        if data.get('stale'):
            c.add_style(widget, 'stale')
        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'transmission': Transmission
}
