#!/usr/bin/python3 -u
"""
Description: Helper functions
Author: thnikk
"""
import inspect
from datetime import datetime
import sys
import gi
import math
import cairo
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, Pango, GObject, GLib  # noqa


align = {
    "fill": Gtk.Align.FILL, "start": Gtk.Align.START,
    "end": Gtk.Align.END, "center": Gtk.Align.CENTER
}


class Graph(Gtk.DrawingArea):
    """ Smooth history graph """
    def __init__(self, data, state=None, unit=None, min_config=None, max_config=None, height=120, width=300):
        super().__init__()
        self.set_content_height(height)
        self.set_content_width(width)
        self.set_hexpand(True)
        self.data = data
        self.state = state
        self.unit = unit
        self.min_config = min_config
        self.max_config = max_config
        self.set_draw_func(self.on_draw)

    def update_data(self, data, state):
        self.data = data
        self.state = state
        self.queue_draw()

    def on_draw(self, area, cr, width, height, *args):
        if not self.data or len(self.data) < 2:
            return

        # Use full width/height for the fill, but slight padding for line
        w = width
        h = height

        min_val = self.min_config if self.min_config is not None else min(self.data)
        max_val = self.max_config if self.max_config is not None else max(self.data)
        range_val = max_val - min_val if max_val != min_val else 1

        def get_coords(i):
            x = (i / (len(self.data) - 1)) * w
            # Leave 10px padding top/bottom for the line and markers
            val = self.data[i]
            # Clip value to min/max
            val = max(min(val, max_val), min_val)
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            return x, y

        # Colors from style.css (blue #8fa1be)
        color = (0.56, 0.63, 0.75)

        # Draw grid lines (Levels)
        cr.set_line_width(1)
        cr.set_source_rgba(color[0], color[1], color[2], 0.1)
        for level in [0, 0.5, 1]:
            y = 10 + (h - 20) * level
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        # Draw smooth curves
        x0, y0 = get_coords(0)
        cr.move_to(x0, y0)

        for i in range(len(self.data) - 1):
            x1, y1 = get_coords(i)
            x2, y2 = get_coords(i + 1)
            cr.curve_to(x1 + (x2 - x1) / 2, y1, x1 + (x2 - x1) / 2, y2, x2, y2)
        
        cr.set_line_width(2)
        cr.set_source_rgb(*color)
        path = cr.copy_path()
        cr.stroke()

        # Fill the area
        cr.append_path(path)
        cr.line_to(w, h)
        cr.line_to(0, h)
        cr.close_path()

        linpat = cairo.LinearGradient(0, 0, 0, h)
        linpat.add_color_stop_rgba(0, color[0], color[1], color[2], 0.3)
        linpat.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
        cr.set_source(linpat)
        cr.fill()

        # Draw Legend (Min/Max values)
        cr.set_source_rgba(color[0], color[1], color[2], 0.5)
        cr.select_font_face("Nunito", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        
        # Max label
        cr.move_to(5, 15)
        cr.show_text(f"{max_val:.1f}")
        # Min label
        cr.move_to(5, h - 5)
        cr.show_text(f"{min_val:.1f}")

        # Draw current value overlay (Bottom Right)
        if self.state:
            text = f"{self.state}{self.unit}"
            cr.set_font_size(24)
            extents = cr.text_extents(text)
            
            # Text position
            tx = w - extents.width - 15
            ty = h - 15
            
            # Subtle background for readability
            padding = 10
            radius = 10
            bg_x = tx - padding
            bg_y = ty - extents.height - padding
            bg_w = extents.width + padding * 2
            bg_h = extents.height + padding * 2
            
            cr.set_source_rgba(0, 0, 0, 0.4)
            # Rounded rectangle
            cr.new_sub_path()
            cr.arc(bg_x + radius, bg_y + radius, radius, math.pi, 3 * math.pi / 2)
            cr.arc(bg_x + bg_w - radius, bg_y + radius, radius, 3 * math.pi / 2, 2 * math.pi)
            cr.arc(bg_x + bg_w - radius, bg_y + bg_h - radius, radius, 0, math.pi / 2)
            cr.arc(bg_x + radius, bg_y + bg_h - radius, radius, math.pi / 2, math.pi)
            cr.close_path()
            cr.fill()
            
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(tx, ty)
            cr.show_text(text)


class StateManager:
    def __init__(self):
        self.data = {}
        self.subscribers = {}  # {name: [callback, ...]}

    def update(self, name, new_data):
        self.data[name] = new_data
        if name in self.subscribers:
            for callback in self.subscribers[name]:
                GLib.idle_add(callback, new_data)

    def subscribe(self, name, callback):
        if name not in self.subscribers:
            self.subscribers[name] = []
        self.subscribers[name].append(callback)
        # Immediately provide current data if available
        if name in self.data:
            GLib.idle_add(callback, self.data[name])

    def get(self, name):
        return self.data.get(name)


state_manager = StateManager()


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
        self.set_cursor_from_name("pointer")
        self.added_styles = []
        self.con = box('v')
        self.indicator = box('h', style='indicator')
        self.indicator_added_styles = []
        self.box = box('h', spacing=5)
        self.box.set_vexpand(True)
        self.con.append(self.box)
        self.con.append(self.indicator)
        self.con.show()

        if icon:
            self.icon = Gtk.Label()
            self.box.prepend(self.icon)
        if text:
            self.text = Gtk.Label()
            self.text.set_hexpand(True)
            self.box.append(self.text)
        self.set_child(self.con)

    def reset_style(self):
        """ Reset module style back to default """
        for style in self.added_styles:
            self.get_style_context().remove_class(style)
        self.added_styles = []

        for style in self.indicator_added_styles:
            self.indicator.get_style_context().remove_class(style)
        self.indicator_added_styles = []

    def add_style(self, style_class):
        """ Set style """
        self.get_style_context().add_class(style_class)
        if isinstance(style_class, str):
            self.added_styles.append(style_class)
        else:
            self.added_styles.extend(style_class)
        return self

    def set_widget(self, box):
        """ Set widget """
        widget = Widget()
        widget.box.append(box)
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
        # self.set_autohide(False)
        self.set_position(Gtk.PositionType.TOP)
        self.box = box('v', spacing=20)

    def heading(self, string):
        self.box.append(label(string))

    def draw(self):
        self.box.show()
        self.set_child(self.box)


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
    bar.set_vexpand(True)
    bar_box.append(bar)
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
