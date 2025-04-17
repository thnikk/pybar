#!/usr/bin/python3 -u
from subprocess import run, CalledProcessError
import time
import json
import threading
import common as c
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Pango, GLib  # noqa


class Rocm(c.Module):
    def __init__(self, bar, config):
        super().__init__()
        self.icon.set_text('')
        self.devices = []

        self.levels = []
        self.widgets = []
        for x in range(0, 2):
            levels = []
            levels_box = c.box('h')
            for y in range(0, 2):
                level = Gtk.LevelBar.new()
                Gtk.Orientable.set_orientation(level, Gtk.Orientation.VERTICAL)
                level.set_value(0.5)
                level.set_inverted(True)
                levels.append(level)
                levels_box.add(level)
            self.box.add(levels_box)
            self.levels.append(levels)

            device = {}
            for item in ["load", "mem"]:
                level = Gtk.LevelBar.new()
                c.add_style(level, 'level-horizontal')
                label = Gtk.Label.new('0%')
                device[item] = {'level': level, 'label': label}
            self.widgets.append(device)

        # c.print_debug(self.widgets)
        self.set_widget(self.widget())

        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()

    def widget(self):
        box = c.box('v', spacing=20)
        box.add(c.label('GPU info', style='heading'))

        # Make boxes for 2 gpus
        for x in range(0, 2):
            device_box = c.box('v', spacing=10)
            c.add_style(device_box, 'box')
            device_box.add(c.label(f'Device {x}'))
            info_box = c.box('v', spacing=10, style='inner-box')
            for line, widgets in self.widgets[x].items():
                line_box = c.box('h', spacing=10)
                for name, item in widgets.items():
                    line_box.add(item)
                info_box.add(line_box)
            # for label, level in self.widgets[x].items():
            #     info_box.add(level)
            device_box.add(info_box)
            box.add(device_box)

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
        for device, info in self.devices.items():
            if 'card' in device:
                loads.append(info['GPU use (%)'])
                num = int(device.strip('card'))

                load = float(info['GPU use (%)'].split('%')[0])/100
                self.widgets[num]['load']['level'].set_value(load)
                self.widgets[num]['load']['label'].set_text(
                        info['GPU use (%)'])
                self.levels[num][0].set_value(load)

                mem = float(info['GPU Memory Allocated (VRAM%)'])/100
                self.widgets[num]['mem']['level'].set_value(mem)
                self.widgets[num]['mem']['label'].set_text(
                        info['GPU Memory Allocated (VRAM%)']
                    )
                self.levels[num][1].set_value(mem)

    def get_devices(self):
        return json.loads(
                run(
                    ['rocm-smi', '-a', '--json'],
                    capture_output=True, check=True
                    ).stdout.decode('utf-8')
                )


def module(bar, config):
    module = Rocm(bar, config)
    return module
