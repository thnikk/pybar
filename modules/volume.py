#!/usr/bin/python3 -u
"""
Description: Pulse module
Author: thnikk
"""
import common as c
import pulsectl
import threading
import time
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa


class Volume(c.Module):
    def __init__(self, config):
        super().__init__()

        while True:
            try:
                self.pulse = pulsectl.Pulse()
                default = self.pulse.sink_default_get()
                break
            except pulsectl.pulsectl.PulseIndexError:
                c.print_debug(
                    "Couldn't connect to pulse server, retrying...",
                    color='red', name='modules-volume')
                time.sleep(1)
                continue

        c.add_style(self, 'module-fixed')

        self.icons = config['icons']

        self.connect('scroll-event', self.scroll)
        self.connect('button-press-event', self.switch_outputs)

        volume = round(default.volume.value_flat * 100)
        self.set_icon(default)
        self.text.set_label(f'{volume}%')

        self.make_widget()

        thread = threading.Thread(target=self.pulse_thread)
        thread.daemon = True
        thread.start()

    def set_volume(self, module, sink):
        """ Set volume for sink/source/sink-input """
        self.pulse.volume_set_all_chans(sink, module.get_value()/100)

    def set_default(self, module, sink):
        """ Set default sink/source """
        self.pulse.default_set(sink)

    def widget_box(self):
        """ Volume widget """
        main_box = c.box('v', style='widget', spacing=20)
        c.add_style(main_box, 'small-widget')
        main_box.add(c.label('Volume', style='heading'))

        for name, list_type in {
            "Outputs": self.pulse.sink_list(),
            "Inputs": self.pulse.source_list(),
            "Programs": self.pulse.sink_input_list()
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
                    sink_label.connect(
                        'clicked', self.set_default, sink)
                sink_box.add(sink_label)
                level = c.slider(round(sink.volume.value_flat*100))
                level.connect('value-changed', self.set_volume, sink)
                sink_box.pack_start(level, 1, 1, 0)
                sinks_box.add(sink_box)
                if sink != sink_list[-1]:
                    sinks_box.add(c.sep('v'))
            section_box.add(sinks_box)
            if sink_list:
                main_box.add(section_box)

        return main_box

    def pulse_listen(self):
        """ Listen for events """
        while True:
            try:
                with pulsectl.Pulse('event-listener') as pulse:
                    def print_events(ev):
                        raise pulsectl.PulseLoopStop
                    pulse.event_mask_set('sink', 'sink_input', 'source')
                    pulse.event_callback_set(print_events)
                    pulse.event_listen()
                    break
            except pulsectl.pulsectl.PulseDisconnected:
                c.print_debug(
                    'Reconnecting to pulse', name='volume-listener',
                    color='red')
                time.sleep(0.1)
                pass

    def pulse_thread(self):
        """ Seperate thread for listening for events """
        while True:
            self.pulse_listen()
            GLib.idle_add(self.update)

    def switch_outputs(self, module, event):
        """ Right click action """
        if event.button == 3 and event.type == Gdk.EventType.BUTTON_PRESS:
            default = self.pulse.server_info().default_sink_name
            sinks = [sink.name for sink in self.pulse.sink_list()]
            index = sinks.index(default) + 1
            if index > len(sinks) - 1:
                index = 0
            self.pulse.sink_default_set(sinks[index])
            self.update()

    def scroll(self, module, event):
        """ Scroll action """
        smooth, x, y = event.get_scroll_deltas()
        smooth_dir = x + (y * -1)
        default = self.pulse.sink_default_get()

        if (
            event.direction == Gdk.ScrollDirection.UP or
            event.direction == Gdk.ScrollDirection.RIGHT or
            (smooth and smooth_dir > 0)
        ):
            if default.volume.value_flat < 1:
                self.pulse.volume_change_all_chans(default, 0.01)
            else:
                self.pulse.volume_set_all_chans(default, 1)
        elif (
            event.direction == Gdk.ScrollDirection.DOWN or
            event.direction == Gdk.ScrollDirection.LEFT or
            (smooth and smooth_dir < 0)
        ):
            self.pulse.volume_change_all_chans(default, -0.01)

    def update(self):
        """ Update """
        while True:
            try:
                default = self.pulse.sink_default_get()
                break
            except (
                    pulsectl.pulsectl.PulseIndexError,
                    pulsectl.pulsectl.PulseOperationFailed
            ):
                c.print_debug(
                    'Reconnecting to pulse', name='volume-updater',
                    color='red')
                time.sleep(0.1)
                self.pulse = pulsectl.Pulse()
                pass
        volume = round(default.volume.value_flat * 100)
        self.text.set_label(f"{volume}%")

        self.set_icon(default)

        if not self.get_active():
            self.make_widget()

    def set_icon(self, sink):
        """ Set icon for module """
        if sink.mute:
            self.icon.set_label('')
            return
        found = False
        for name, icon in self.icons.items():
            if name.lower() in sink.name.lower():
                self.icon.set_label(icon)
                found = True
        if not found:
            self.icon.set_label('')

    def make_widget(self):
        """ Make widget for module """
        widget = c.Widget()
        widget.box.add(self.widget_box())
        widget.draw()
        self.set_popover(widget)


def module(config=None):
    """ PulseAudio module """
    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    module = Volume(config)

    return module
