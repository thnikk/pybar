#!/usr/bin/python3 -u
"""
Description: Privacy module
Author: thnikk
"""
import common as c
import threading
from subprocess import Popen, PIPE, STDOUT, CalledProcessError
import os
import signal
import gi
import time
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa


class Privacy(c.Module):
    def __init__(self, bar, config):
        super().__init__()
        self.set_position(bar.position)
        self.alive = True
        self.pid = None
        c.add_style(self, 'green')
        self.text.show()
        self.box.show()
        self.set_no_show_all(True)

        thread = threading.Thread(target=self.listen_wrapper)
        thread.daemon = True
        thread.start()
        self.connect('destroy', self.destroy)

    def destroy(self, _):
        """ Clean up thread """
        os.kill(self.pid, signal.SIGTERM)
        self.alive = False
        c.print_debug('thread killed')

    def listen_wrapper(self):
        """ Wrapper to auto-reconnect to listen function """
        while self.alive:
            try:
                self.listen()
            except CalledProcessError:
                time.sleep(1)
                continue

    def listen(self):
        """ Listen for new event """
        devices = {}
        device = {}
        with Popen(['pw-mon', '-a'],
                   stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
            self.pid = p.pid
            for line in p.stdout:
                line = line.decode('utf-8').rstrip()

                # Save last device
                if 'added' in line or 'changed' in line:
                    try:
                        if (
                                'Stream/Input' in
                                device['properties']['media.class']
                        ):
                            devices[device['id']] = device
                            GLib.idle_add(self.update, devices)
                    except KeyError:
                        pass
                    device = {}

                # Remove device by ID
                if 'removed' in line:
                    try:
                        devices.pop(device['id'])
                        GLib.idle_add(self.update, devices)
                    except KeyError:
                        pass
                    device = {}

                # Add info to device dict
                try:
                    if line.split(':')[1]:
                        parts = [
                            part.strip().strip('"')
                            for part in line.split(':')]
                        device[parts[0]] = ":".join(parts[1:])
                except IndexError:
                    pass

                # Add info to properties
                if '=' in line:
                    parts = [
                        part.strip().strip('"')
                        for part in line.split('=')]
                    if 'properties' not in list(device):
                        device['properties'] = {}
                    device['properties'][parts[0]] = parts[1]

    def get_widget(self, devices):
        """ Draw widget """
        box = c.box('v', spacing=20)
        box.add(c.label('Privacy', style='heading'))
        c.add_style(box, 'small-widget')

        # Seperate devices by type
        categories = {}
        for id, device in devices.items():
            category = device['properties']['media.class'].split('/')[-1]
            if category not in list(categories):
                categories[category] = set()
            try:
                name = device['properties'][
                    'application.process.binary'].title()
            except KeyError:
                try:
                    name = device['properties']['node.name'].title()
                except KeyError:
                    name = device['properties']['media.name'].title()
            categories[category].add(name)

        for category, programs in categories.items():
            category_box = c.box('v', spacing=10)
            category_box.add(c.label(category, style='title', ha='start'))
            program_box = c.box('v', style='box')
            for program in programs:
                program_box.add(c.label(program, style='inner-box'))
                if program != list(programs)[-1]:
                    program_box.add(c.sep('v'))
            category_box.add(program_box)
            box.add(category_box)

        return box

    def update(self, devices):
        """ Update module """
        icons = {'Audio': '', 'Video': ''}

        # Get unique media types
        types = []
        for id, device in devices.items():
            types.append(device['properties']['media.class'].split('/')[-1])
        types = set(types)

        # Get icons
        text = [icons[item] for item in types]

        # Set widget
        self.set_widget(self.get_widget(devices))

        # Set label
        if text:
            self.text.set_label("  ".join(text))
            self.show()
        else:
            self.text.set_label('')
            self.hide()


def module(bar, config=None):
    """ PulseAudio module """

    module = Privacy(bar, config)

    return module
