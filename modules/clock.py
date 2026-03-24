#!/usr/bin/python3 -u
"""
Description: Clock widget using Gtk.Calendar
Author: thnikk
"""
import weakref
import subprocess
import json
import os
import common as c
from datetime import datetime, date
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


# Path for per-source event cache
_EVENTS_CACHE_PATH = os.path.expanduser(
    '~/.cache/pybar/clock_events.json'
)


def _load_events_cache():
    """Load the per-source event cache from disk."""
    try:
        if os.path.exists(_EVENTS_CACHE_PATH):
            with open(_EVENTS_CACHE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        c.print_debug(
            f"Failed to load event cache: {e}", color='red'
        )
    return {}


def _save_events_cache(cache):
    """Persist the per-source event cache to disk."""
    try:
        os.makedirs(
            os.path.dirname(_EVENTS_CACHE_PATH), exist_ok=True
        )
        with open(_EVENTS_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
    except Exception as e:
        c.print_debug(
            f"Failed to save event cache: {e}", color='red'
        )


def _resolve_password(source):
    """
    Return plaintext password for a source dict.
    Uses password_command if present, else password field.
    Returns None if neither is set or command fails.
    """
    cmd = source.get('password_command', '').strip()
    if cmd:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True,
                text=True, timeout=10
            )
            if result.returncode != 0:
                c.print_debug(
                    f"password_command exited {result.returncode}: "
                    f"{result.stderr.strip()}",
                    color='red'
                )
                return None
            return result.stdout.strip()
        except Exception as e:
            c.print_debug(
                f"password_command error: {e}", color='red'
            )
            return None
    return source.get('password') or None


def _date_range():
    """
    Return (start, end) as date objects covering today through
    Dec 31 of the current year.
    """
    today = date.today()
    end = date(today.year, 12, 31)
    return today, end


def _normalise_events(raw):
    """
    Convert a raw {MM/DD: desc} dict (from JSON source) or a
    {YYYY-MM-DD: desc} dict (from remote sources) into the
    canonical {MM/DD: desc} format used by the UI.
    Annual recurring events from remote sources are kept as MM/DD.
    """
    out = {}
    for key, desc in raw.items():
        parts = key.split('-')
        if len(parts) == 3:
            # Full date — store as MM/DD for current-year display
            out[f"{parts[1]}/{parts[2]}"] = desc
        else:
            # Already MM/DD
            out[key] = desc
    return out


def _load_json_events():
    """
    Load events from ~/.config/calendar-events.json.
    Returns {MM/DD: description} or {} on failure.
    """
    try:
        path = os.path.expanduser(
            '~/.config/calendar-events.json'
        )
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        c.print_debug(
            f"Failed to load calendar-events.json: {e}",
            color='red'
        )
    return {}


def _ical_summary(component):
    """Return the SUMMARY string from an icalendar component."""
    summary = component.get('SUMMARY')
    if summary is None:
        return ''
    return str(summary)


def _load_ics_events(url):
    """
    Fetch and parse an ICS URL.
    Returns {MM/DD: description} for events in the current year,
    including RRULE:FREQ=YEARLY annual events.
    """
    try:
        import requests
        import icalendar
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        cal = icalendar.Calendar.from_ical(resp.content)
        today, end = _date_range()
        events = {}
        for component in cal.walk():
            if component.name != 'VEVENT':
                continue
            summary = _ical_summary(component)
            dtstart = component.get('DTSTART')
            if not dtstart:
                continue
            event_date = dtstart.dt
            # Handle date-only and datetime values
            if hasattr(event_date, 'date'):
                event_date = event_date.date()
            rrule = component.get('RRULE')
            is_annual = (
                rrule and
                rrule.get('FREQ', [None])[0] == 'YEARLY'
            )
            if is_annual:
                # Store as MM/DD so it appears every year
                key = event_date.strftime('%m/%d')
                events[key] = summary
            elif today <= event_date <= end:
                key = event_date.strftime('%m/%d')
                events[key] = summary
        return events
    except Exception as e:
        c.print_debug(
            f"ICS fetch failed ({url}): {e}", color='red'
        )
        return None  # None signals failure; {} means empty success


def _load_caldav_events(url, username, password):
    """
    Fetch events from a CalDAV server.
    Returns {MM/DD: description} for events in the current year,
    including RRULE:FREQ=YEARLY annual events. Returns None on error.
    """
    try:
        import caldav
        import icalendar
        client = caldav.DAVClient(
            url=url, username=username, password=password
        )
        principal = client.principal()
        calendars = principal.calendars()
        today, end = _date_range()
        events = {}
        for calendar in calendars:
            try:
                results = calendar.date_search(
                    start=today, end=end, expand=True
                )
                for event in results:
                    try:
                        cal = icalendar.Calendar.from_ical(
                            event.data
                        )
                        for component in cal.walk():
                            if component.name != 'VEVENT':
                                continue
                            summary = _ical_summary(component)
                            dtstart = component.get('DTSTART')
                            if not dtstart:
                                continue
                            event_date = dtstart.dt
                            if hasattr(event_date, 'date'):
                                event_date = event_date.date()
                            rrule = component.get('RRULE')
                            is_annual = (
                                rrule and
                                rrule.get('FREQ', [None])[0]
                                == 'YEARLY'
                            )
                            if is_annual:
                                key = event_date.strftime('%m/%d')
                                events[key] = summary
                            elif today <= event_date <= end:
                                key = event_date.strftime('%m/%d')
                                events[key] = summary
                    except Exception as e:
                        c.print_debug(
                            f"CalDAV event parse error: {e}",
                            color='yellow'
                        )
            except Exception as e:
                c.print_debug(
                    f"CalDAV calendar search error: {e}",
                    color='yellow'
                )
        return events
    except Exception as e:
        c.print_debug(
            f"CalDAV connect failed ({url}): {e}", color='red'
        )
        return None  # None signals failure; {} means empty success


def _load_credentials(config_path):
    """Load credentials file, return {} on any failure."""
    if not config_path:
        return {}
    try:
        import credentials as creds_mod
        return creds_mod.load(config_path)
    except Exception as e:
        c.print_debug(
            f"Failed to load credentials: {e}", color='red'
        )
    return {}


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
        """Get current time."""
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
        """
        Aggregate events from all configured sources.
        Falls back to cached events per source on failure.
        If no sources are configured, reads the legacy JSON file.
        """
        sources = self.config.get('sources') if self.config else None
        if not sources:
            # Legacy behaviour — JSON file only
            return _load_json_events()

        cache = _load_events_cache()
        merged = {}
        # Read config path from state manager (set by main.py)
        config_path = c.state_manager.get('config_path')
        credentials = _load_credentials(config_path)
        caldav_creds = credentials.get('caldav', [])

        for source in sources:
            stype = source.get('type', '')

            if stype == 'json':
                key = 'json'
                result = _load_json_events()
                # JSON never fails, so always update cache
                cache[key] = result
                merged.update(result)

            elif stype == 'ics_url':
                url = source.get('url', '').strip()
                if not url:
                    continue
                key = f"ics_url:{url}"
                result = _load_ics_events(url)
                if result is None:
                    # Use cached events on failure
                    cached = cache.get(key, {})
                    if cached:
                        c.print_debug(
                            f"ICS failed, using cache for {url}",
                            color='yellow'
                        )
                        merged.update(cached)
                else:
                    cache[key] = result
                    merged.update(result)

            elif stype == 'caldav':
                url = source.get('url', '').strip()
                username = source.get('username', '').strip()
                if not url or not username:
                    continue
                key = f"caldav:{url}:{username}"
                # Find matching credentials entry
                password = None
                for entry in caldav_creds:
                    if (entry.get('url', '').strip() == url and
                            entry.get('username', '').strip()
                            == username):
                        password = _resolve_password(entry)
                        break
                if not password:
                    c.print_debug(
                        f"No credentials found for CalDAV "
                        f"{username}@{url}",
                        color='yellow'
                    )
                    # Still try cached events
                    cached = cache.get(key, {})
                    merged.update(cached)
                    continue
                result = _load_caldav_events(url, username, password)
                if result is None:
                    cached = cache.get(key, {})
                    if cached:
                        c.print_debug(
                            f"CalDAV failed, using cache for "
                            f"{username}@{url}",
                            color='yellow'
                        )
                        merged.update(cached)
                else:
                    cache[key] = result
                    merged.update(result)

        _save_events_cache(cache)
        return merged

    def event_lookup(self, event):
        """Get style for event."""
        event_types = {
            "birthday": "blue",
            "appointment": "orange",
        }
        for event_type, style in event_types.items():
            if event_type in event.lower():
                return style
        return "green"

    def refresh_events(self, calendar_widget, event_box):
        """Update marks and event list based on displayed month."""
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

            # Map event colour names to RGB tuples
            color_map = {
                'blue':   (0x8f, 0xa1, 0xbe),
                'orange': (0xd0, 0x87, 0x70),
                'green':  (0xa3, 0xbe, 0x8c),
            }

            # Size group keeps all left-side cells equal width
            left_size_group = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL
            )

            def get_ordinal(n):
                if 11 <= n <= 13:
                    return 'th'
                return {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')

            for i, (day, event) in enumerate(month_events):
                row = c.box('h')
                color_style = self.event_lookup(event)
                r, g, b = color_map.get(
                    color_style, color_map['green']
                )

                # Left cell: indicator bar + date label
                left_cell = c.box('h')
                left_size_group.add_widget(left_cell)

                # Coloured vertical bar indicator
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
                    provider,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                left_cell.append(indicator)

                date_label = c.label(
                    f"{day}{get_ordinal(day)}", style='inner-box'
                )
                left_cell.append(date_label)

                row.append(left_cell)
                row.append(c.sep('v'))

                desc_label = c.label(
                    event, style='inner-box', ha='end'
                )
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
            path = os.path.expanduser(
                '~/.config/calendar-events.json'
            )
            if not os.path.exists(path):
                alert = c.box('v', style='box')
                alert.append(c.label(
                    'Set up events in '
                    '~/.config/calendar-events.json',
                    style='inner-box', wrap=20
                ))
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
                        is_today = 'today' in classes

                        for cls in [
                            'blue', 'orange', 'green',
                            'blue-fg', 'orange-fg', 'green-fg',
                            'calendar-event'
                        ]:
                            if cls in classes:
                                child.remove_css_class(cls)

                        if is_today:
                            child.add_css_class('today')

                        if 'other-month' not in classes:
                            try:
                                day_val = int(child.get_text())
                                if day_val in event_map:
                                    style = self.event_lookup(
                                        event_map[day_val][0]
                                    )
                                    child.add_css_class(
                                        'calendar-event'
                                    )
                                    child.add_css_class(
                                        f"{style}-fg"
                                    )
                                    child.set_tooltip_text(
                                        "\n".join(
                                            event_map[day_val]
                                        )
                                    )
                                else:
                                    child.set_tooltip_text(None)
                            except ValueError:
                                pass
                child = child.get_next_sibling()

    def widget_content(self):
        """Create calendar widget popover content."""
        widget = c.box('v', style='widget', spacing=10)
        widget.set_size_request(300, -1)

        heading = c.label(
            "Calendar", style="heading", he=True, ha="fill"
        )
        heading.set_xalign(0.5)
        widget.append(heading)

        cal = Gtk.Calendar()
        cal.add_css_class('view')
        cal.set_size_request(-1, 230)
        widget.append(cal)

        widget.append(
            c.label("Events", style="title", he=True, ha="start")
        )

        event_scroll = c.scroll(height=200, style='scroll')
        event_list_box = c.box('v', spacing=10)
        event_scroll.set_child(event_list_box)
        widget.append(event_scroll)

        self.refresh_events(cal, event_list_box)

        cal.connect('notify::month', lambda *_: self.refresh_events(
            cal, event_list_box
        ))
        cal.connect('notify::year', lambda *_: self.refresh_events(
            cal, event_list_box
        ))

        return widget

    def create_widget(self, bar):
        """Clock module widget."""
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')
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
        """Update clock UI."""
        if widget.text is None:
            return

        last = widget.text.get_text()
        new = data['text']
        widget.set_visible(True)
        if new != last:
            widget.set_label(new)

        # Refresh calendar widget on day change
        current_day = data.get('day')
        last_day = getattr(widget, 'last_day', None)

        if current_day != last_day:
            widget.set_widget(self.widget_content())
            widget.last_day = current_day


module_map = {
    'clock': Clock
}
