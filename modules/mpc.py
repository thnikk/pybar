#!/usr/bin/python -u
from subprocess import run, DEVNULL, CalledProcessError
import common as c
import threading
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango, GLib  # noqa


class Mpc(c.Module):
    def __init__(self, bar, config):
        super().__init__()
        self.icon.set_text('')
        self.text.set_max_width_chars(20)
        self.text.set_ellipsize(Pango.EllipsizeMode.END)

        try:
            run(['mpc', 'version'], check=True, stdout=DEVNULL, stderr=DEVNULL)
        except CalledProcessError:
            self.text.set_text('mpd not running')
        self.update()

        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()

    def listen(self):
        while True:
            try:
                run(['mpc', 'idle'], stdout=DEVNULL, stderr=DEVNULL)
                GLib.idle_add(self.update)
            except CalledProcessError:
                time.sleep(5)

    def update(self):
        try:
            output = run(
                ['mpc', 'status'], capture_output=True, check=True
            ).stdout.decode('utf-8').splitlines()
        except CalledProcessError:
            return
        artist = output[0].split(' - ')[0].strip()
        song = output[0].split(' - ')[-1]
        status = output[1].split(']')[0].lstrip('[')
        if status == 'playing':
            self.icon.set_text('')
        elif status == 'paused':
            self.icon.set_text('')
        else:
            self.icon.set_text('')
        self.text.set_text(song)


def module(bar, config):
    module = Mpc(bar, config)
    return module
