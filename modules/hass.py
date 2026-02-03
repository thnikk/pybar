#!/usr/bin/python3 -u
"""
Description: Home Assistant module refactored for unified state
Author: thnikk
"""
import requests
import time
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

HISTORY = {}


class HASS(c.BaseModule):
    SCHEMA = {
        'server': {
            'type': 'string',
            'default': '',
            'label': 'Server',
            'description': 'Home Assistant server address (e.g. 192.168.1.100:8123)'
        },
        'sensor': {
            'type': 'string',
            'default': '',
            'label': 'Sensor Entity ID',
            'description': 'Entity ID of the sensor (e.g. sensor.temperature)'
        },
        'bearer_token': {
            'type': 'string',
            'default': '',
            'label': 'Bearer Token',
            'description': 'Long-lived access token from Home Assistant'
        },
        'format': {
            'type': 'string',
            'default': '{}',
            'label': 'Format String',
            'description': 'Format string with {} for value (e.g. "{}°C")'
        },
        'history': {
            'type': 'integer',
            'default': 100,
            'label': 'History Length',
            'description': 'Number of data points to keep for graph',
            'min': 10,
            'max': 500
        },
        'min': {
            'type': 'float',
            'default': None,
            'label': 'Graph Minimum',
            'description': 'Minimum value for graph scale (optional)'
        },
        'max': {
            'type': 'float',
            'default': None,
            'label': 'Graph Maximum',
            'description': 'Maximum value for graph scale (optional)'
        },
        'interval': {
            'type': 'integer',
            'default': 30,
            'label': 'Update Interval',
            'description': 'How often to poll sensor (seconds)',
            'min': 5,
            'max': 600
        }
    }

    def get_ha_data(self, server, sensor, bearer_token):
        try:
            response = requests.get(
                f"http://{server}/api/states/{sensor}",
                headers={
                    "Authorization": bearer_token,
                    "content-type": "application/json",
                },
                timeout=3
            ).json()
            return response
        except Exception as e:
            c.print_debug(f"HASS fetch failed: {e}", color='red')
            return None

    def fetch_data(self):
        server = self.config.get('server')
        sensor = self.config.get('sensor')
        token = self.config.get('bearer_token')

        if not all([server, sensor, token]):
            return {}

        data = self.get_ha_data(server, sensor, token)
        if not data or data.get('state') == 'unavailable':
            return {}

        history_len = self.config.get('history', 100)
        try:
            val = float(data['state'])
            if sensor not in HISTORY:
                HISTORY[sensor] = []
            HISTORY[sensor].append({"val": val, "time": time.time()})
            if len(HISTORY[sensor]) > history_len:
                HISTORY[sensor].pop(0)
        except (ValueError, KeyError):
            pass

        history_data = HISTORY.get(sensor, [])
        duration = 0
        if len(history_data) > 1:
            duration = history_data[-1]['time'] - history_data[0]['time']

        return {
            "text": self.config.get(
                'format', '{}').replace('{}', data['state'].split('.')[0]),
            "name": data['attributes'].get('friendly_name', sensor),
            "state": data['state'],
            "unit": data['attributes'].get('unit_of_measurement', ''),
            "history": [i['val'] for i in history_data],
            "duration": duration,
            "min": self.config.get('min'),
            "max": self.config.get('max')
        }

    def build_popover(self, widget, data):
        """ Home Assistant history widget """
        main_box = c.box('v', spacing=10, style='small-widget')

        header = c.box('h')
        header.append(
            c.label(data['name'], style='heading', ha='start', he=True))
        main_box.append(header)

        if data.get('history'):
            graph_box = c.box('v', style='box')
            graph_box.set_overflow(Gtk.Overflow.HIDDEN)
            widget.graph = c.Graph(
                data['history'],
                state=data['state'],
                unit=data['unit'],
                min_config=data.get('min'),
                max_config=data.get('max'),
                smooth=False
            )
            graph_box.append(widget.graph)
            main_box.append(graph_box)

            # Time legend below graph
            time_box = c.box('h')
            duration_str = f"{data.get('duration', 0):.0f}s ago"
            widget.duration_label = c.label(
                duration_str, style='gray', ha='start', he=True)
            time_box.append(widget.duration_label)
            time_box.append(c.label('Now', style='gray', ha='end'))
            main_box.append(time_box)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.graph = None
        m.duration_label = None

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
            widget.set_widget(self.build_popover(widget, data))
        else:
            if widget.graph:
                widget.graph.update_data(
                    data.get('history', []), data.get('state'))
            if widget.duration_label:
                widget.duration_label.set_text(
                    f"{data.get('duration', 0):.0f}s ago")


module_map = {
    'hass': HASS
}
