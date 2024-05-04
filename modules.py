#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import run, check_output, CalledProcessError
from datetime import datetime
import json
import os
import time
import gi
import common as c
import widgets
from pulse import Pulse
from calendar_widget import calendar_widget
from volume_widget import volume_widget
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib  # noqa


def get_widget(name, info=None):
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
        case 'calendar':
            return calendar_widget()
        case 'volume':
            return volume_widget()
        case _:
            return widgets.generic_widget(name, info)


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


def module(name, icons=None):
    """ Waybar module """
    # builtin = {
    #     "clock": clock,
    #     "workspaces": workspaces,
    #     "volume": volume
    # }
    if name == 'clock':
        return clock()
    elif name == 'workspaces':
        return workspaces(icons)
    elif name == 'volume':
        return volume()

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
                try:
                    output = json.loads(file.read())
                except json.decoder.JSONDecodeError:
                    return True
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


def switch_workspace(_, workspace):
    """ Click action """
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def workspaces(icons):
    module = c.box('h', style='workspaces')
    buttons = []
    for x in range(0, 11):
        try:
            button = c.button(label=icons[str(x)], style='workspace')
        except (KeyError, TypeError):
            try:
                button = c.button(label=icons['default'], style='workspace')
            except KeyError:
                button = c.button(label=str(x), style='workspace')
        button.hide()
        button.connect('clicked', switch_workspace, x)
        buttons.append(button)
        module.add(button)

    def get_workspaces():
        with open(
            os.path.expanduser('~/.cache/pybar/sway.json'),
            'r', encoding='utf-8'
        ) as file:
            try:
                cache = json.loads(file.read())
            except json.decoder.JSONDecodeError:
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


def clock():
    """ Clock module """
    label = Gtk.MenuButton(popover=pop('calendar'))
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')

    def get_time():
        label.set_label(datetime.now().strftime(' %I:%M %m/%d'))
        return True

    if get_time():
        GLib.timeout_add(1000, get_time)
        return label


def volume():
    """ """
    label = Gtk.MenuButton(popover=pop('volume'))
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')

    def get_volume():
        p = Pulse()
        label.set_label(f' {p.get_sink_volume(p.get_default_sink())}%')
        return True

    if get_volume():
        GLib.timeout_add(1000, get_volume)
        return label
