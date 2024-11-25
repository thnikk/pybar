#!/usr/bin/python3 -u
import common as c
from datetime import datetime
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib # noqa


def gen_ev_box(calendar, events):
    outer = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
    outer.set_min_content_height(100)
    box = c.box('v')
    box.set_vexpand(True)
    box.add_css_class('split-container')
    calendar.clear_marks()
    if events:
        for day, event in events.items():
            calendar.mark_day(int(day))
            event_box = c.box('h', style='split-box')
            event_box.set_vexpand(True)
            day_text = day
            if day[-1] == '1':
                day_text = day_text + 'st'
            elif day[-1] == '2':
                day_text = day_text + 'nd'
            elif day[-1] == '3':
                day_text = day_text + 'rd'
            else:
                day_text = day_text + 'th'
            event_box.append(c.label(f"{day_text} - {event}"))
            box.append(event_box)
            if day != list(events)[-1]:
                box.append(c.sep('v'))
    else:
        box.append(c.label(
            'No events', he=True, ha='center',
            ve=True, va='center', style='split-box'))
    outer.set_child(box)
    return outer


def module():
    module = c.Module()
    module.icon.set_label('')

    module.set_widget('Calendar')
    calendar = Gtk.Calendar.new()
    module.widget_content.append(calendar)

    label_box = c.box('v', spacing=10)
    label = c.label('Events', he=True, ha='start')
    label_box.append(label)

    events = {
        "9": {
            "18": "Nick's birthday"
        },
        "10": {
            "2": "Nicole's birthday", "22": "My birthday"
        },
        "11": {
            "6": "Dilly's birthday", "7": "Test event 1", "8": "Test event 2",
            "9": "Test event 3", "10": "Test event 4"
        }
    }

    module.widget_content.append(label_box)
    module.events_box = gen_ev_box(
        calendar, events[str(calendar.get_date().get_month())])
    module.widget_content.append(module.events_box)

    def changed(calendar, module, events_box):
        module.widget_content.remove(module.events_box)
        month = str(calendar.get_date().get_month())
        try:
            module.events_box = gen_ev_box(calendar, events[month])
            module.widget_content.append(module.events_box)
        except KeyError:
            module.events_box = gen_ev_box(calendar, {})
            module.widget_content.append(module.events_box)

    for sig in ['next-month', 'prev-month', 'next-year', 'prev-year']:
        calendar.connect(sig, changed, module, module.events_box)

    def update():
        module.text.set_label(datetime.now().strftime("%I:%M %m/%d"))
        return True

    if update():
        GLib.timeout_add(1000, update)
        return module
