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
    buttons = []
    for x in range(0, 11):
        try:
            button = c.button(label=config['icons'][str(x)], style='workspace')
        except (KeyError, TypeError):
            try:
                button = c.button(
                    label=config['icons']['default'], style='workspace')
            except (KeyError, TypeError):
                button = c.button(label=str(x), style='workspace')
        button.hide()
        button.connect('clicked', switch_workspace, x)
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
        workspaces = cache['workspaces']
        focused = cache['focused']
        for x in range(0, 11):
            if str(x) not in workspaces:
                buttons[x].hide()
            else:
                buttons[x].show()
        for workspace in buttons:
            c.del_style(workspace, 'focused')
        c.add_style(buttons[int(focused)], 'focused')
        return True
    if get_workspaces():
        GLib.timeout_add(50, get_workspaces)
        return module
