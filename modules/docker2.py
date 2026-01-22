#!/usr/bin/python3 -u
"""
Description: Docker widget
Author: thnikk
"""
import common as c
import threading
import time
from subprocess import run, Popen, PIPE, STDOUT, CalledProcessError
import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


class Docker(c.Module):
    def __init__(self, bar, config):
        super().__init__()
        self.path = os.path.expanduser(config['path'])
        self.name = self.path.rstrip('/').split('/')[-1]
        self.log = Gtk.TextBuffer()
        self.set_widget(self.widget())
        self.pid = None
        self.alive = True

        thread = threading.Thread(target=self.listen_wrapper)
        thread.daemon = True
        thread.start()

        self.set_position(bar.position)
        self.text.set_label(
            config['label'] if config['label'] else self.name
        )

    def widget(self):
        container = c.box('v', spacing=10)
        container.append(c.label(self.name))
        log_box = Gtk.TextView()
        c.add_style(log_box, 'text-box')
        log_box.set_buffer(self.log)
        scrollable = c.scroll(width=600, height=300)
        c.add_style(scrollable, 'scroll-box')
        scrollable.set_child(log_box)
        container.append(scrollable)
        funcs = {
            "": ["up", "-d"],
            "": ["down"],
            "": ["restart"]
        }
        button_box = c.box('h', spacing=10)
        for icon, func in funcs.items():
            button = c.button(label=icon)
            c.add_style(button, 'module')
            button.connect('clicked', self.event_action, func)
            button_box.append(button)
        container.append(button_box)
        return container

    def event_action(self, button, command):
        Popen(
            ['docker', 'compose'] + command,
            cwd=self.path
        )

    def update(self):
        # Get state
        state = run(
            ['docker', 'compose', 'ps', '--format', '"{{.State}}"'],
            check=True, capture_output=True,
            cwd=self.path
        ).stdout.decode('utf-8')
        if 'running' in state:
            self.icon.set_label('')
            c.add_style(self.indicator, 'green')
            # output = run(
            #     ['docker', 'compose', 'logs', '--no-log-prefix'],
            #     cwd=path,
            #     capture_output=True, check=True
            # ).stdout.decode('utf-8')
            # log.set_text(
            #     '\n'.join(
            #         reversed(output.splitlines())))
        else:
            self.icon.set_label('')
            self.reset_style()
        return True

    def listen_wrapper(self):
        """ Wrapper to auto-reconnect to listen function """
        while self.alive:
            try:
                self.listen()
            except CalledProcessError:
                time.sleep(1)
                continue

    def listen(self):
        with Popen(
            ['docker', 'compose', 'log', '--no-log-prefix'],
            stdin=PIPE, stdout=PIPE, stderr=STDOUT
        ) as p:
            self.pid = p.pid
            for line in p.stdout:
                GLib.idle_add(self.update)


def module(bar, config=None):
    """ Memory module """

    module = Docker(bar, config)

    # if module.update():
    #     GLib.timeout_add(1000, module.update)
    return module
