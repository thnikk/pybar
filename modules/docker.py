#!/usr/bin/python3 -u
"""
Description: Docker widget
Author: thnikk
"""
import common as c
from subprocess import run, Popen
import os
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def event_action(button, command, path):
    Popen(
        ['docker', 'compose'] + command,
        cwd=path
    )


def widget(path, log):
    container = c.box('v', spacing=10)
    container.add(c.label(
        path.rstrip('/').split('/')[-1], style='heading'))
    log_box = Gtk.TextView()
    c.add_style(log_box, 'text-box')
    log_box.set_buffer(log)
    scrollable = c.scroll(width=600, height=300)
    c.add_style(scrollable, 'scroll-box')
    scrollable.add(log_box)
    container.add(scrollable)
    funcs = {
        "": ["up", "-d"],
        "": ["down"],
        "": ["restart"]
    }
    button_box = c.box('h', spacing=10)
    for icon, func in funcs.items():
        button = c.button(label=icon, style='normal')
        # c.add_style(button, 'module')
        button.connect('clicked', event_action, func, path)
        button_box.append(button)
    container.add(button_box)
    return container


def module(bar, config=None):
    """ Memory module """

    if 'path' not in config:
        return False
    path = os.path.expanduser(config['path'])

    module = c.Module()
    log = Gtk.TextBuffer()
    module.set_widget(widget(path, log))

    module.set_position(bar.position)
    module.text.set_label(
        config['label'] if config['label'] else 'Docker'
    )
    # module.connect('button-press-event', start, path)

    def update():
        # Get state
        state = run(
            ['docker', 'compose', 'ps', '--format', '"{{.State}}"'],
            check=True, capture_output=True,
            cwd=path
        ).stdout.decode('utf-8')
        if 'running' in state:
            module.icon.set_label('')
            c.add_style(module.indicator, 'green')
            output = run(
                ['docker', 'compose', 'logs', '--no-log-prefix'],
                cwd=path,
                capture_output=True, check=True
            ).stdout.decode('utf-8').splitlines()
            log.set_text(
                '\n'.join(output[-14:])
            )
        else:
            module.icon.set_label('')
            module.reset_style()
        return True

    if update():
        GLib.timeout_add(1000, update)
        return module
