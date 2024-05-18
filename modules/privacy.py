#!/usr/bin/python3 -u
"""
Description: Privacy module
Author: thnikk
"""
import common as c
import threading
from subprocess import Popen, PIPE, STDOUT, CalledProcessError
import gi
import time
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa


class Privacy(Gtk.MenuButton):
    def __init__(self, config):
        super().__init__()
        c.add_style(self, 'module')
        c.add_style(self, 'green')
        self.set_no_show_all(True)

        thread = threading.Thread(target=self.listen_wrapper)
        thread.daemon = True
        thread.start()

    def listen_wrapper(self):
        """ Wrapper to auto-reconnect to listen function """
        while True:
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

        # Set label
        if text:
            self.set_label("  ".join(text))
            self.show()
        else:
            self.set_label('')
            self.hide()


def module(config=None):
    """ PulseAudio module """

    module = Privacy(config)

    return module
