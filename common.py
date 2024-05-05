#!/usr/bin/python3 -u
"""
Description: Helper functions
Author: thnikk
"""
import os
import json
import inspect
from datetime import datetime
import sys
from subprocess import check_output, Popen
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango  # noqa


def print_debug(msg, name=None, color=38) -> None:
    """ Print debug message """
    colors = {
        "gray": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34,
        "purple": 36, "cyan": 36
    }
    if isinstance(color, str):
        try:
            color = colors[color]
        except KeyError:
            color = 31
    if not name:
        # Get filename of program calling this function
        frame = inspect.stack()[1]
        name = frame[0].f_code.co_filename.split('/')[-1].split('.')[0]
    # Color the name using escape sequences
    colored_name = f"\033[{color}m{name}\033[0m"
    # Get the time in the same format as waybar
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    # Print the debug message
    print(f'[{timestamp}] [{colored_name}] {msg}', file=sys.stderr)


def level(value, min=0, max=100, style=None):
    """ Create level bar """
    bar = Gtk.LevelBar().new_for_interval(min, max)
    bar.set_value(value)
    if style:
        bar.get_style_context().add_class(style)
    return bar


def dict_from_cmd(command) -> dict:
    """ Get json output of command """
    command = [os.path.expanduser(part) for part in command]
    return json.loads(check_output(command))


def scroll(width=0, height=0, style=None):
    """ Create scrollable window """
    window = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
    window.set_max_content_width(width)
    window.set_min_content_width(width)
    window.set_min_content_height(height)
    window.set_max_content_height(height)
    window.set_propagate_natural_width(True)
    window.set_propagate_natural_height(True)
    if width:
        hs = Gtk.PolicyType.ALWAYS
    else:
        hs = Gtk.PolicyType.NEVER
    if height:
        vs = Gtk.PolicyType.ALWAYS
    else:
        vs = Gtk.PolicyType.NEVER
    window.set_policy(
        hscrollbar_policy=hs,
        vscrollbar_policy=vs
    )
    if style:
        window.get_style_context().add_class(style)
    return window


def click_link(module, url):
    """ Click action """
    del module
    Popen(['xdg-open', url])


def pop():
    """ Create popover widget """
    popover = Gtk.Popover()
    popover.set_constrain_to(Gtk.PopoverConstraint.NONE)
    popover.set_modal(True)
    popover.set_position(Gtk.PositionType.TOP)
    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    vbox.pack_start(Gtk.ModelButton(label="Item 1"), False, True, 10)
    vbox.pack_start(Gtk.Label(label="Item 2"), False, True, 10)
    vbox.show_all()
    popover.add(vbox)
    popover.set_position(Gtk.PositionType.TOP)
    return popover


def box(orientation, spacing=0, style=None):
    """ Create box """
    if orientation == 'v':
        obox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    else:
        obox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if style:
        obox.get_style_context().add_class(style)
    return obox


def add_style(widget, style):
    """ Add style to widget """
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().add_class(item)
    else:
        widget.get_style_context().add_class(style)


def del_style(widget, style):
    """ Add style to widget """
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().remove_class(item)
    else:
        widget.get_style_context().remove_class(style)


def button(label=None, style=None):
    """ Button """
    __button__ = Gtk.Button.new()
    if label:
        __button__.set_label(label)
    if style:
        __button__.get_style_context().add_class(style)
    return __button__


def mbutton(label=None, style=None):
    """ Button """
    __button__ = Gtk.MenuButton.new()
    if label:
        __button__.set_label(label)
    if style:
        __button__.get_style_context().add_class(style)
    return __button__


def v_lines(lines, right=False, style=None) -> Gtk.Box:
    """ Takes list and returns GTK nested boxes """
    container = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL, spacing=0)
    if style:
        container.get_style_context().add_class(style)
    for line in lines:
        line_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        text = Gtk.Label()
        text.set_label(f'{line}')
        if right:
            line_box.pack_end(text, False, False, 0)
        else:
            line_box.pack_start(text, False, False, 0)
        container.pack_start(line_box, True, False, 0)
    return container


def h_lines(lines, style=None) -> Gtk.Box:
    """ Takes list and returns GTK nested boxes """
    container = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    if style:
        container.get_style_context().add_class(style)
    for line in lines:
        text = Gtk.Label()
        text.set_label(f'{line}')
        container.pack_start(text, True, False, 0)
    return container


def sep(orientation, style=None):
    """ Separator """
    if orientation == 'v':
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
    if orientation == 'h':
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    if style:
        separator.get_style_context().add_class(style)
    return separator


def label(
    input_text, style=None, va=None, ha=None, he=False, wrap=None,
    length=None
):
    """ Create label """
    text = Gtk.Label()
    text.set_text(f'{input_text}')
    if style:
        text.get_style_context().add_class(style)

    options = {
        "fill": Gtk.Align.FILL, "start": Gtk.Align.START,
        "end": Gtk.Align.END, "center": Gtk.Align.CENTER
    }

    try:
        text.props.valign = options[va]
    except KeyError:
        pass

    try:
        text.props.halign = options[ha]
    except KeyError:
        pass
    if isinstance(he, bool):
        text.props.hexpand = he

    if isinstance(wrap, int):
        text.props.wrap = True
        text.set_max_width_chars(wrap)

    if isinstance(length, int):
        text.set_max_width_chars(length)
        text.set_ellipsize(Pango.EllipsizeMode.END)

    return text
