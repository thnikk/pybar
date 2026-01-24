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
import logging
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, Pango, GObject, GLib  # noqa


# Alignment mapping for GTK
align = {
    "fill": Gtk.Align.FILL, "start": Gtk.Align.START,
    "end": Gtk.Align.END, "center": Gtk.Align.CENTER
}
align_map = align


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

        w = width
        h = height

        min_val = self.min_config if self.min_config is not None else min(self.data)
        max_val = self.max_config if self.max_config is not None else max(self.data)
        range_val = max_val - min_val if max_val != min_val else 1

        def get_coords(i):
            x = (i / (len(self.data) - 1)) * w
            val = self.data[i]
            val = max(min(val, max_val), min_val)
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            return x, y

        color = (0.56, 0.63, 0.75)

        cr.set_line_width(1)
        cr.set_source_rgba(color[0], color[1], color[2], 0.1)
        for level in [0, 0.5, 1]:
            y = 10 + (h - 20) * level
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

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

        cr.append_path(path)
        cr.line_to(w, h)
        cr.line_to(0, h)
        cr.close_path()

        linpat = cairo.LinearGradient(0, 0, 0, h)
        linpat.add_color_stop_rgba(0, color[0], color[1], color[2], 0.3)
        linpat.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
        cr.set_source(linpat)
        cr.fill()

        cr.set_source_rgba(color[0], color[1], color[2], 0.5)
        cr.select_font_face("Nunito", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        
        cr.move_to(5, 15)
        cr.show_text(f"{max_val:.1f}")
        cr.move_to(5, h - 5)
        cr.show_text(f"{min_val:.1f}")

        if self.state:
            text = f"{self.state}{self.unit}"
            cr.set_font_size(24)
            extents = cr.text_extents(text)
            tx = w - extents.width - 15
            ty = h - 15
            padding = 10
            radius = 10
            bg_x = tx - padding
            bg_y = ty - extents.height - padding
            bg_w = extents.width + padding * 2
            bg_h = extents.height + padding * 2
            cr.set_source_rgba(0, 0, 0, 0.4)
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
        self.subscribers = {}

    def update(self, name, new_data):
        self.data[name] = new_data
        if name in self.subscribers:
            for callback in self.subscribers[name]:
                GLib.idle_add(callback, new_data)

    def subscribe(self, name, callback):
        if name not in self.subscribers:
            self.subscribers[name] = []
        self.subscribers[name].append(callback)
        if name in self.data:
            GLib.idle_add(callback, self.data[name])

    def get(self, name):
        return self.data.get(name)


state_manager = StateManager()


class Module(Gtk.MenuButton):
    """ Template module """
    def __init__(self, icon=True, text=True):
        super().__init__()
        self.set_direction(Gtk.ArrowType.UP)
        self.get_style_context().add_class('module')
        self.set_cursor_from_name("pointer")
        self.added_styles = []
        
        self.con = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.indicator = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.indicator.get_style_context().add_class('indicator')
        self.indicator_added_styles = []
        
        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.set_vexpand(True)
        self.box.set_halign(Gtk.Align.CENTER)
        
        self.con.append(self.box)
        self.con.append(self.indicator)
        self.set_child(self.con)

        self.icon = None
        self.text = None

        if icon:
            self.icon = Gtk.Label()
            self.icon.set_visible(False)
            self.icon.set_valign(Gtk.Align.CENTER)
            self.box.append(self.icon)
        if text:
            self.text = Gtk.Label()
            self.text.set_visible(False)
            self.text.set_valign(Gtk.Align.CENTER)
            self.text.set_margin_start(0)
            self.box.append(self.text)

    def set_label(self, text):
        """ Set text and toggle visibility """
        if self.text:
            self.text.set_text(str(text))
            self.text.set_visible(bool(text))
            self._update_layout()
        return self

    def get_text(self):
        """ Get current text """
        return self.text.get_text() if self.text else ""

    def set_icon(self, icon):
        """ Set icon and toggle visibility """
        if self.icon:
            self.icon.set_text(str(icon))
            self.icon.set_visible(bool(icon))
            self._update_layout()
        return self

    def get_active(self):
        """ Check if the popover is visible """
        popover = self.get_popover()
        if popover:
            return popover.get_visible()
        return False

    def _update_layout(self):
        """ Update spacing/margins based on what is visible """
        # Count visible children in the main box
        count = 0
        child = self.box.get_first_child()
        while child:
            if child.get_visible():
                count += 1
            child = child.get_next_sibling()
        
        # Set spacing if more than one child is visible
        self.box.set_spacing(5 if count > 1 else 0)

        # Handle text margin if icon is also visible
        if self.text and self.icon:
            if self.text.get_visible() and self.icon.get_visible():
                self.text.set_margin_start(5)
            else:
                self.text.set_margin_start(0)

    def _update_spacing(self):
        """ Alias for compatibility """
        self._update_layout()

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
        if isinstance(style_class, str):
            self.get_style_context().add_class(style_class)
            self.added_styles.append(style_class)
        elif isinstance(style_class, list):
            for item in style_class:
                self.get_style_context().add_class(item)
                self.added_styles.append(item)
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
        self.set_direction(directions.get(position, Gtk.ArrowType.UP))
        return self


class Widget(Gtk.Popover):
    """ Template widget"""
    def __init__(self):
        super().__init__()
        self.set_position(Gtk.PositionType.TOP)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)

    def heading(self, string):
        self.box.append(label(string))

    def draw(self):
        self.box.set_visible(True)
        self.set_child(self.box)


