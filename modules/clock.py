#!/usr/bin/python3 -u
"""
Description: Clock widget using Gtk.Calendar
Author: thnikk
"""
import common as c
from datetime import datetime
import os
import json
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


class Clock(c.BaseModule):
    DEFAULT_INTERVAL = 1

    SCHEMA = {
        'format': {
            'type': 'string',
            'default': '%I:%M %m/%d',
            'label': 'Time Format',
            'description': 'strftime format string for the clock display'
        },
        'interval': {
            'type': 'integer',
            'default': 1,
            'label': 'Update Interval',
            'description': 'Seconds between updates',
            'min': 1,
            'max': 60
        }
    }

    def fetch_data(self):
        """ Get current time """
        now = datetime.now()
        try:
            datestring = self.config.get('format', '%I:%M %m/%d')
        except (TypeError, KeyError):
            datestring = '%I:%M %m/%d'

        return {
            "text": now.strftime(datestring),
            "day": now.day,
            "month": now.month,
            "year": now.year,
        }

    def load_events(self):
        """ Load events from config file """
        try:
            path = os.path.expanduser('~/.config/calendar-events.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            c.print_debug(f"Failed to load calendar events: {e}", color='red')
        return {}

    def event_lookup(self, event):
        """ Get style for event """
        event_types = {
            "birthday": "blue",
            "appointment": "orange",
        }
        for event_type, style in event_types.items():
            if event_type in event.lower():
                return style
        return "green"

    def refresh_events(self, calendar_widget, event_box):
        """ Update marks and event list based on displayed month """
        month = calendar_widget.get_month() + 1
        calendar_widget.clear_marks()

        # Clear event box
        child = event_box.get_first_child()
        while child:
            event_box.remove(child)
            child = event_box.get_first_child()

        events = self.load_events()
        month_events = []
        event_map = {}  # day -> [descriptions]

        if events:
            for date_str, event_desc in events.items():
                try:
                    m, d = map(int, date_str.split('/'))
                    if m == month:
                        calendar_widget.mark_day(d)
                        month_events.append((d, event_desc))
                        if d not in event_map:
                            event_map[d] = []
                        event_map[d].append(event_desc)
                except (ValueError, IndexError):
                    continue

        if month_events:
            month_events.sort()
            events_container = c.box('v', style='box')
            events_container.set_overflow(Gtk.Overflow.HIDDEN)
            
            # Horizontal size group for date blocks
            # Attach to container to prevent garbage collection
            events_container.size_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
            
            def get_ordinal(n):
                if 11 <= n <= 13:
                    return 'th'
                return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

            for i, (day, event) in enumerate(month_events):
                row = c.box('h')
                color_style = self.event_lookup(event)
                
                # Date Block - Fixed width based on SizeGroup
                date_box = c.box('h', style=color_style)
                date_box.get_style_context().add_class('event-date-box')
                date_box.set_valign(Gtk.Align.FILL)
                date_box.set_hexpand(False)
                events_container.size_group.add_widget(date_box)
                
                # Internal centering for date/ordinal
                date_content = c.box('h')
                date_content.set_halign(Gtk.Align.CENTER)
                date_content.set_hexpand(True)
                date_content.append(c.label(day, style='event-day-number'))
                date_content.append(c.label(get_ordinal(day), style='event-day-ordinal', va='start'))
                date_box.append(date_content)
                
                row.append(date_box)
                row.append(c.sep('v'))

                # Event description - Takes up all remaining space
                desc_label = c.label(event, style='inner-box', wrap=25, ha='start')
                desc_label.set_hexpand(True)
                desc_label.set_halign(Gtk.Align.START)
                row.append(desc_label)
                
                events_container.append(row)
                if i < len(month_events) - 1:
                    events_container.append(c.sep('h'))
            event_box.append(events_container)
        else:
            event_box.append(c.label('No events', style='gray'))
            path = os.path.expanduser('~/.config/calendar-events.json')
            if not os.path.exists(path):
                alert = c.box('v', style='box')
                alert.append(c.label(
                    'Set up events in ~/.config/calendar-events.json',
                    style='inner-box', wrap=20))
                event_box.append(alert)

        # Style internal calendar labels for better visibility
        grid = None
        child = calendar_widget.get_first_child()
        while child:
            if isinstance(child, Gtk.Grid):
                grid = child
                break
            child = child.get_next_sibling()

        if grid:
            child = grid.get_first_child()
            while child:
                if isinstance(child, Gtk.Label):
                    classes = child.get_css_classes()
                    if 'day-number' in classes:
                        for cls in ['blue', 'orange', 'green', 'blue-fg', 'orange-fg', 'green-fg', 'calendar-event']:
                            if cls in classes:
                                child.remove_css_class(cls)
                        
                        if 'other-month' not in classes:
                            try:
                                day_val = int(child.get_text())
                                if day_val in event_map:
                                    style = self.event_lookup(event_map[day_val][0])
                                    child.add_css_class('calendar-event')
                                    child.add_css_class(f"{style}-fg")
                                    child.set_tooltip_text("\n".join(event_map[day_val]))
                                else:
                                    child.set_tooltip_text(None)
                            except ValueError:
                                pass
                child = child.get_next_sibling()

    def widget_content(self):
        """ Create calendar widget popover content """
        widget = c.box('v', style='widget', spacing=10)
        widget.set_size_request(300, -1)

        heading = c.label(
            "Calendar", style="heading", he=True, ha="fill")
        heading.set_xalign(0.5)
        widget.append(heading)

        cal = Gtk.Calendar()
        cal.add_css_class('view')
        cal.set_size_request(-1, 230)
        widget.append(cal)

        # Add "Events" title
        widget.append(c.label("Events", style="title", he=True, ha="start"))

        # Scrollable event list
        event_scroll = c.scroll(height=200, style='scroll')
        event_list_box = c.box('v', spacing=10)
        event_scroll.set_child(event_list_box)
        widget.append(event_scroll)

        # Initial refresh
        self.refresh_events(cal, event_list_box)

        # Connect signals for navigation
        cal.connect('notify::month', lambda *_: self.refresh_events(
            cal, event_list_box))
        cal.connect('notify::year', lambda *_: self.refresh_events(
            cal, event_list_box))

        return widget

    def create_widget(self, bar):
        """ Clock module widget """
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')
        m.set_widget(self.widget_content())

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Update clock UI """
        if widget.text is None:
            return

        last = widget.text.get_text()
        new = data['text']
        widget.set_visible(True)
        if new != last:
            widget.set_label(new)

        # Check if we need to refresh calendar on new day
        current_day = data.get('day')
        last_day = getattr(widget, 'last_day', None)

        if current_day != last_day:
            widget.set_widget(self.widget_content())
            widget.last_day = current_day


module_map = {
    'clock': Clock
}
