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

        self.widgets = [
            {item: {
                'level': Gtk.LevelBar.new(), 'label': Gtk.Label.new("0%")
            } for item in ["load", "mem"]}
            for x in range(0, 2)
        ]
        c.print_debug(self.widgets)
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
        for num, device in enumerate(self.devices):
            loads.append(device['gpu'])

            load = float(device['gpu'].split('%')[0])/100
            self.widgets[num]['load']['level'].set_value(load)
            self.widgets[num]['load']['label'].set_text(device['gpu'])

            mem = float(device['vram'].split('%')[0])/100
            self.widgets[num]['mem']['level'].set_value(mem)
            self.widgets[num]['mem']['label'].set_text(device['vram'])

        self.text.set_text(' '.join(loads))

    def get_devices(self):
        output = run(
            ["rocm-smi"], capture_output=True, check=True
        ).stdout.decode('utf-8').splitlines()

        devices = []
        columns = [
            'device', 'node', 'did', 'guid', 'temp', 'power', 'mem',
            'compute', 'id', 'sclk', 'mclk', 'fan', 'perf', 'pwr_cap',
            'vram', 'gpu']
        for line in output:
            if len(line) > 0 and line[0].isdigit():
                device = {}
                parts = ' '.join(line.split()).split()
                for num, part in enumerate(parts):
                    device[columns[num]] = part
                devices.append(device)
        return devices
        # return json.loads(
        #         run(
        #             ['rocm-smi'], capture_output=True, check=True
        #             ).stdout.decode('utf-8')
        #         )


def module(bar, config):
    module = Rocm(bar, config)
    return module
