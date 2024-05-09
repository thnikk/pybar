#!/usr/bin/python3 -u
"""
Description: Load module and popover widgets
Author: thnikk
"""
from subprocess import run, check_output, CalledProcessError
from datetime import datetime
import json
import os
import time
from glob import glob
import gi
import common as c
import widgets
import pulsectl
from calendar_widget import calendar_widget
from volume_widget import volume_widget
# from modules_new import volume as volume_new
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


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
        case 'xdrip':
            return widgets.xdrip(info)
        case 'calendar':
            return calendar_widget()
        case 'volume':
            return volume_widget(info)
        case 'backlight':
            return widgets.backlight(info)
        case 'battery':
            return widgets.battery(info)
        case 'network':
            return widgets.network(info)
        case 'power':
            return widgets.power()
        case 'sales':
            return widgets.sales(info)
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
                c.print_debug('Failed to load module.', color='red', name=name)
                pass
        time.sleep(interval)


def module(name, config):
    """ Waybar module """
    builtin = {
        'clock': clock,
        'workspaces': workspaces,
        'volume': volume,
        'backlight': backlight,
        'battery': battery,
        'power': power,
        'test': test
    }

    if name in list(builtin):
        try:
            config = config['modules'][name]
        except KeyError:
            config = None
        return builtin[name](config)

    button = Gtk.MenuButton()
    c.add_style(button, 'module')
    button.set_direction(Gtk.ArrowType.UP)
    button.set_visible(False)
    button.set_no_show_all(True)

    def get_output():
        """ Create module using cache """
        # Load cache
        try:
            with open(
                os.path.expanduser(f'~/.cache/pybar/{name}.json'),
                'r', encoding='utf-8'
            ) as file:
                output = json.loads(file.read())
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            return True
        if button.get_label() == output['text']:
            return True

        # Set label
        if output['text']:
            button.set_visible(True)
            button.set_label(output['text'])
        else:
            if button.get_visible():
                button.set_visible(False)
                button.set_label('')
            return True

        # Set tooltip or popover
        try:
            if (
                button.get_tooltip_markup() != output['tooltip']
                and not button.get_active()
            ):
                try:
                    button.set_popover(pop(name, info=output['widget']))
                except KeyError:
                    pass
                button.set_tooltip_markup(output['tooltip'])
            try:
                output['widget']
                button.set_has_tooltip(False)
            except KeyError:
                pass
        except KeyError:
            pass

        # Set class
        try:
            if not output['class']:
                raise ValueError
            c.add_style(button, output['class'])
        except (KeyError, ValueError):
            for s in ['red', 'green', 'blue', 'orange', 'yellow']:
                button.get_style_context().remove_class(s)
        return True
    if get_output():
        # Timeout of less than 1 second breaks tooltips
        GLib.timeout_add(1000, get_output)
        return button


def switch_workspace(_, workspace):
    """ Click action """
    run(['swaymsg', 'workspace', 'number', str(workspace)], check=False)


def workspaces(config=None):
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


def clock(config=None):
    """ Clock module """
    label = Gtk.MenuButton(popover=pop('calendar'))
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')

    def get_time():
        try:
            datestring = config['format']
        except (TypeError, KeyError):
            datestring = '%I:%M %m/%d'
        new = datetime.now().strftime(f' {datestring}')
        if new == label.get_label():
            return True
        label.set_label(new)
        return True

    if get_time():
        GLib.timeout_add(1000, get_time)
        return label


def battery(config=None):
    """ Battery module """
    label = Gtk.MenuButton()
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')
    c.add_style(label, 'module-fixed')

    def get_percent():
        info = {}
        full = 0
        now = 0
        for path in glob('/sys/class/power_supply/BAT*'):
            battery_info = {}
            for file in ["energy_now", "energy_full"]:
                with open(f"{path}/{file}", 'r', encoding='utf-8') as f:
                    value = int(f.read())
                    battery_info[file] = value
                    if file == 'energy_now':
                        now += value
                    elif file == 'energy_full':
                        full += value
            info[path.split('/')[-1]] = battery_info
        if not label.get_active():
            label.set_popover(pop('battery', info))
        percentage = str(round((now/full)*100))
        label.set_label(f' {percentage}%')
        return True
    if get_percent():
        GLib.timeout_add(60000, get_percent)
        return label


