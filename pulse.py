#!/usr/bin/python3 -u
"""
Description: Cache pulse events to a file
Author: thnikk
"""
import pulsectl
import json
import os


def cache():
    """ Write events to cache file """
    with pulsectl.Pulse() as pulse:
        output = {
            "default-sink": pulse.server_info().default_sink_name,
            "sinks": {
                sink.proplist['node.name']: {
                    "name": sink.proplist['device.product.name'],
                    "volume": round(sink.volume.value_flat * 100)
                }
                for sink in pulse.sink_list()
                },
            "sink-inputs": [
                {
                    "id": sink_input.proplist['object.serial'],
                    "name": sink_input.proplist['application.process.binary'],
                    "volume": round(sink_input.volume.value_flat * 100)
                }
                for sink_input in pulse.sink_input_list()
            ]
        }
        with open(
            os.path.expanduser('~/.cache/pybar/pulse.json'),
            'w', encoding='utf-8'
        ) as file:
            file.write(json.dumps(output, indent=4))


def listen():
    """ Listen for events """
    with pulsectl.Pulse('event-printer') as pulse:

        def print_events(ev):
            raise pulsectl.PulseLoopStop

        pulse.event_mask_set('all')
        pulse.event_callback_set(print_events)
        pulse.event_listen()


def update():
    """ Main function """
    while True:
        cache()
        listen()
