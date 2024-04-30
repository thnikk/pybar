#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import run
import time
import common as c


def switch_workspace(module, workspace):
    """ Click action for workspaces """
    del module
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def sway_module(box):
    """ Sway workspaces """
    buttons = []
    for x in range(0, 10):
        button = c.button(label=str(x), style='workspace')
        button.connect('clicked', switch_workspace, x)
        buttons.append(button)
        box.add(button)

    while True:
        output = c.dict_from_cmd(['swaymsg', '-t', 'get_workspaces'])
        workspaces = [workspace['name'] for workspace in output]
        focused = [
            workspace['name'] for workspace in output
            if workspace['focused']
        ][0]
        for x in range(0, 10):
            if str(x) not in workspaces:
                buttons[x].hide()
            else:
                buttons[x].show()
        for workspace in buttons:
            workspace.get_style_context().remove_class('focused')
        buttons[int(focused)].get_style_context().add_class("focused")
        time.sleep(0.1)
