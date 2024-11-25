#!/usr/bin/python3 -u
"""
Description: Home Assistant module
Author: thnikk
"""
import common as c
import requests
import traceback
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def get_data(server, sensor, bearer_token) -> dict:
    """ Get HomeAssistant data for sensor """
    response = requests.get(
        f"http://{server}/api/states/{sensor}",
        headers={
            "Authorization": bearer_token,
            "content-type": "application/json",
        },
        timeout=3
    ).json()
    return response


def switch_action(switch, state, config, id) -> None:
    """ Toggle switch """
    requests.post(
        f"http://{config['server']}/api/services/switch/toggle",
        headers={
            "Authorization": config['bearer_token'],
            "content-type": "application/json",
        },
        json={
            "entity_id": id
        },
        timeout=3
    )


def widget(config):
    """ Backlight widget """
    main_box = c.box('v', spacing=20)
    main_box.add(c.label('Home Assistant', style='heading-small'))

    for section, devices in config['devices'].items():
        section_box = c.box('v', spacing=10)
        section_box.add(c.label(section, style='title', ha='start'))
        lines_box = c.box('v', style='box')

        for name, id in devices.items():
            line_box = c.box('h', spacing=20, style='inner-box')
            line_box.pack_start(
                c.label(name, ha="start"), 1, 1, 0)

            if id.split('.')[0] == 'sensor':
                data = get_data(
                    config['server'], id, config['bearer_token'])
                value = data['state']
                try:
                    value += data['attributes']['unit_of_measurement']
                except KeyError:
                    pass
                line_box.pack_start(
                    c.label(value, ha="end"), 1, 1, 0)

            if id.split('.')[0] == 'switch' or id.split('.')[0] == 'light':
                try:
                    switch = Gtk.Switch.new()
                    c.add_style(switch, 'switch')
                    switch_v = c.box('v')
                    switch_h = c.box('h')
                    switch_v.pack_start(switch, 1, 0, 0)
                    switch_h.pack_start(switch_v, 1, 0, 0)

                    data = get_data(
                        config['server'], id, config['bearer_token'])
                    values = ["off", "on"]
                    switch.set_state(values.index(data['state']))
                    switch.connect('state_set', switch_action, config, id)

                    line_box.pack_end(switch_h, 0, 0, 0)
                except KeyError:
                    # continue
                    line_box.pack_end(c.label('???'), 0, 0, 0)

            lines_box.add(line_box)
            if name != list(devices)[-1]:
                lines_box.add(c.sep('v'))
        section_box.add(lines_box)

        main_box.pack_start(section_box, 1, 1, 0)
    return main_box


def module(bar, config=None):
    """ Backlight module """
    module = c.Module(1, 0)
    module.set_position(bar.position)
    module.icon.set_label('')

    def update_module():
        if not module.get_active():
            try:
                module.set_widget(widget(config))
            except BaseException:
                c.print_debug('Caught exception:')
                print(traceback.print_exc())
        return True

    if update_module():
        GLib.timeout_add(5000, update_module)
        return module
