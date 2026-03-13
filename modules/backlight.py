#!/usr/bin/python3 -u
"""
Description: Brightness module — sysfs backlight and DDC monitors
Author: thnikk
"""
import os
import subprocess
import threading
import weakref
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib  # noqa


class Backlight(c.BaseModule):
    SCHEMA = {
        'device': {
            'type': 'string',
            'default': '',
            'label': 'Backlight Device',
            'description': (
                'sysfs device name (e.g. intel_backlight). '
                'Leave empty for auto-detect.'
            )
        },
        'interval': {
            'type': 'integer',
            'default': 5,
            'label': 'Update Interval',
            'description': 'Seconds between brightness polls',
            'min': 1,
            'max': 300
        },
        'step': {
            'type': 'integer',
            'default': 5,
            'label': 'DDC Scroll Step',
            'description': (
                'Brightness step (% of max) used when scrolling '
                'a DDC monitor'
            ),
            'min': 1,
            'max': 20
        }
    }

    # FA solid sun (f185)
    ICON = '\uf185'

    # ------------------------------------------------------------------
    # sysfs helpers
    # ------------------------------------------------------------------

    def _sysfs_path(self):
        """Resolve the sysfs backlight device path."""
        base = '/sys/class/backlight'
        device = self.config.get('device', '')
        if device:
            p = os.path.join(base, device)
            if os.path.exists(p):
                return p
        for name in ('intel_backlight', 'acpi_video0'):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
        if os.path.exists(base):
            try:
                entries = os.listdir(base)
                if entries:
                    return os.path.join(base, entries[0])
            except OSError:
                pass
        return None

    def _read_sysfs(self):
        """Return a sysfs source dict, or None if unavailable."""
        path = self._sysfs_path()
        if not path:
            return None
        try:
            def _read(name):
                with open(
                    os.path.join(path, name), 'r', encoding='utf-8'
                ) as fh:
                    return int(fh.read().strip())
            brightness = _read('brightness')
            maximum = _read('max_brightness')
            return {
                'kind': 'sysfs',
                'key': path,
                'name': 'Backlight',
                'brightness': brightness,
                'max_brightness': maximum,
                'path': path,
            }
        except Exception as e:
            c.print_debug(f"sysfs read error: {e}", color='red')
            return None

    def _set_sysfs(self, path, value):
        """Write brightness to sysfs (blocking, call from a thread)."""
        try:
            with open(
                os.path.join(path, 'brightness'), 'w', encoding='utf-8'
            ) as fh:
                fh.write(str(round(value)))
        except PermissionError:
            c.print_debug(
                'Permission denied writing sysfs brightness', color='red'
            )

    # ------------------------------------------------------------------
    # DDC helpers
    # ------------------------------------------------------------------

    def _ddcutil(self, args):
        """Run ddcutil with args; return stdout or None on error."""
        try:
            r = subprocess.run(
                ['ddcutil'] + args,
                capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return r.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            c.print_debug(f"ddcutil error: {e}", color='red')
        return None

    def _read_ddc(self):
        """Return a list of DDC source dicts for all detected monitors."""
        out = self._ddcutil(['detect'])
        if not out:
            return []
        monitors = []
        bus = None
        connector = None
        name = None
        for line in out.splitlines():
            line = line.strip()
            # New display block — flush previous entry first
            if line.startswith('Display '):
                if bus is not None:
                    monitors.append((bus, name or 'Monitor', connector))
                bus = None
                connector = None
                name = None
            elif line.startswith('I2C bus:'):
                try:
                    bus = int(line.split('/dev/i2c-')[-1])
                except ValueError:
                    bus = None
            elif line.startswith('DRM_connector:') and bus is not None:
                # Format: "DRM_connector: cardN-OUTPUT" → strip "cardN-"
                raw = line.split('DRM_connector:', 1)[-1].strip()
                connector = raw.split('-', 1)[-1] if '-' in raw else raw
            elif line.startswith('Model:') and bus is not None:
                # Verbose output: model under "EDID synopsis:"
                name = line.split('Model:', 1)[-1].strip()
        # Flush last entry
        if bus is not None:
            monitors.append((bus, name or 'Monitor', connector))
        sources = []
        for bus, name, connector in monitors:
            out = self._ddcutil(
                ['getvcp', '10', '--bus', str(bus), '--brief']
            )
            if not out:
                continue
            # Brief format: "VCP 10 C <current> <max>"
            parts = out.strip().split()
            try:
                current, maximum = int(parts[3]), int(parts[4])
            except (IndexError, ValueError):
                continue
            sources.append({
                'kind': 'ddc',
                'key': str(bus),
                'name': name,
                'brightness': current,
                'max_brightness': maximum,
                'bus': bus,
                'connector': connector,
            })
        return sources

    def _set_ddc(self, bus, value):
        """Set DDC brightness (blocking, call from a thread)."""
        self._ddcutil(
            ['setvcp', '10', str(round(value)), '--bus', str(bus)]
        )

    # ------------------------------------------------------------------
    # Data fetching
    # ------------------------------------------------------------------

    def fetch_data(self):
        """Collect brightness from sysfs and all DDC monitors."""
        sources = []
        sysfs = self._read_sysfs()
        if sysfs:
            sources.append(sysfs)
        sources.extend(self._read_ddc())
        return {'sources': sources} if sources else {}

    # ------------------------------------------------------------------
    # Writing brightness — debounced via GLib from the UI thread
    # ------------------------------------------------------------------

    def _apply_brightness(self, source, value):
        """Dispatch the appropriate write in a daemon thread."""
        if source['kind'] == 'sysfs':
            threading.Thread(
                target=self._set_sysfs,
                args=(source['path'], value),
                daemon=True
            ).start()
        else:
            threading.Thread(
                target=self._set_ddc,
                args=(source['bus'], value),
                daemon=True
            ).start()

    def _make_slider_handler(self, widget, source, pct_label=None):
        """Return a value-changed callback with per-source debounce."""
        key = source['key']
        max_b = source['max_brightness']
        connector = getattr(widget, '_connector', None)

        def on_value_changed(slider):
            # Cancel any pending write for this source
            handle = widget._debounce.get(key)
            if handle is not None:
                GLib.source_remove(handle)

            value = slider.get_value()
            pct = round((value / max_b) * 100)

            # Update the inline percentage label in the popover row
            if pct_label is not None:
                pct_label.set_text(f'{pct}%')

            # Update the bar module label if this source matches the bar
            matched = self._find_source_for_connector(
                [source], connector
            )
            if matched or len(
                getattr(widget, 'source_rows', {})
            ) == 1:
                pending = getattr(widget, '_scroll_pending', {})
                if key not in pending:
                    widget.set_label(f'{pct}%')

            def do_apply():
                widget._debounce.pop(key, None)
                self._apply_brightness(source, value)
                import module as _module
                _module.force_update(self.name)
                return GLib.SOURCE_REMOVE

            widget._debounce[key] = GLib.timeout_add(300, do_apply)

        return on_value_changed

    # ------------------------------------------------------------------
    # Popover construction and incremental sync
    # ------------------------------------------------------------------

    def _make_row(self, widget, source):
        """Build a (row_box, slider, handler_id) tuple for one source."""
        row_box = c.box('v', spacing=8)
        row_box.append(c.label(source['name'], style='title', ha='start'))

        outer = c.box('h', style='box', spacing=10)
        c.add_style(outer, 'inner-box-min')
        outer.set_hexpand(True)
        outer.append(c.label(self.ICON))

        sl = c.slider(
            source['brightness'], 0, source['max_brightness']
        )
        sl.set_hexpand(True)

        # Percentage label to the right of the slider
        pct = round(
            (source['brightness'] / source['max_brightness']) * 100
        )
        pct_label = c.label(f'{pct}%')
        pct_label.set_width_chars(4)
        pct_label.set_xalign(1.0)

        # Connect and store the signal handler ID for block/unblock
        hid = sl.connect(
            'value-changed',
            self._make_slider_handler(widget, source, pct_label)
        )
        outer.append(sl)
        outer.append(pct_label)
        row_box.append(outer)
        return row_box, sl, hid

    def build_popover(self, widget, sources):
        """Create the popover content; call only once per widget."""
        widget._debounce = {}
        widget.source_rows = {}

        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Brightness', style='heading'))

        sources_box = c.box('v', spacing=16)
        widget.sources_box = sources_box

        for source in sources:
            row_box, sl, hid = self._make_row(widget, source)
            # Store pct_label via slider's next sibling (appended after sl)
            pct_label = sl.get_next_sibling()
            widget.source_rows[source['key']] = (
                row_box, sl, hid, pct_label
            )
            sources_box.append(row_box)

        main_box.append(sources_box)
        widget.set_widget(main_box)

    def sync_popover_rows(self, widget, sources):
        """Diff sources against existing rows; add, remove, or update."""
        current_keys = {s['key']: s for s in sources}
        existing_keys = set(widget.source_rows.keys())

        # Remove rows for disconnected sources
        for key in existing_keys - current_keys.keys():
            row_box, _sl, _hid, _pct = widget.source_rows.pop(key)
            widget.sources_box.remove(row_box)
            # Cancel any pending debounce for this key
            handle = widget._debounce.pop(key, None)
            if handle is not None:
                GLib.source_remove(handle)

        # Add rows for newly connected sources
        for key in current_keys.keys() - existing_keys:
            source = current_keys[key]
            row_box, sl, hid = self._make_row(widget, source)
            pct_label = sl.get_next_sibling()
            widget.source_rows[key] = (row_box, sl, hid, pct_label)
            widget.sources_box.append(row_box)

        # Silently update sliders for existing rows (skip if being dragged)
        for key, source in current_keys.items():
            if key not in widget.source_rows:
                continue
            _row_box, sl, hid, pct_label = widget.source_rows[key]
            # Skip update while user is interacting or a write is pending
            if key in widget._debounce:
                continue
            new_val = source['brightness']
            if sl.get_value() != new_val:
                # Block by handler ID to avoid re-triggering the debounce
                sl.handler_block(hid)
                sl.set_value(new_val)
                sl.handler_unblock(hid)
                max_b = source['max_brightness']
                pct_label.set_text(
                    f'{round((new_val / max_b) * 100)}%'
                )

    # ------------------------------------------------------------------
    # Widget creation and UI update
    # ------------------------------------------------------------------

    def _find_source_for_connector(self, sources, connector):
        """Return the DDC source whose connector matches, or None."""
        if not connector:
            return None
        for s in sources:
            if s.get('connector') == connector:
                return s
        return None

    def create_widget(self, bar):
        """Create the brightness bar module."""
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon(self.ICON)
        m.set_label('...')
        m.set_visible(True)

        # Store the connector name for this bar's monitor so scroll and
        # label can target the right DDC source.
        try:
            m._connector = bar.monitor.get_connector()
        except Exception:
            m._connector = None

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)

        def scroll_action(_controller, _dx, dy):
            """Scroll the source that matches this bar's monitor."""
            data = c.state_manager.get(self.name)
            if not data:
                return
            sources = data.get('sources', [])
            if not sources:
                return
            widget = widget_ref()
            if widget is None:
                return
            connector = getattr(widget, '_connector', None)
            source = self._find_source_for_connector(sources, connector)
            # Fall back to single-source behaviour when no match
            if source is None:
                if len(sources) != 1:
                    return
                source = sources[0]
            max_b = source['max_brightness']
            key = source['key']
            # Always step 1% of max regardless of source kind
            delta = max(1, round(max_b * 0.01))
            # Use pending value if a debounce is in flight, else state value
            if not hasattr(widget, '_scroll_pending'):
                widget._scroll_pending = {}
            if not hasattr(widget, '_scroll_debounce'):
                widget._scroll_debounce = {}
            current = widget._scroll_pending.get(
                key, source['brightness']
            )
            # dy > 0 → scroll down → dimmer; dy < 0 → scroll up → brighter
            new_val = current + (-delta if dy > 0 else delta)
            new_val = max(0, min(new_val, max_b))
            widget._scroll_pending[key] = new_val
            # Update label immediately
            pct = round((new_val / max_b) * 100)
            widget.set_label(f'{pct}%')
            # Cancel any pending write and reschedule
            handle = widget._scroll_debounce.get(key)
            if handle is not None:
                GLib.source_remove(handle)

            def do_scroll_apply():
                widget._scroll_debounce.pop(key, None)
                # Keep pending value until next poll confirms the new state
                self._apply_brightness(source, new_val)
                # Wake the worker so the widget reflects the new value
                import module as _module
                _module.force_update(self.name)
                return GLib.SOURCE_REMOVE

            widget._scroll_debounce[key] = GLib.timeout_add(
                300, do_scroll_apply
            )

        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll_controller.connect('scroll', scroll_action)
        m.add_controller(scroll_controller)

        return m

    def update_ui(self, widget, data):
        """Update bar label and sync popover rows from state data."""
        if not data:
            widget.set_label('ERR')
            widget.set_visible(True)
            return

        sources = data.get('sources', [])
        if not sources:
            widget.set_label('ERR')
            widget.set_visible(True)
            return

        widget.set_visible(True)

        # Prefer the source for this bar's monitor; fall back to
        # single-source pct or icon-only for multiple sources.
        connector = getattr(widget, '_connector', None)
        matched = self._find_source_for_connector(sources, connector)
        label_source = matched if matched else (
            sources[0] if len(sources) == 1 else None
        )
        if label_source:
            key = label_source['key']
            pending = getattr(widget, '_scroll_pending', {})
            if key in pending:
                # Clear pending once polled state has caught up
                if label_source['brightness'] == pending[key]:
                    pending.pop(key, None)
                else:
                    # Write still in flight; keep showing the pending value
                    pct = round((pending[key] / label_source['max_brightness'])
                                * 100)
                    widget.set_label(f'{pct}%')
                    return
            pct = round(
                (label_source['brightness']
                 / label_source['max_brightness']) * 100
            )
            widget.set_label(f'{pct}%')
        else:
            widget.set_label('')

        # First call: build the popover structure
        if not hasattr(widget, 'source_rows'):
            self.build_popover(widget, sources)
            return

        # Subsequent calls: diff and patch rows in place
        self.sync_popover_rows(widget, sources)


module_map = {
    'backlight': Backlight,
    'ddc': Backlight,
    'brightness': Backlight,
}
