#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output, run
import json
import gi
import common as c
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GLib


def switch_workspace(module, workspace):
    """ Click action """
    del module
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def module():
    module = c.box('h', style='workspaces')
    buttons = []
    for x in range(0, 10):
        button = c.button(label=str(x), style='workspace')
        button.hide()
        button.connect('clicked', switch_workspace, x)
        buttons.append(button)
        module.add(button)

    def get_workspaces():
        output = json.loads(check_output(['swaymsg', '-t', 'get_workspaces']))
        workspaces = [workspace['name'] for workspace in output]
        focused = [
            workspace['name'] for workspace in output
            if workspace['focused']][0]
        for x in range(0, 10):
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
