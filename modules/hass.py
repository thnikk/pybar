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

# We'll use a local history cache in the module scope
HISTORY = {}


def get_ha_data(server, sensor, bearer_token):
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
    except Exception:
        return None


def fetch_data(config):
    server = config.get('server')
    sensor = config.get('sensor')
    token = config.get('bearer_token')

    if not all([server, sensor, token]):
        return None

    data = get_ha_data(server, sensor, token)
    if not data or data.get('state') == 'unavailable':
        return None

    history_len = config.get('history', 100)
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
        "text": config.get(
            'format', '{}').replace('{}', data['state'].split('.')[0]),
        "name": data['attributes'].get('friendly_name', sensor),
        "state": data['state'],
        "unit": data['attributes'].get('unit_of_measurement', ''),
        "history": [i['val'] for i in history_data],
        "duration": duration,
        "min": config.get('min'),
        "max": config.get('max')
    }


def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.graph = None
    module.duration_label = None
    return module


def update_ui(module, data):
    module.set_label(data['text'])
    module.set_visible(bool(data['text']))

    if not module.get_active():
        module.set_widget(build_popover(module, data))
    else:
        # Live update graph and labels
        if module.graph:
            module.graph.update_data(
                data.get('history', []), data.get('state'))
        if module.duration_label:
            module.duration_label.set_text(
                f"{data.get('duration', 0):.0f}s ago")


def build_popover(module, data):
    """ Home Assistant history widget """
    main_box = c.box('v', spacing=10, style='small-widget')

    header = c.box('h')
    header.append(c.label(data['name'], style='heading', ha='start', he=True))
    main_box.append(header)

    if data.get('history'):
        graph_box = c.box('v', style='box')
        graph_box.set_overflow(Gtk.Overflow.HIDDEN)
        module.graph = c.Graph(
            data['history'],
            state=data['state'],
            unit=data['unit'],
            min_config=data.get('min'),
            max_config=data.get('max'),
            smooth=False
        )
        graph_box.append(module.graph)
        main_box.append(graph_box)

        # Time legend below graph
        time_box = c.box('h')
        duration_str = f"{data.get('duration', 0):.0f}s ago"
        module.duration_label = c.label(
            duration_str, style='gray', ha='start', he=True)
        time_box.append(module.duration_label)
        time_box.append(c.label('Now', style='gray', ha='end'))
        main_box.append(time_box)

    return main_box
