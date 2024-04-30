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
from waybar_module import waybar_module
from sway_module import sway_module
from clock_module import clock_module
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango


def pop():
    """ Thing """
    popover = Gtk.Popover()
    # popover.set_position(Gtk.PositionType.TOP)
    # popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
    # popover.set_modal(True)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    vbox.pack_start(c.label('Calendar', style='heading'), 0, 0, 0)
    # for x in range(0, 3):
    #     vbox.add(c.label(f'Thing {x}'))
    cal = Gtk.Calendar.new()
    cal.props.no_month_change = True
    cal.mark_day(datetime.now().day)
    vbox.add(cal)
    vbox.show_all()
    popover.add(vbox)
    return popover


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    pybar = c.Bar(spacing=5)
    pybar.css('style.css')

    workspaces = c.box('h', style='workspaces')
    pybar.left.pack_start(workspaces, 0, 0, 0)
    executor.submit(sway_module, workspaces)

    widget_button = Gtk.MenuButton(popover=pop())
    widget_button.set_direction(Gtk.ArrowType.UP)
    widget_button.get_style_context().add_class('module')
    widget_button.get_style_context().add_class('popover-position-top')
    pybar.right.pack_end(widget_button, 0, 0, 0)

    clock_button = c.label('Clock', style='module')
    executor.submit(clock_module, clock_button)
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
        [["~/.local/bin/bar/weather-new.py", "94002"], 300],
    ]

    for command, interval in right_config:
        module = c.label('', style='module')
        pybar.right.pack_start(module, 0, 0, 0)
        module.set_visible(False)
        module.set_no_show_all(True)
        executor.submit(waybar_module, module, command, interval=interval)

    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
