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
        out = self._ddcutil(['detect', '--brief'])
        if not out:
            return []
        monitors = []
        bus = None
        for line in out.splitlines():
            line = line.strip()
            if line.startswith('I2C bus:'):
                try:
                    bus = int(line.split('/dev/i2c-')[-1])
                except ValueError:
                    bus = None
            elif line.startswith('Monitor:') and bus is not None:
                name = line.split('Monitor:', 1)[-1].strip()
                monitors.append((bus, name))
                bus = None
        sources = []
        for bus, name in monitors:
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

    def _make_slider_handler(self, widget, source):
        """Return a value-changed callback with per-source debounce."""
        key = source['key']

        def on_value_changed(slider):
            # Cancel any pending write for this source
            handle = widget._debounce.get(key)
            if handle is not None:
                GLib.source_remove(handle)

            value = slider.get_value()

            def do_apply():
                widget._debounce.pop(key, None)
                self._apply_brightness(source, value)
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

        outer = c.box('h', style='box')
        outer.set_hexpand(True)
        outer.append(c.label(self.ICON, style='inner-box'))

        sl = c.slider(
            source['brightness'], 0, source['max_brightness']
        )
        sl.set_hexpand(True)
        sl.set_margin_end(10)
        # Connect and store the signal handler ID for block/unblock
        hid = sl.connect(
            'value-changed', self._make_slider_handler(widget, source)
        )
        outer.append(sl)
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
            widget.source_rows[source['key']] = (row_box, sl, hid)
            sources_box.append(row_box)

        main_box.append(sources_box)
        widget.set_widget(main_box)

    def sync_popover_rows(self, widget, sources):
        """Diff sources against existing rows; add, remove, or update."""
        current_keys = {s['key']: s for s in sources}
        existing_keys = set(widget.source_rows.keys())

        # Remove rows for disconnected sources
        for key in existing_keys - current_keys.keys():
            row_box, _sl, _hid = widget.source_rows.pop(key)
            widget.sources_box.remove(row_box)
            # Cancel any pending debounce for this key
            handle = widget._debounce.pop(key, None)
            if handle is not None:
                GLib.source_remove(handle)

        # Add rows for newly connected sources
        for key in current_keys.keys() - existing_keys:
            source = current_keys[key]
            row_box, sl, hid = self._make_row(widget, source)
            widget.source_rows[key] = (row_box, sl, hid)
            widget.sources_box.append(row_box)

        # Silently update sliders for existing rows (skip if being dragged)
        for key, source in current_keys.items():
            if key not in widget.source_rows:
                continue
            _row_box, sl, hid = widget.source_rows[key]
            # Skip update while user is interacting or a write is pending
            if key in widget._debounce:
                continue
            new_val = source['brightness']
            if sl.get_value() != new_val:
                # Block by handler ID to avoid re-triggering the debounce
                sl.handler_block(hid)
                sl.set_value(new_val)
                sl.handler_unblock(hid)

    # ------------------------------------------------------------------
    # Widget creation and UI update
    # ------------------------------------------------------------------

    def create_widget(self, bar):
        """Create the brightness bar module."""
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon(self.ICON)
        m.set_label('...')
        m.set_visible(True)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)

        def scroll_action(_controller, _dx, dy):
            """Scroll adjusts brightness when there is exactly one source."""
            data = c.state_manager.get(self.name)
            if not data:
                return
            sources = data.get('sources', [])
            if len(sources) != 1:
                return
            source = sources[0]
            max_b = source['max_brightness']
            b = source['brightness']
            if source['kind'] == 'sysfs':
                # 1 % of max per tick, matching original behaviour
                delta = round(max_b * 0.01)
            else:
                delta = round(
                    max_b * (self.config.get('step', 5) / 100)
                )
            # dy < 0 → scroll up → brighter
            new_val = b + (-delta if dy < 0 else delta)
            new_val = max(0, min(new_val, max_b))
            self._apply_brightness(source, new_val)

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

        # Bar label: percentage for one source, icon-only for many
        if len(sources) == 1:
            s = sources[0]
            pct = round((s['brightness'] / s['max_brightness']) * 100)
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
