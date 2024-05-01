#!/usr/bin/python3 -u
"""
Description: Calendar widget for clock module
Author: thnikk
"""
import json
from datetime import datetime
import calendar
import os
import common as c


def diff_month(year, month, diff):
    """ Find year and month difference """
    if diff < 0 and month == 1:
        month = 12 - (diff + 1)
        year = year - 1
    elif diff > 0 and month == 12:
        month = 1 + (diff - 1)
        year = year + 1
    else:
        month = month + diff
    return year, month


def cal_list(year, month, style=None):
    """ Get calendar list for month and append style to boxes """
    cal = calendar.Calendar(6)
    return [
        [
            [day, [style]] for day in month
            if day
        ]
        for month in
        cal.monthdayscalendar(year, month)
    ]


def event_lookup(event):
    """ Get style for event """
    event_types = {
        "birthday": "blue-fg",
        "appointment": "orange-fg",
    }

    for event_type, style in event_types.items():
        if event_type in event.lower():
            return style
    return "green-fg"


def calendar_widget():
    """ Draw calendar """
    widget = c.box('v', style='widget', spacing=20)

    now = datetime.now()

    month_label = c.label(now.strftime('%B'), style='heading')
    widget.add(month_label)

    cal_section = c.box('v')

    # Create calendar box
    row = c.box('h', spacing=10)
    for dow in ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]:
        dow_label = c.label(dow, style='day')
        c.add_style(dow_label, 'dow')
        row.add(dow_label)
    cal_box = c.box('v')
    cal_box.add(row)

    last_month = cal_list(*diff_month(now.year, now.month, -1), 'old')[-2:]
    current_month = cal_list(now.year, now.month)
    next_month = cal_list(*diff_month(now.year, now.month, 1), 'old')[:2]

    try:
        with open(
            os.path.expanduser('~/.config/calendar-events.json'),
            'r', encoding='utf-8'
        ) as file:
            events = json.loads(file.read())
    except FileNotFoundError:
        events = {}
        alert = c.box('v', style='events-box')
        alert.add(c.label(
            'Set up events in ~/.config/calendar-events.json',
            style='event-box', wrap=20))

    style_events(last_month, current_month, next_month, events, now)

    cal_box.add(draw_calendar(last_month, current_month, next_month))
    cal_section.add(cal_box)
    widget.add(cal_section)

    widget.add(draw_events(now, events))

    try:
        widget.add(alert)
    except UnboundLocalError:
        pass

    return widget


def style_events(last_month, current_month, next_month, events, now):
    """ Add style to events """
    for count, month in enumerate([last_month, current_month, next_month]):
        for week in month:
            for day, styles in week:
                if count == 1 and day == now.day:
                    styles.append('today')
                date = (
                    f"{diff_month(now.year, now.month, count - 1)[1]}"
                    f"/{day}"
                )
                if date in list(events):
                    event_style = event_lookup(events[date])
                    styles.append('event')
                    styles.append(event_style)


def draw_calendar(last_month, current_month, next_month):
    """ Draw calendar"""
    combined_month = []
    if len(last_month[-1]) < 7:
        combined_month += last_month[:-1]
        combined_month += [last_month[-1] + current_month[0]]
        combined_month += current_month[1:]
    else:
        combined_month = last_month + current_month
    if len(next_month[0]) < 7:
        mixed_month = [combined_month[-1] + next_month[0]]
        del combined_month[-1]
        combined_month += mixed_month + next_month[1:]
    lines = c.box('v')
    for week in combined_month:
        line = c.box('h', spacing=10)
        for day, styles in week:
            day_label = c.label(day)
            for style in styles:
                if style:
                    day_label.get_style_context().add_class(style)
            day_label.get_style_context().add_class('day')
            line.add(day_label)
        lines.add(line)
    return lines


def draw_events(now, events):
    """ Draw events """
    events_section = c.box('v', spacing=20)
    for offset, month in enumerate(['Last', 'This', 'Next']):
        month_events = {
            date: event for date, event in events.items()
            if date.split('/', maxsplit=1)[0] == str(
                diff_month(now.year, now.month, offset-1)[1])
        }

        if month_events:
            event_section = c.box('v', spacing=10)
            event_line = c.box('h')
            event_line.add(c.label(f'{month} month'))
            event_section.add(event_line)

            events_box = c.box('v', style='events-box')
            for date, event in month_events.items():
                event_box = c.box('h', style='event-box', spacing=10)
                event_dot = c.label('', style='event-dot')
                event_style = event_lookup(event)
                event_dot.get_style_context().add_class(event_style)
                event_box.pack_start(event_dot, False, True, 0)
                event_box.pack_start(
                    c.label(date, style='event-day'), False, True, 0)
                event_box.pack_start(
                    c.label(event, wrap=20), False, True, 0)
                events_box.add(event_box)

                if date != list(month_events)[-1]:
                    events_box.add(c.sep('h'))
            event_section.add(events_box)
            events_section.add(event_section)
    return events_section
