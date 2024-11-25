#!/usr/bin/python3 -u
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib # noqa


align = {
    "start": Gtk.Align.START,
    "center": Gtk.Align.CENTER,
    "end": Gtk.Align.END
}

orientation = {
    "h": Gtk.Orientation.HORIZONTAL,
    "v": Gtk.Orientation.VERTICAL,
}


class Label(Gtk.Label):
    def __init__(self, text):
        super().__init__()
        self.set_label(text)

    def ha(self, value):
        self.set_halign(align[value])
        return self

    def va(self, value):
        self.set_valign(align[value])
        return self

    def he(self, value=True):
        self.set_hexpand(value)
        return self

    def ve(self, value=True):
        self.set_vexpand(value)
        return self

    def css(self, css_class):
        self.add_css_class(css_class)
        return self


class Box(Gtk.Box):
    def __init__(self, orientation_string):
        super().__init__()
        self.set_orientation(orientation[orientation_string])

    def spacing(self, value):
        self.set_spacing(value)
        return self

    def ha(self, value):
        self.set_halign(align[value])
        return self

    def va(self, value):
        self.set_valign(align[value])
        return self

    def he(self, value=True):
        self.set_hexpand(value)
        return self

    def ve(self, value=True):
        self.set_vexpand(value)
        return self

    def css(self, css_class):
        self.add_css_class(css_class)
        return self


class Sep(Gtk.Separator):
    def __init__(self, orientation_string):
        super().__init__()
        self.set_orientation(orientation[orientation_string])


def module():
    module = Gtk.MenuButton.new()
    module.set_direction(Gtk.ArrowType.NONE)
    module.set_label('Test')

    widget = Gtk.Popover.new()
    widget.add_css_class('widget-outer')
    widget.set_position(Gtk.PositionType.TOP)

    outer = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    header = Gtk.Label.new('Calendar')
    header.add_css_class('widget-header')
    outer.append(header)
    inner = Gtk.Box.new(Gtk.Orientation.VERTICAL, 20)
    inner.add_css_class('widget-inner')

    calendar = Gtk.Calendar.new()
    inner.append(calendar)

    section_box = Box('v').spacing(10)
    section_box.append(Label('Events').he().ha('start'))
    container = Box('v').css('split-container')
    nums = range(1, 5)
    for num in nums:
        container.append(
            Label(f"Event {num}").css('split-box').he().ha('start'))
        if num != nums[-1]:
            container.append(Sep('v'))
    section_box.append(container)

    inner.append(section_box)

    outer.append(inner)
    widget.set_child(outer)

    module.set_popover(widget)

    return module
