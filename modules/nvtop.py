#!/usr/bin/python3 -u
from subprocess import run, CalledProcessError
import time
import json
import threading
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango, GLib  # noqa


class Rocm(c.Module):
    def __init__(self, bar, config):
        super().__init__(text=False)
        self.icon.set_text('')
        self.devices = []

        self.device_labels = []
        self.levels = []
        self.widgets = []
        self.bar_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        self.label_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        self.cards_box = c.box('h', spacing=10)
        self.box.append(self.cards_box)
        for x in range(0, 2):
            levels = []
            levels_box = c.box('h', spacing=4)
            for y in range(0, 2):
                level = Gtk.LevelBar.new()
                Gtk.Orientable.set_orientation(level, Gtk.Orientation.VERTICAL)
                level.set_value(50)
                level.set_max_value(100)
                level.set_inverted(True)
                levels.append(level)
                levels_box.append(level)
            self.cards_box.append(levels_box)
            self.levels.append(levels)

            device = {}
            for item in ["load", "mem"]:
                level = Gtk.LevelBar.new()
                level.set_max_value(100)
                level.set_hexpand(True)  # Make horizontal levels span full width
                c.add_style(level, 'level-horizontal')
                self.bar_group.add_widget(level)
                label = Gtk.Label.new('0%')
                label.set_xalign(1)
                self.label_group.add_widget(label)
                device[item] = {'level': level, 'label': label}
            self.widgets.append(device)

        # c.print_debug(self.widgets)
        self.set_widget(self.widget())

        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()

    def widget(self):
        box = c.box('v', spacing=10)
        box.append(c.label('GPU info', style="heading"))

        devices_box = c.box('v', spacing=10)
        # Make boxes for 2 gpus
        for x in range(0, 2):
            card_box = c.box('v', spacing=4)
            label = c.label(f'Device {x}', style='title', ha='start', he=True)
            self.device_labels.append(label)
            card_box.append(label)

            info_outer_box = c.box('v', spacing=0)
            c.add_style(info_outer_box, 'box')

            inner_info_box = c.box('v', spacing=10, style='inner-box')
            for line, widgets in self.widgets[x].items():
                line_box = c.box('h', spacing=10)
                for name, item in widgets.items():
                    line_box.append(item)
                inner_info_box.append(line_box)

            info_outer_box.append(inner_info_box)
            card_box.append(info_outer_box)
            devices_box.append(card_box)

        box.append(devices_box)
        return box

    def listen(self):
        while True:
            try:
                self.devices = self.get_devices()
                GLib.idle_add(self.update)
            except CalledProcessError:
                pass
            time.sleep(1)

    def update(self):
        loads = []
        for num, info in enumerate(self.devices):
            self.device_labels[num].set_text(info["device_name"])
            loads.append(info['gpu_util'])

            if info['gpu_util']:
                load = int(info['gpu_util'].strip('%'))
            else:
                load = 0

            self.widgets[num]['load']['level'].set_value(load)
            self.widgets[num]['load']['label'].set_text(f"{load}%")
            self.levels[num][0].set_value(load)

            mem = int(info['mem_util'].strip('%'))
            self.widgets[num]['mem']['level'].set_value(mem)
            self.widgets[num]['mem']['label'].set_text(f"{mem}%")
            self.levels[num][1].set_value(mem)

    def get_devices(self):
        return json.loads(
                run(
                    ['nvtop', '-s'],
                    capture_output=True, check=True
                    ).stdout.decode('utf-8')
                )


def module(bar, config):
    module = Rocm(bar, config)
    return module
