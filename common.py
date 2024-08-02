#!/usr/bin/python3 -u
"""
Description: Helper functions
Author: thnikk
"""
import inspect
from datetime import datetime
import sys
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk, Gdk, GtkLayerShell, Pango, GObject  # noqa


align = {
    "fill": Gtk.Align.FILL, "start": Gtk.Align.START,
    "end": Gtk.Align.END, "center": Gtk.Align.CENTER
}


class ModuleCache():
    def __init__(self):
        self.text = None
        self.icon = None
        self.tooltip = None
        self.widget = None


class Module(Gtk.MenuButton):
    """ Template module """
    def __init__(self, icon=True, text=True):
        super().__init__()
        self.cache = ModuleCache()
        self.set_direction(Gtk.ArrowType.UP)
        self.get_style_context().add_class('module')
        self.default_styles = self.get_style_context().list_classes()
        self.box = box('h', spacing=5)
        if icon:
            self.icon = Gtk.Label()
            self.box.pack_start(self.icon, 0, 0, 0)
        if text:
            self.text = Gtk.Label()
            self.box.pack_end(self.text, 1, 1, 0)
        self.add(self.box)
        self.add_events(Gdk.EventMask.SCROLL_MASK)
        self.add_events(Gdk.EventMask.SMOOTH_SCROLL_MASK)

    def reset_style(self):
        """ Reset module style back to default """
        if self.default_styles != self.get_styles():
            for style in self.get_styles():
                if style not in self.default_styles:
                    self.get_style_context().remove_class(style)

    def get_styles(self):
        """ Get styles """
        return self.get_style_context().list_classes()

    def add_style(self, style_class):
        """ Set style """
        self.get_style_context().add_class(style_class)
        return self

    def set_widget(self, box):
        """ Set widget """
        widget = Widget()
        widget.box.add(box)
        widget.draw()
        self.set_popover(widget)

    def set_position(self, position):
        """ Set popover direction """
        directions = {
            "top": Gtk.ArrowType.DOWN,
            "left": Gtk.ArrowType.RIGHT,
            "bottom": Gtk.ArrowType.UP,
            "right": Gtk.ArrowType.LEFT,
        }
        try:
            direction = directions[position]
        except KeyError:
            return self
        self.set_direction(direction)
        return self


GObject.signal_new(
    'update', Module, GObject.SIGNAL_RUN_LAST, GObject.TYPE_BOOLEAN, ())


class Widget(Gtk.Popover):
    """ Template widget"""
    def __init__(self):
        super().__init__()
        self.set_constrain_to(Gtk.PopoverConstraint.NONE)
        self.set_position(Gtk.PositionType.TOP)
        self.set_transitions_enabled(False)
        self.box = box('v', spacing=20)

    def heading(self, string):
        self.box.add(label(string, style='heading'))

    def draw(self):
        self.box.show_all()
        self.add(self.box)


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


def level(min, max, value):
    """ Level bar """
    bar_box = box('v')
    bar = Gtk.LevelBar().new_for_interval(min, max)
    bar.set_value(value)
    bar_box.pack_start(bar, 1, 0, 0)
    return bar_box


def slider(value, min=0, max=100, style=None):
    """ Create a slider """
    widget = Gtk.Scale().new_with_range(
        orientation=Gtk.Orientation.HORIZONTAL,
        min=min, max=max, step=1
    )
    widget.set_value(value)
    widget.set_draw_value(False)
    if style:
        widget.get_style_context().add_class(style)
    return widget


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
    """ Remove style from widget """
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().remove_class(item)
    else:
        widget.get_style_context().remove_class(style)


def button(label=None, style=None, ha=None, length=None):
    """ Button """
    widget = Gtk.Button.new()
    if label:
        widget.set_label(label)
    if style:
        widget.get_style_context().add_class(style)
    try:
        widget.props.halign = align[ha]
    except KeyError:
        pass
    if length:
        widget.get_child().set_max_width_chars(length)
        widget.get_child().set_ellipsize(
            Pango.EllipsizeMode.END)
        if len(label) > length + 3:
            widget.set_tooltip_text(label)
    return widget


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

    try:
        text.props.valign = align[va]
    except KeyError:
        pass

    try:
        text.props.halign = align[ha]
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
        if len(input_text) > length + 3:
            text.set_tooltip_text(input_text)

    return text
