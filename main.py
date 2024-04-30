#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import run, Popen, PIPE, STDOUT
import time
import calendar
from datetime import datetime
import concurrent.futures
import common as c


def switch_workspace(module, workspace):
    """ Click action for workspaces """
    del module
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def sway(box):
    """ Sway workspaces """
    buttons = []
    for x in range(0, 10):
        button = c.button(label=str(x), style='workspace')
        button.connect('clicked', switch_workspace, x)
        buttons.append(button)
        box.add(button)

    while True:
        output = c.load_module(['swaymsg', '-t', 'get_workspaces'])
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


def clock(label):
    """ d """
    while True:
        label.set_label(f" {datetime.now().strftime('%I:%M %m/%d')}")
        now = datetime.now()
        cal = calendar.TextCalendar(firstweekday=6)
        label.props.tooltip_text = cal.formatmonth(
            now.year, now.month).rstrip()
        time.sleep(1)


def waybar_module(label, command, interval):
    """ d """
    while True:
        output = c.load_module(command)
        if output['text']:
            label.set_visible(True)
        else:
            label.set_visible(False)
        label.set_label(output['text'])
        try:
            label.get_style_context().add_class(output['class'])
        except KeyError:
            pass
        try:
            label.props.tooltip_markup = output['tooltip']
        except KeyError:
            pass
        time.sleep(interval)


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    pybar = c.Bar(spacing=5)
    pybar.css('style.css')
    clock_button = c.label('Clock', style='module')
    executor.submit(clock, clock_button)
    pybar.right.pack_end(clock_button, 0, 0, 0)

    right_config = [
        [["~/.local/bin/bar/privacy.py"], 1],
        [["~/.local/bin/bar/updates.py"], 300],
        [["~/.local/bin/bar/sales.py"], 300],
        [[
            "~/.venv/hoyo-stats/bin/python",
            "~/.local/bin/bar/hoyo-stats.py", "-g", "genshin"], 300],
        [[
            "~/.venv/hoyo-stats/bin/python",
            "~/.local/bin/bar/hoyo-stats.py", "-g", "hsr"], 300],
        [["~/.local/bin/bar/ups.py", "0764", "0501"], 5],
        [["~/.local/bin/bar/weather.py", "94002"], 300],
    ]

    for command, interval in right_config:
        module = c.label('', style='module')
        pybar.right.pack_start(module, 0, 0, 0)
        module.set_visible(False)
        module.set_no_show_all(True)
        executor.submit(waybar_module, module, command, interval=interval)

    workspaces = c.box('h', style='workspaces')
    pybar.left.pack_start(workspaces, 0, 0, 0)
    executor.submit(sway, workspaces)

    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
