#!/usr/bin/python3 -u
"""
Description: Volume widget
Author: thnikk
"""
import common as c
from pulse import Pulse
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib  # noqa


def sink_volume(widget, sink):
    """ Action for changing value of scale """
    p = Pulse()
    p.set_sink_volume(sink, widget.get_value())


def sink_input_volume(widget, sink):
    """ Action for changing value of scale """
    p = Pulse()
    p.set_sink_input_volume(sink, widget.get_value())


def volume_widget():
    """ Volume widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    main_box.add(c.label('Volume', style='heading'))
    p = Pulse()
    sinks = {
        sink['device.description']: {
            "name": sink['Name']}
        for sink in p.get_sinks('sinks')
    }

    section_box = c.box('v', spacing=10)
    section_box.add(c.label('Outputs', style='title', ha='start'))
    icons = {'pnp': '', 'arctis': ''}
    sinks_box = c.box('v', style='box')
    for description, info in sinks.items():
        for short, icon in icons.items():
            if short in description.lower():
                sink_box = c.box('h', spacing=10, style='inner-box')
                sink_box.add(c.label(icon, style='icon-volume'))
                level = c.slider(p.get_sink_volume(info['name']))
                level.connect(
                    'value-changed', sink_volume, info['name'])
                level_box = c.box('v')
                level_box.pack_start(level, 1, 0, 0)
                sink_box.pack_start(level_box, 1, 1, 0)
                sinks_box.add(sink_box)
    section_box.add(sinks_box)
    main_box.add(section_box)

    section_box = c.box('v', spacing=10)
    section_box.add(c.label('Programs', style='title', ha='start'))
    sinks_box = c.box('v', style='box')
    sink_inputs = {
        sink['node.name']: {
            "id": sink['Sink Input'],
            "volume": int(sink['Volume'].split('/')[1].split('%')[0].strip())
        }
        for sink in p.get_sinks('sink-inputs')
        if 'node.name' in list(sink)
    }
    for name, info in sink_inputs.items():
        sink_box = c.box('v', spacing=10, style='inner-box')
        sink_box.add(c.label(name))
        level = c.slider(info['volume'])
        level.connect(
            'value-changed', sink_input_volume, info['id'])
        sink_box.pack_start(level, 1, 1, 0)
        sinks_box.add(sink_box)
        if name != list(sink_inputs)[-1]:
            sinks_box.add(c.sep('v'))
    section_box.add(sinks_box)
    main_box.add(section_box)

    # def get_volume(sinks):
    #     p = Pulse
    #     for description, info in sinks.items():
    #         sinks[description]['level'].set_level(p.get_sink_volume(info['name']))
    #     return True
    # if get_volume(sinks):
    #     GLib.timeout_add(1000, get_volume)
    return main_box
