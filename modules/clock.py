#!/usr/bin/python3 -u
"""
Description: Clock widget using Gtk.Calendar
Author: thnikk
"""
import weakref
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

            # Map event color names to RGB tuples
            color_map = {
                'blue':   (0x8f, 0xa1, 0xbe),
                'orange': (0xd0, 0x87, 0x70),
                'green':  (0xa3, 0xbe, 0x8c),
            }

            # Size group keeps all left-side (indicator + date) cells equal
            left_size_group = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL)

            def get_ordinal(n):
                if 11 <= n <= 13:
                    return 'th'
                return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

            for i, (day, event) in enumerate(month_events):
                row = c.box('h')
                color_style = self.event_lookup(event)
                r, g, b = color_map.get(color_style, color_map['green'])

                # Left cell: indicator bar + date label, width equalised
                left_cell = c.box('h')
                left_size_group.add_widget(left_cell)

                # Colored vertical bar indicator (same style as disks/cpu)
                indicator = Gtk.Box()
                indicator.set_size_request(6, 16)
                indicator.set_valign(Gtk.Align.CENTER)
                indicator.set_margin_start(10)
                indicator.set_margin_end(4)
                css = (
                    f"box {{ background-color: rgb({r}, {g}, {b}); "
                    f"border-radius: 999px; }}"
                )
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                indicator.get_style_context().add_provider(
                    provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                left_cell.append(indicator)

                # Date label (day number + ordinal suffix)
                date_label = c.label(
                    f"{day}{get_ordinal(day)}", style='inner-box')
                left_cell.append(date_label)

                row.append(left_cell)
                row.append(c.sep('v'))

                # Event description - truncates with ellipsis
                desc_label = c.label(event, style='inner-box', ha='end')
                desc_label.set_hexpand(True)
                desc_label.set_halign(Gtk.Align.END)
                desc_label.set_ellipsize(c.Pango.EllipsizeMode.END)
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
                        # Check if this is today before clearing classes
                        is_today = 'today' in classes

                        for cls in [
                                'blue', 'orange', 'green', 'blue-fg',
                                'orange-fg', 'green-fg', 'calendar-event']:
                            if cls in classes:
                                child.remove_css_class(cls)

                        # Re-apply today class if it was present
                        if is_today:
                            child.add_css_class('today')

                        if 'other-month' not in classes:
                            try:
                                day_val = int(child.get_text())
                                if day_val in event_map:
                                    style = self.event_lookup(
                                        event_map[day_val][0])
                                    child.add_css_class('calendar-event')
                                    child.add_css_class(f"{style}-fg")
                                    child.set_tooltip_text(
                                        "\n".join(event_map[day_val]))
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

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
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
