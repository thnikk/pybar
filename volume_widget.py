#!/usr/bin/python3 -u
"""
Description: Volume widget
Author: thnikk
"""
import common as c
from subprocess import run
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib  # noqa


def sink_volume(widget, sink):
    """ Action for changing value of scale """
    run(["pactl", "set-sink-volume", sink, f"{str(widget.get_value())}%"],
        check=False, capture_output=False)


def source_volume(widget, source):
    """ Action for changing value of scale """
    run(["pactl", "set-source-volume", source, f"{str(widget.get_value())}%"],
        check=False, capture_output=False)


def sink_input_volume(widget, sink):
    """ Action for changing value of scale """
    run([
        "pactl", "set-sink-input-volume", sink,
        f"{str(widget.get_value())}%"],
        check=False, capture_output=False)


def set_default_sink(widget, sink):
    """ Set the default sink """
    run(["pactl", "set-default-sink", sink],
        check=False, capture_output=False)


def set_default_source(widget, source):
    """ Set the default sink """
    run(["pactl", "set-default-source", source],
        check=False, capture_output=False)


def volume_widget(cache):
    """ Volume widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    main_box.add(c.label('Volume', style='heading'))

    section_box = c.box('v', spacing=10)
    section_box.add(c.label('Outputs', style='title', ha='start'))
    sinks_box = c.box('v', style='box')
    for id, info in cache['sinks'].items():
        sink_box = c.box('v', spacing=10, style='inner-box')
        sink_label = c.button(info['name'])
        sink_label.connect('clicked', set_default_sink, id)
        if id == cache['default-sink']:
            c.add_style(sink_label, 'active')
        sink_box.add(sink_label)
        level = c.slider(info['volume'])
        level.connect('value-changed', sink_volume, id)
        sink_box.pack_start(level, 1, 1, 0)
        sinks_box.add(sink_box)
        if id != list(cache['sinks'])[-1]:
            sinks_box.add(c.sep('v'))
    section_box.add(sinks_box)
    main_box.add(section_box)

    section_box = c.box('v', spacing=10)
    section_box.add(c.label('Inputs', style='title', ha='start'))
    sources_box = c.box('v', style='box')
    for id, info in cache['sources'].items():
        source_box = c.box('v', spacing=10, style='inner-box')
        source_label = c.button(info['name'])
        source_label.connect('clicked', set_default_source, id)
        if id == cache['default-source']:
            c.add_style(source_label, 'active')
        source_box.add(source_label)
        level = c.slider(info['volume'])
        level.connect('value-changed', source_volume, id)
        source_box.pack_start(level, 1, 1, 0)
        sources_box.add(source_box)
        if id != list(cache['sources'])[-1]:
            sinks_box.add(c.sep('v'))
    section_box.add(sources_box)
    main_box.add(section_box)

    section_box = c.box('v', spacing=10)
    section_box.add(c.label('Programs', style='title', ha='start'))
    sinks_box = c.box('v', style='box')
    for sink_input in cache['sink-inputs']:
        sink_box = c.box('v', spacing=10, style='inner-box')
        sink_box.add(c.label(sink_input['name']))
        level = c.slider(sink_input['volume'])
        level.connect('value-changed', sink_input_volume, sink_input['id'])
        sink_box.pack_start(level, 1, 1, 0)
        sinks_box.add(sink_box)
        if sink_input != cache['sink-inputs'][-1]:
            sinks_box.add(c.sep('v'))
    section_box.add(sinks_box)
    main_box.add(section_box)

    return main_box