def print_debug(msg, name=None, color=None) -> None:
    """ Print debug message using logging """
    if not name:
        frame = inspect.stack()[1]
        name = frame[0].f_code.co_filename.split('/')[-1].split('.')[0]
    logger = logging.getLogger(name)
    logger.debug(msg)


def box(orientation, spacing=0, style=None):
    """ Create box """
    obox = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL if orientation == 'v' else Gtk.Orientation.HORIZONTAL,
        spacing=spacing
    )
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
    if ha in align:
        widget.set_halign(align[ha])
    if length and label:
        child = widget.get_child()
        if isinstance(child, Gtk.Label):
            child.set_max_width_chars(length)
            child.set_ellipsize(Pango.EllipsizeMode.END)
            if len(label) > length:
                widget.set_tooltip_text(label)
    return widget


def sep(orientation, style=None):
    """ Separator """
    separator = Gtk.Separator(
        orientation=Gtk.Orientation.VERTICAL if orientation == 'v' else Gtk.Orientation.HORIZONTAL
    )
    if style:
        separator.get_style_context().add_class(style)
    return separator


def label(input_text, style=None, va=None, ha=None, he=False, wrap=None, length=None):
    """ Create label """
    text = Gtk.Label(label=str(input_text))
    if style:
        text.get_style_context().add_class(style)
    if va in align:
        text.set_valign(align[va])
    if ha in align:
        text.set_halign(align[ha])
    text.set_hexpand(bool(he))
    if isinstance(wrap, int):
        text.set_wrap(True)
        text.set_max_width_chars(wrap)
    if isinstance(length, int):
        text.set_max_width_chars(length)
        text.set_ellipsize(Pango.EllipsizeMode.END)
        if len(str(input_text)) > length:
            text.set_tooltip_text(str(input_text))
    return text


def slider(value, min=0, max=100, style=None, scrollable=True):
    """ Create a slider """
    widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min, max, 1)
    widget.set_value(value)
    widget.set_draw_value(False)
    if style:
        widget.get_style_context().add_class(style)

    if not scrollable:
        scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_scroll(controller, dx, dy):
            # Find the parent ScrolledWindow
            parent = widget.get_parent()
            while parent and not isinstance(parent, Gtk.ScrolledWindow):
                parent = parent.get_parent()

            if parent:
                adj = parent.get_vadjustment()
                if adj:
                    adj.set_value(adj.get_value() + (dy * 30))
            return True

        scroll_controller.connect("scroll", on_scroll)
        widget.add_controller(scroll_controller)

    return widget


def level(min=0, max=100, value=0, style=None):
    """ Create level bar """
    widget = Gtk.LevelBar.new_with_offsets(min, max)
    widget.set_value(value)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def scroll(width=0, height=0, style=None, vexpand=False, hexpand=True):
    """ Create scrollable window """
    window = Gtk.ScrolledWindow(hexpand=hexpand, vexpand=vexpand)
    window.set_min_content_width(width)
    window.set_min_content_height(height)
    if height > 0:
        window.set_max_content_height(height)
    if width > 0:
        window.set_max_content_width(width)
    window.set_propagate_natural_width(True)
    window.set_propagate_natural_height(True)
    window.set_policy(
        Gtk.PolicyType.AUTOMATIC if width else Gtk.PolicyType.NEVER,
        Gtk.PolicyType.AUTOMATIC if height else Gtk.PolicyType.NEVER
    )
    if style:
        window.get_style_context().add_class(style)
    return window
