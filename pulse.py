#!/usr/bin/python3 -u
"""
Description: Cache pulse events to a file
Author: thnikk
"""
import pulsectl
import json
import os


def get_status():
    """ Get pulse devices """
    with pulsectl.Pulse() as pulse:
        return {
            "default-sink": pulse.server_info().default_sink_name,
            "default-source": pulse.server_info().default_source_name,
            "sinks": {
                sink.proplist['node.name']: {
                    "name": sink.proplist['device.product.name'],
                    "volume": round(sink.volume.value_flat * 100)
                }
                for sink in pulse.sink_list()
            },
            "sources": {
                source.proplist['node.name']: {
                    "name": source.proplist['alsa.card_name'],
                    "volume": round(source.volume.value_flat * 100),
                }
                for source in pulse.source_list()
                if 'alsa.card_name' in source.proplist
                and source.proplist['device.class'] != 'monitor'
            },
            "sink-inputs": [
                {
                    "id": sink_input.proplist['object.serial'],
                    "name": sink_input.proplist['application.name'],
                    "volume": round(sink_input.volume.value_flat * 100)
                }
                for sink_input in pulse.sink_input_list()
            ]
        }


def cache(status):
    """ Write cache to file """
    with open(
        os.path.expanduser('~/.cache/pybar/pulse.json'),
        'w', encoding='utf-8'
    ) as file:
        file.write(json.dumps(status, indent=4))


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
        cache(get_status())
        listen()


def main():
    """ Debug """
    # cache()
    while True:
        print(json.dumps(get_status(), indent=4))
        listen()


if __name__ == "__main__":
    main()
