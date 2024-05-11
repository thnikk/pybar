#!/usr/bin/python3 -u
"""
Description: Volume module
Author: thnikk
"""
import common as c
from subprocess import run
import pulsectl
import os
import json
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


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


def set_default_sink(button, sink, widget):
    """ Set the default sink """
    run(["pactl", "set-default-sink", sink],
        check=False, capture_output=False)
    widget.popdown()


def set_default_source(button, source):
    """ Set the default sink """
    run(["pactl", "set-default-source", source],
        check=False, capture_output=False)


def widget_box(module, cache, widget):
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
        sink_label.connect('clicked', set_default_sink, id, widget)
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
    if cache['sinks']:
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
    if cache['sources']:
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
    if cache['sink-inputs']:
        main_box.add(section_box)

    return main_box


def action(module, event):
    """ Scroll action """
    with pulsectl.Pulse('volume-increaser') as pulse:
        default = pulse.sink_default_get()
        if event.direction == Gdk.ScrollDirection.UP:
            if default.volume.value_flat < 1:
                pulse.volume_change_all_chans(default, 0.01)
            else:
                pulse.volume_set_all_chans(default, 1)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            pulse.volume_change_all_chans(default, -0.01)
        # volume = round(pulse.sink_default_get().volume.value_flat * 100)
        # module.text.set_label(f'{volume}%')
    get_volume(module)


def get_volume(module):
    """ Get volume data from cache """
    try:
        with open(
            os.path.expanduser('~/.cache/pybar/pulse.json'),
            'r', encoding='utf-8'
        ) as file:
            cache_raw = file.read()
            cache = json.loads(cache_raw)
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return True

    volume = cache['sinks'][cache['default-sink']]['volume']
    icons = ["", "", ""]
    icon_index = int(volume // (100 / len(icons)))
    try:
        icon = icons[icon_index]
    except IndexError:
        icon = icons[-1]
    if icon != module.icon.get_label():
        module.icon.set_label(icon)
    new = f'{volume}%'
    if new != module.text.get_label():
        module.text.set_label(new)
    if not module.get_active():
        if module.get_tooltip_text() != cache_raw:
            module.set_tooltip_text(cache_raw)
            module.set_has_tooltip(False)
            widget = c.Widget()
            widget.box.add(widget_box(module, cache, widget))
            widget.draw()
            module.set_popover(widget)
    return True


def module(config=None):
    """ Volume module """
    module = c.Module()
    c.add_style(module, 'module-fixed')
    module.connect('scroll-event', action)

    if get_volume(module):
        GLib.timeout_add(250, get_volume, module)
        return module
