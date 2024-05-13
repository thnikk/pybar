#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import Popen, PIPE, STDOUT, check_output
import concurrent.futures
import json
import common as c
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GObject  # noqa


def get_workspaces():
    """ Get workspaces """
    raw = json.loads(check_output(
        ['swaymsg', '-t', 'get_workspaces']))
    workspaces = [workspace['name'] for workspace in raw]
    workspaces.sort()
    focused = [
        workspace['name'] for workspace in raw
        if workspace['focused']
    ][0]
    return {
        'workspaces': workspaces,
        'focused': focused
    }


def sway_listen(module):
    """ Listen for events """
    with Popen(['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'],
               stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
        for line in p.stdout:
            module.emit('update')


def update(module, buttons):
    """ Update module """
    workspaces = get_workspaces()
    for n, button in enumerate(buttons):
        name = str(n+1)
        if name in workspaces['workspaces']:
            button.show()
        else:
            button.hide()
        if name in workspaces['focused']:
            c.add_style(button, 'focused')
        else:
            c.del_style(button, 'focused')


def module(config=None):
    """ Sway module """
    module = c.box('h', style='workspaces')

    if not config:
        config = {}
    if 'icons' not in config:
        config['icons'] = {}

    buttons = []
    for n in range(1, 11):
        button = c.button(style='workspace')
        button.set_no_show_all(True)
        try:
            button.set_label(config['icons'][str(n)])
        except KeyError:
            try:
                button.set_label(config['icons']['default'])
            except KeyError:
                button.set_label(str(n))
        buttons.append(button)
        module.add(button)

    update(module, buttons)

    GObject.signal_new(
        'update', module,
        GObject.SIGNAL_RUN_LAST, GObject.TYPE_BOOLEAN, ())
    module.connect('update', update, buttons)

    executor = concurrent.futures.ThreadPoolExecutor()
    executor.submit(sway_listen, module)

    return module
