#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
from subprocess import check_output
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango


def dict_from_cmd(command) -> dict:
    command = [os.path.expanduser(part) for part in command]
    return json.loads(check_output(command))


def pop():
    """ d """
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


class Bar:
    """ Bar class"""
    def __init__(self, spacing=0):
        self.window = Gtk.Window()
        self.bar = box('h', style='bar', spacing=spacing)
        self.left = box('h', style='modules-left', spacing=spacing)
        self.center = box('h', style='modules-center', spacing=spacing)
        self.right = box('h', style='modules-right', spacing=spacing)
        self.bar.pack_start(self.left, 0, 0, 0)
        self.bar.set_center_widget(self.center)
        self.bar.pack_end(self.right, 0, 0, 0)
        self.window.add(self.bar)

    def css(self, file):
        """ Load CSS from file """
        css_provider = Gtk.CssProvider()
        css_provider.load_from_path(os.path.expanduser(file))
        screen = Gdk.Screen.get_default()
        style_context = Gtk.StyleContext()
        style_context.add_provider_for_screen(
            screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def modules(self, modules):
        """ Add modules to bar """
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.get_style_context().add_class("bar")

        for index, position in enumerate(["left", "center", "right"]):
            section = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            section.get_style_context().add_class(position)
            for module in modules[index]:
                section.pack_start(module(), False, False, 0)
            main.pack_start(section, position == "center", False, 0)

        self.window.add(main)

    def start(self):
        """ Start bar """
        GtkLayerShell.init_for_window(self.window)

        # Anchor and stretch to bottom of the screen
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.BOTTOM, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.LEFT, 1)
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.RIGHT, 1)

        # Set margin to make bar more readable for testing
        margin = 10
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.LEFT, margin)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.RIGHT, margin)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.BOTTOM, margin)
        # GtkLayerShell.set_margin(
        #     self.window, GtkLayerShell.Edge.TOP, 200)

        GtkLayerShell.set_namespace(self.window, 'waybar')

        # Reserve part of screen
        GtkLayerShell.auto_exclusive_zone_enable(self.window)

        self.window.show_all()
        self.window.connect('destroy', Gtk.main_quit)
        Gtk.main()
