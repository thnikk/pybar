#!/usr/bin/python3 -u
"""
Description: Pulse module
Author: thnikk
"""
import common as c
import pulsectl
import concurrent.futures
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa


def set_volume(widget, pulse, sink):
    """ Set volume for sink/source/sink-input """
    pulse.volume_set_all_chans(sink, widget.get_value()/100)


def set_default(widget, pulse, sink):
    """ Set default sink/source """
    pulse.default_set(sink)


def widget_box(module, widget, pulse):
    """ Volume widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    main_box.add(c.label('Volume', style='heading'))

    for name, list_type in {
        "Outputs": pulse.sink_list(),
        "Inputs": pulse.source_list(),
        "Programs": pulse.sink_input_list()
    }.items():
        section_box = c.box('v', spacing=10)
        section_box.add(c.label(name, style='title', ha='start'))
        sinks_box = c.box('v', style='box')
        sink_list = list_type
        for sink in sink_list:
            sink_box = c.box('v', spacing=10, style='inner-box')
            if name == 'Programs':
                try:
                    prog = sink.proplist[
                        'application.process.binary']
                except KeyError:
                    prog = sink.name
                sink_label = c.button(prog, ha='start')
            else:
                if 'Monitor of' in sink.description:
                    continue
                sink_label = c.button(sink.description, ha='start')
                sink_label.connect('clicked', set_default, pulse, sink)
            sink_box.add(sink_label)
            level = c.slider(round(sink.volume.value_flat*100))
            level.connect('value-changed', set_volume, pulse, sink)
            sink_box.pack_start(level, 1, 1, 0)
            sinks_box.add(sink_box)
            if sink != sink_list[-1]:
                sinks_box.add(c.sep('v'))
        section_box.add(sinks_box)
        if sink_list:
            main_box.add(section_box)

    return main_box


def pulse_listen(module):
    """ Listen for events """
    with pulsectl.Pulse('event-listener') as pulse:
        def print_events(ev):
            raise pulsectl.PulseLoopStop
        pulse.event_mask_set('sink', 'sink_input', 'source')
        pulse.event_callback_set(print_events)
        pulse.event_listen()


def pulse_thread(module):
    """ Seperate thread for listening for events """
    while True:
        pulse_listen(module)
        module.emit('update')


def switch_outputs(module, event, pulse, icons):
    """ Right click action """
    if event.button == 3:
        default = pulse.server_info().default_sink_name
        sinks = [sink.name for sink in pulse.sink_list()]
        index = sinks.index(default) + 1
        if index > len(sinks) - 1:
            index = 0
        pulse.sink_default_set(sinks[index])
        update(module, pulse, icons)


def scroll(module, event, pulse):
    """ Scroll action """
    default = pulse.sink_default_get()
    if event.direction == Gdk.ScrollDirection.UP:
        if default.volume.value_flat < 1:
            pulse.volume_change_all_chans(default, 0.01)
        else:
            pulse.volume_set_all_chans(default, 1)
    elif event.direction == Gdk.ScrollDirection.DOWN:
        pulse.volume_change_all_chans(default, -0.01)


def update(module, pulse, icons):
    """ Update """
    default = pulse.sink_default_get()
    volume = round(default.volume.value_flat * 100)
    module.text.set_label(f"{volume}%")

    set_icon(module, default, icons)

    if not module.get_active():
        make_widget(module, pulse)


def set_icon(module, sink, icons):
    """ Set icon for module """
    found = False
    for name, icon in icons.items():
        if name.lower() in sink.name.lower():
            module.icon.set_label(icon)
            found = True
    if not found:
        module.icon.set_label('')


def make_widget(module, pulse):
    """ Make widget for module """
    widget = c.Widget()
    widget.box.add(widget_box(module, widget, pulse))
    widget.draw()
    module.set_popover(widget)


def module(config=None):
    """ PulseAudio module """
    # Initialize config
    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    # Initialize module
    pulse = pulsectl.Pulse('Pybar')
    module = c.Module()
    c.add_style(module, 'module-fixed')
    module.connect('update', update, pulse, config['icons'])
    module.connect('scroll-event', scroll, pulse)
    module.connect(
        'button-press-event', switch_outputs, pulse, config['icons'])

    default = pulse.sink_default_get()
    volume = round(default.volume.value_flat * 100)
    set_icon(module, default, config['icons'])
    module.text.set_label(f'{volume}%')

    make_widget(module, pulse)

    executor = concurrent.futures.ThreadPoolExecutor()
    executor.submit(pulse_thread, module)

    return module
