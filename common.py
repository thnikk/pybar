#!/usr/bin/python3 -u
import sys
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

align = {
    "start": Gtk.Align.START,
    "center": Gtk.Align.CENTER,
    "end": Gtk.Align.END
}


def print_debug(text, color=None, name=None):
    print(text, file=sys.stderr)


class Module(Gtk.MenuButton):
    def __init__(self, icon=True, text=True):
        super().__init__()
        self.set_direction(Gtk.ArrowType.NONE)
        self.box = box('h', spacing=5)
        if icon:
            self.icon = Gtk.Label.new()
            self.box.prepend(self.icon)
        if text:
            self.text = Gtk.Label.new()
            self.text.set_hexpand(True)
            self.text.set_halign(Gtk.Align.CENTER)
            self.box.append(self.text)
        self.set_child(self.box)

    def set_widget(self, text):
        self.widget = Gtk.Popover.new()
        self.widget.set_position(Gtk.PositionType.TOP)
        self.widget_box = box('v')
        self.widget_header = Gtk.Label.new(text)
        self.widget_header.add_css_class('header')
        self.widget_box.prepend(self.widget_header)
        self.widget_content = box('v', spacing=20, style='content')
        self.widget_box.append(self.widget_content)
        self.widget.set_child(self.widget_box)
        self.set_popover(self.widget)


def box(orientation, spacing=0, style=None, ha=None, he=None, va=None, ve=None):
    """ Create box """
    if orientation == 'v':
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
    else:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=spacing)
    if style:
        box.add_css_class(style)
    if ha:
        box.set_halign(align[ha])
    if va:
        box.set_valign(align[va])
    if he:
        box.set_hexpand(True)
    if ve:
        box.set_vexpand(True)
    return box


def button(label=None, style=None):
    button = Gtk.Button.new()
    if label:
        button.set_label(label)
    if style:
        button.add_css_class(style)
    return button


def label(input_text, style=None, ha=None, he=None, va=None, ve=None):
    """ Create label """
    label = Gtk.Label.new()
    label.set_text(f'{input_text}')
    if style:
        label.add_css_class(style)
    if ha:
        label.set_halign(align[ha])
    if va:
        label.set_valign(align[va])
    if he:
        label.set_hexpand(True)
    if ve:
        label.set_vexpand(True)

    return label


def sep(orientation, style=None):
    """ Separator """
    if orientation == 'v':
        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
    if orientation == 'h':
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
    if style:
        separator.get_style_context().add_class(style)
    return separator
