#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output, CalledProcessError
import json
import os
import time
import gi
import common as c
from weather_widget import weather_widget
from hoyo_widget import hoyo_widget
from updates_widget import updates_widget
from git_widget import git_widget
from ups_widget import ups_widget
from privacy_widget import privacy_widget
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib


def get_widget(name, info=None):
    """ Get widget box from appropriate widget """
    match name:
        case 'weather':
            return weather_widget(info)
        case 'genshin':
            return hoyo_widget(info, 'genshin')
        case 'hsr':
            return hoyo_widget(info, 'hsr')
        case 'updates':
            return updates_widget(info)
        case 'git':
            return git_widget(info)
        case 'ups':
            return ups_widget(info)
        case 'privacy':
            return privacy_widget(info)
        case _:
            widget = c.box('v', style='widget', spacing=20)
            widget.add(c.label('Example popover', style='heading'))
            for x in range(0, 3):
                widget.add(c.label(f'Item {x}'))
            return widget


def pop(name, info=None):
    """ Make popover widget """
    popover = Gtk.Popover()
    popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
    popover.set_position(Gtk.PositionType.TOP)
    popover.set_transitions_enabled(False)
    widget = get_widget(name, info)
    widget.show_all()
    popover.add(widget)
    popover.set_position(Gtk.PositionType.TOP)
    return popover


def cache(name, command, interval):
    """ Save command output to cache file """
    while True:
        cache_dir = os.path.expanduser('~/.cache/pybar')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        command = [os.path.expanduser(arg) for arg in command]
        with open(
            os.path.expanduser(f'{cache_dir}/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            try:
                file.write(check_output(command).decode())
            except CalledProcessError:
                pass
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
            try:
                if (
                    button.get_tooltip_markup() != output['tooltip']
                    and not button.get_active()
                ):
                    try:
                        button.set_popover(pop(name, info=output['widget']))
                    except KeyError:
                        button.set_popover(pop(name))
                button.set_tooltip_markup(output['tooltip'])
                button.set_has_tooltip(False)
            except KeyError:
                pass
            try:
                if not output['class']:
                    raise ValueError
                c.add_style(button, output['class'])
            except (KeyError, ValueError):
                for s in ['red', 'green', 'blue', 'orange', 'yellow']:
                    button.get_style_context().remove_class(s)
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass
        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return button
