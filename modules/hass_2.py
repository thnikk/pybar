#!/usr/bin/python3 -u
"""
Description: Home Assistant dashboard module refactored for unified state
Author: thnikk
"""
import requests
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class HASS2(c.BaseModule):
    SCHEMA = {
        'server': {
            'type': 'string',
            'default': '',
            'label': 'Server',
            'description': 'Home Assistant server address (e.g. 192.168.1.100:8123)'
        },
        'bearer_token': {
            'type': 'string',
            'default': '',
            'label': 'Bearer Token',
            'description': 'Long-lived access token from Home Assistant'
        },
        'interval': {
            'type': 'integer',
            'default': 30,
            'label': 'Update Interval',
            'description': 'How often to poll devices (seconds)',
            'min': 5,
            'max': 600
        },
        'devices': {
            'type': 'dict',
            'key_type': 'string',
            'value_type': 'dict',
            'schema': {
                'type': 'dict',
                'key_type': 'string',
                'value_type': 'string'
            },
            'default': {},
            'label': 'Devices',
            'description': 'Home Assistant devices organized by section'
        }
    }

    def get_ha_state(self, server, entity, token):
        try:
            res = requests.get(
                f"http://{server}/api/states/{entity}",
                headers={
                    "Authorization": token,
                    "content-type": "application/json"},
                timeout=3).json()
            return res
        except Exception:
            return None

    def fetch_data(self):
        server = self.config.get('server')
        token = self.config.get('bearer_token')
        devices_config = self.config.get('devices', {})

        if not server or not token:
            return {}

        sections = {}
        for section, entities in devices_config.items():
            sections[section] = []
            for name, eid in entities.items():
                state_data = self.get_ha_state(server, eid, token)
                if state_data:
                    sections[section].append({
                        "name": name,
                        "id": eid,
                        "state": state_data.get('state'),
                        "unit": state_data.get('attributes', {}).get(
                            'unit_of_measurement', '')
                    })

        return {
            "sections": sections,
            "server": server,
            "token": token
        }

    def toggle_ha(self, data, eid, _state):
        try:
            domain = eid.split('.')[0]
            # Always use toggle service for simplicity
            requests.post(
                f"http://{data['server']}/api/services/{domain}/toggle",
                headers={
                    "Authorization": data['token'],
                    "content-type": "application/json"},
                json={"entity_id": eid}, timeout=3)
        except Exception:
            pass
        return False

    def build_popover(self, data):
        box = c.box('v', spacing=20)
        box.append(c.label('Home Assistant', style='heading'))

        for section, devices in data.get('sections', {}).items():
            sec_box = c.box('v', spacing=10)
            sec_box.append(c.label(section, style='title', ha='start'))
            ibox = c.box('v', style='box')

            for i, dev in enumerate(devices):
                row = c.box('h', spacing=20, style='inner-box')
                row.append(c.label(dev['name'], ha="start", he=True))

                eid_type = dev['id'].split('.')[0]
                if eid_type == 'sensor':
                    val = dev.get('state', 'unknown')
                    if val and '.' in val:
                        val = val.split('.')[0]
                    row.append(c.label(f"{val}{dev['unit']}", ha="end"))
                elif eid_type in ['switch', 'light']:
                    sw = Gtk.Switch.new()
                    sw.set_active(dev['state'] == 'on')
                    sw.set_valign(Gtk.Align.CENTER)
                    sw.connect(
                        'state-set', lambda _s, st, d=data, eid=dev['id']:
                        self.toggle_ha(d, eid, st))
                    row.append(sw)

                ibox.append(row)
                if i < len(devices) - 1:
                    ibox.append(c.sep('h'))

            sec_box.append(ibox)
            box.append(sec_box)

        return box

    def create_widget(self, bar):
        m = c.Module(True, False)
        m.set_position(bar.position)
        m.set_icon('')
        m.set_visible(False)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        if data.get('sections'):
            widget.set_visible(True)
        else:
            widget.set_visible(True)  # Force visible

        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'hass_dashboard': HASS2
}
alias_map = {
    'hass_2': HASS2
}
