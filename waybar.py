#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output
import json
import os
import time
import gi
import common as c
from weather_widget import weather_widget
from hoyo_widget import hoyo_widget
from updates_widget import updates_widget
from git_widget import git_widget
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk


def pop(name):
    """ thing """
    popover = Gtk.Popover()
    popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
    popover.set_position(Gtk.PositionType.TOP)
    popover.set_transitions_enabled(False)
    if name == 'weather':
        widget = weather_widget('~/.cache/weather-widget.json')
    elif name == 'genshin':
        widget = hoyo_widget('genshin')
    elif name == 'hsr':
        widget = hoyo_widget('hsr')
    elif name == 'updates':
        widget = updates_widget()
    elif name == 'git':
        widget = git_widget('~/Development/Git/waybar-modules')
    else:
        widget = c.box('v', style='widget', spacing=20)
        widget.add(c.label('Example popover', style='heading'))
        for x in range(0, 3):
            widget.add(c.label(f'Item {x}'))
    widget.show_all()
    popover.add(widget)
    # popover.set_pointing_to(Gdk.Rectangle(0, 0, 0, 0))
    popover.set_position(Gtk.PositionType.TOP)
    return popover


def cache(name, command, interval):
    """ Save command output to cache file """
    while True:
        command = [os.path.expanduser(arg) for arg in command]
        with open(
            os.path.expanduser(f'~/.cache/pybar/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            file.write(check_output(command).decode())
        time.sleep(interval)


def module(name):
    """ Waybar module """
    button = c.mbutton(style='module')
    button.set_direction(Gtk.ArrowType.UP)
    button.set_visible(False)
    button.set_no_show_all(True)

    def get_output():
        try:
            with open(
                os.path.expanduser(f'~/.cache/pybar/{name}.json'),
                'r', encoding='utf-8'
            ) as file:
                output = json.loads(file.read())
            if output['text']:
                button.set_visible(True)
                button.set_label(output['text'])
            else:
                button.set_visible(False)
            if output['tooltip']:
                if button.get_tooltip_markup() != output['tooltip']:
                    button.set_popover(pop(name))
                button.set_tooltip_markup(output['tooltip'])
                button.set_has_tooltip(False)
            try:
                c.add_style(button, output['class'])
            except KeyError:
                pass
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass
        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return button
