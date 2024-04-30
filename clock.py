#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from datetime import datetime
import calendar
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import common as c


def widget():
    """ Clock widget """
    pop = Gtk.Popover()
    widget = c.box('v', spacing=20)
    widget.add(c.label('Calendar', style='heading'))

    now = datetime.now()
    cal_box = c.box('v', spacing=5)
    dow_box = c.box('h', spacing=5)
    for dow in ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']:
        dow_label = c.label(dow, style='day')
        dow_box.add(dow_label)
        dow_label.get_style_context().add_class('dow')
    cal_box.add(dow_box)
    cal = calendar.Calendar(6)
    for week in cal.monthdayscalendar(now.year, now.month):
        week_box = c.box('h', spacing=5)
        for day in week:
            if day == 0:
                day = ' '
            day_label = c.label(day, style='day')
            if day == now.day:
                day_label.get_style_context().add_class('today')
            week_box.add(day_label)
        cal_box.add(week_box)

    widget.add(cal_box)
    widget.show_all()
    pop.add(widget)
    return pop


def module():
    """ Clock module """
    label = Gtk.MenuButton(popover=widget())
    label.get_style_context().add_class('module')

    def get_time():
        label.set_label(datetime.now().strftime(' %I:%M:%S'))
        return True

    if get_time():
        GLib.timeout_add(1000, get_time)
        return label
