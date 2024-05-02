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
import widgets
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib


def get_widget(name, info):
    """ Get widget box from appropriate widget """
    match name:
        case 'weather':
            return widgets.weather_widget(info)
        case 'genshin':
            return widgets.hoyo_widget(info, 'genshin')
        case 'hsr':
            return widgets.hoyo_widget(info, 'hsr')
        case 'updates':
            return widgets.updates_widget(info)
        case 'git':
            return widgets.git_widget(info)
        case 'ups':
            return widgets.ups_widget(info)
        case _:
            return widgets.generic_widget(name, info)


def pop(name, info):
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
                        button.set_popover(pop(name, output['widget']))
                    except KeyError:
                        # button.set_popover(pop(name))
                        pass
                button.set_tooltip_markup(output['tooltip'])
                try:
                    output['widget']
                    button.set_has_tooltip(False)
                except KeyError:
                    pass
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
