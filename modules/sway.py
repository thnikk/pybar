#!/usr/bin/python3 -u
"""
Description: Sway workspaces module
Author: thnikk
"""
from subprocess import run
import json
import common as c
import os
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def switch_workspace(_, workspace):
    """ Click action """
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def module(config=None):
    """ Workspaces module """
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
        button.connect('clicked', switch_workspace, n)
        buttons.append(button)
        module.add(button)

    def get_workspaces():
        try:
            with open(
                os.path.expanduser('~/.cache/pybar/sway.json'),
                'r', encoding='utf-8'
            ) as file:
                try:
                    cache = json.loads(file.read())
                except json.decoder.JSONDecodeError:
                    return True
        except FileNotFoundError:
            return True

        for n, button in enumerate(buttons):
            name = str(n+1)
            if name in cache['workspaces']:
                button.show()
            else:
                button.hide()
            if name in cache['focused']:
                c.add_style(button, 'focused')
            else:
                c.del_style(button, 'focused')

        return True
    if get_workspaces():
        GLib.timeout_add(50, get_workspaces)
        return module