def backlight(config=None):
    """ Backlight module """
    label = Gtk.MenuButton()
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')
    c.add_style(label, 'module-fixed')

    def get_brightness():
        base_path = "/sys/class/backlight/intel_backlight"
        if not os.path.exists(base_path):
            return False
        info = {}
        for item in ["brightness", "max_brightness"]:
            with open(f'{base_path}/{item}', 'r', encoding='utf-8') as file:
                info[item] = int(file.read())
        if not label.get_active():
            label.set_popover(pop('backlight', info))
        percentage = round((info['brightness']/info['max_brightness'])*100)
        label.set_label(f' {percentage}%')
        return True

    if get_brightness():
        GLib.timeout_add(1000, get_brightness)
        return label


def action(button, event):
    """ Scroll action """
    with pulsectl.Pulse('volume-increaser') as pulse:
        default = pulse.sink_default_get()
        if event.direction == Gdk.ScrollDirection.UP:
            if default.volume.value_flat < 1:
                pulse.volume_change_all_chans(default, 0.01)
            else:
                pulse.volume_set_all_chans(default, 1)
        elif event.direction == Gdk.ScrollDirection.DOWN:
            pulse.volume_change_all_chans(default, -0.01)
    get_volume(button)


def get_volume(label):
    """ Get volume data from cache """
    try:
        with open(
            os.path.expanduser('~/.cache/pybar/pulse.json'),
            'r', encoding='utf-8'
        ) as file:
            cache = json.loads(file.read())
    except (FileNotFoundError, json.decoder.JSONDecodeError):
        return True

    with pulsectl.Pulse() as pulse:
        volume = round(pulse.sink_default_get().volume.value_flat * 100)
        icons = ["  ", " ", ""]
        icon_index = int(volume // (100 / len(icons)))
        icon = icons[icon_index]
        new = f'{icon} {volume}%'
        if new != label.get_label():
            label.set_label(new)
    if not label.get_active():
        label.set_popover(pop('volume', cache))
    return True


def volume(config=None):
    """ Volume module """
    label = Gtk.MenuButton()
    label.set_direction(Gtk.ArrowType.UP)
    label.get_style_context().add_class('module')
    c.add_style(label, 'module-fixed')
    label.add_events(Gdk.EventMask.SCROLL_MASK)
    label.connect('scroll-event', action)

    if get_volume(label):
        GLib.timeout_add(1000, get_volume, label)
        return label


def click_action(module, event):
    c.print_debug(event.button)


def scroll_action(module, event):
    c.print_debug(event.direction)


def test(config=None):
    module = c.Module()
    module.icon.set_label('')
    module.text.set_label('0')

    widget = c.Widget()
    widget.heading('Test')
    widget.draw()
    module.set_popover(widget)

    # module.connect('button-press-event', click_action)
    # module.connect('scroll-event', scroll_action)

    def update():
        num = int(module.text.get_label()) + 1
        module.text.set_label(str(num))
        return True

    if update():
        GLib.timeout_add(1000, update)
        return module


def power(config=None):
    """ Power module """
    module = c.Module()
    module.icon.set_label('')

    def power_action(button, command, widget):
        """ Action for power menu buttons """
        widget.popdown()
        run(command, check=False, capture_output=False)

    buttons = {
        "Lock  ": ["swaylock"],
        "Log out  ": ["swaymsg", "exit"],
        "Suspend  ": ["systemctl", "suspend"],
        "Reboot  ": ["systemctl", "reboot"],
        "Reboot to UEFI  ": ["systemctl", "reboot", "--firmware-setup"],
        "Shut down  ": ["systemctl", "poweroff"],
    }

    widget = c.Widget()
    power_box = c.box('v', style='box')
    for icon, command in buttons.items():
        button = c.button(label=icon, ha='end', style='power-item')
        button.connect('clicked', power_action, command, widget)
        power_box.add(button)
        if icon != list(buttons)[-1]:
            power_box.add(c.sep('h'))

    widget.box.add(power_box)
    widget.draw()
    module.set_popover(widget)

    return module
