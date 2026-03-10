#!/usr/bin/python3 -u
"""
Description: UPower module using Gio.DBusProxy directly (no dasbus)
Author: thnikk
"""
import weakref
import time
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio  # noqa

UPOWER_SERVICE = 'org.freedesktop.UPower'
UPOWER_PATH = '/org/freedesktop/UPower'
UPOWER_IFACE = 'org.freedesktop.UPower'
DEVICE_IFACE = 'org.freedesktop.UPower.Device'
PROPS_IFACE = 'org.freedesktop.DBus.Properties'

TYPE_MAP = {
    0: "Unknown", 1: "Line Power", 2: "Battery", 3: "UPS",
    4: "Monitor", 5: "Mouse", 6: "Touchpad", 7: "Keyboard",
    8: "PDA", 9: "Phone", 10: "Media Player", 11: "Tablet",
    12: "Computer", 13: "Controller", 14: "Pen", 15: "Touchpad",
    16: "Modem", 17: "Network", 18: "Headset", 19: "Speakers",
    20: "Headphones", 21: "Video", 22: "Audio", 23: "Remote",
    24: "Printer", 25: "Scanner", 26: "Camera", 27: "Wearable",
    28: "Toy", 29: "Bluetooth"
}

ICON_LOOKUP = {
    2: "\uf240",   # Battery (fa-battery-full)
    3: "\uf207",   # UPS (fa-plug)
    5: "\uf8cc",   # Mouse (fa-computer-mouse)
    7: "\uf11c",   # Keyboard (fa-keyboard)
    13: "\uf11b",  # Controller (fa-gamepad)
    18: "\uf58f",  # Headset (fa-headphones-alt)
    19: "\uf028",  # Speakers (fa-volume-up)
    20: "\uf58f",  # Headphones (fa-headphones-alt)
    29: "\uf293",  # Bluetooth (fa-bluetooth)
}

# UPower BatteryLevel enum mapping to 0-4 (critical to full)
BATT_LEVEL_MAP = {
    3: 0,  # Critical
    2: 1,  # Low
    4: 2,  # Normal
    5: 3,  # High
    6: 4,  # Full
}


class UPower(c.BaseModule):
    DEFAULT_INTERVAL = 30

    SCHEMA = {
        'ignore': {
            'type': 'list',
            'default': [],
            'label': 'Ignore List',
            'description': 'List of device names to ignore'
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.ignore = [i.lower() for i in config.get('ignore', [])]
        # system bus connection, created once in run_worker
        self._bus = None
        # set of known device paths
        self._device_paths = set()
        # subscriptions to cancel on cleanup
        self._signal_subs = []

    def _get_all_props(self, path):
        """
        Call org.freedesktop.DBus.Properties.GetAll on a device path.
        Returns a plain dict of property name -> unpacked value, or None.
        This guarantees we get fresh values rather than relying on the
        proxy's property cache, which may be empty right after creation.
        """
        try:
            result = self._bus.call_sync(
                UPOWER_SERVICE,
                path,
                PROPS_IFACE,
                'GetAll',
                GLib.Variant('(s)', (DEVICE_IFACE,)),
                GLib.VariantType.new('(a{sv})'),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            # result[0] is a dict of str -> GLib.Variant (or already unpacked)
            return {
                k: v.unpack() if hasattr(v, 'unpack') else v
                for k, v in result[0].items()
            }
        except Exception as e:
            c.print_debug(
                f"UPower GetAll failed for {path}: {e}", color='red')
            return None

    def _props_to_device(self, props):
        """
        Convert a raw property dict from GetAll into a device data dict.
        Returns None if the device should be skipped.
        """
        if not props:
            return None

        # Skip absent or line-power devices
        if props.get('IsPresent', True) is False:
            return None
        dev_type = props.get('Type', 0)
        if dev_type in (0, 1):
            return None

        vendor = props.get('Vendor', '') or ''
        model = props.get('Model', '') or ''
        name = ''
        if vendor and vendor != 'Unknown':
            name += vendor + ' '
        if model and model != 'Unknown':
            name += model
        name = name.strip() or TYPE_MAP.get(dev_type, 'Unknown Device')

        if any(i in name.lower() for i in self.ignore):
            return None

        percentage = props.get('Percentage', 0) or 0
        battery_level = props.get('BatteryLevel', 0) or 0

        # Fall back to estimated percentage from coarse battery level
        if (not percentage or percentage <= 0) and (
                battery_level in BATT_LEVEL_MAP):
            est_map = {0: 10, 1: 30, 2: 60, 3: 85, 4: 100}
            percentage = est_map.get(BATT_LEVEL_MAP[battery_level], 0)

        if battery_level in BATT_LEVEL_MAP:
            level = BATT_LEVEL_MAP[battery_level]
        else:
            level = max(0, min(int(percentage // 20) - 1, 4))

        icon = ICON_LOOKUP.get(dev_type, '')
        if 'xbox' in name.lower() or 'controller' in name.lower():
            icon = "\uf11b"

        return {
            'name': name,
            'level': level,
            'percentage': int(round(percentage)),
            'icon': icon,
            'type': dev_type
        }

    def fetch_data(self):
        """
        Enumerate UPower devices and call GetAll on each one.
        Returns a state dict ready for the state manager.
        """
        if self._bus is None:
            return None
        try:
            result = self._bus.call_sync(
                UPOWER_SERVICE,
                UPOWER_PATH,
                UPOWER_IFACE,
                'EnumerateDevices',
                None,
                GLib.VariantType.new('(ao)'),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            paths = result[0]
        except Exception as e:
            c.print_debug(f"UPower EnumerateDevices error: {e}", color='red')
            return None

        self._device_paths = set(paths)
        devices = []
        icons = []
        for path in paths:
            props = self._get_all_props(path)
            dev = self._props_to_device(props)
            if dev:
                devices.append(dev)
                icons.append(dev['icon'])
                c.print_debug(
                    f"UPower: found device '{dev['name']}'", color='green')

        text = '  '.join(sorted(set(icons)))
        return {'text': text, 'devices': devices}

    def _wake_worker(self):
        """ Signal the worker thread to run fetch_data immediately """
        import module as mod
        wake = mod._worker_wake_flags.get(self.name)
        if wake:
            wake.set()

    def _on_device_signal(
            self, _conn, _sender, _path, _iface, signal_name,
            _params, _data):
        """
        Callback for DeviceAdded / DeviceRemoved on the UPower interface.
        Wakes the worker so fetch_data runs right away.
        """
        c.print_debug(f"UPower: signal {signal_name}, waking worker")
        self._wake_worker()

    def _on_props_changed(
            self, _conn, _sender, path, _iface, _signal,
            _params, _data):
        """
        Callback for PropertiesChanged on any monitored device path.
        Wakes the worker so fetch_data runs right away.
        """
        c.print_debug(
            f"UPower: properties changed on {path}, waking worker")
        self._wake_worker()

    def run_worker(self):
        """ Background worker: set up DBus subscriptions then run base loop """
        import module as mod

        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        except Exception as e:
            c.print_debug(f"UPower: bus_get_sync failed: {e}", color='red')
            return

        # Subscribe to DeviceAdded / DeviceRemoved on the UPower object
        sub_id = self._bus.signal_subscribe(
            UPOWER_SERVICE,
            UPOWER_IFACE,
            None,           # any signal name
            UPOWER_PATH,
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_device_signal,
            None
        )
        self._signal_subs.append(sub_id)

        stop_event = mod._worker_stop_flags.get(self.name)
        wake_event = mod._worker_wake_flags.get(self.name)

        # track which paths we've already subscribed to
        subscribed_paths = set()

        while True:
            data = self.fetch_data()
            if data is not None:
                # Subscribe to PropertiesChanged for any newly seen paths
                for path in self._device_paths - subscribed_paths:
                    self._bus.signal_subscribe(
                        UPOWER_SERVICE,
                        PROPS_IFACE,
                        'PropertiesChanged',
                        path,
                        None,
                        Gio.DBusSignalFlags.NONE,
                        self._on_props_changed,
                        None
                    )
                    subscribed_paths.add(path)
                c.state_manager.update(self.name, data)

            if not stop_event:
                time.sleep(self.interval)
                continue

            if wake_event:
                woken = wake_event.wait(timeout=self.interval)
                if stop_event.is_set():
                    break
                if woken:
                    wake_event.clear()
            else:
                if stop_event.wait(timeout=self.interval):
                    break

        # Clean up subscriptions
        for sub_id in self._signal_subs:
            try:
                self._bus.signal_unsubscribe(sub_id)
            except Exception:
                pass
        self._signal_subs.clear()

    def _populate_box(self, widget, data, box):
        widget.popover_widgets = []
        box.append(c.label('Power Supply', style='heading'))

        devices = data.get('devices', [])
        if not devices:
            box.append(c.label('No devices found', style='dim-label'))
            return

        for dev in devices:
            device_box = c.box('v', spacing=10)
            name_label = c.label(
                f"{dev['icon']}  {dev['name']}", ha='start', style='title')
            device_box.append(name_label)

            outer = c.box('v', spacing=10, style='box')
            row = c.box('h', spacing=10, style='inner-box')

            lvl = Gtk.LevelBar.new_for_interval(0, 100)
            lvl.set_min_value(0)
            lvl.set_max_value(100)
            lvl.set_value(dev['percentage'])
            lvl.set_hexpand(True)
            row.append(lvl)

            pct_label = c.label(f"{dev['percentage']}%", style='percent')
            pct_label.set_width_chars(4)
            row.append(pct_label)

            widget.popover_widgets.append({
                'name': dev['name'],
                'level': lvl,
                'percent': pct_label
            })

            outer.append(row)
            device_box.append(outer)
            box.append(device_box)

    def build_popover(self, widget, data):
        box = c.box('v', spacing=20, style='small-widget')
        widget.popover_inner_box = box
        self._populate_box(widget, data, box)
        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.popover_widgets = []

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))

        if not widget.get_active():
            widget.set_widget(self.build_popover(widget, data))
        else:
            devices = {d['name']: d for d in data.get('devices', [])}
            current_names = {w['name'] for w in widget.popover_widgets}
            new_names = set(devices.keys())

            if current_names != new_names:
                if hasattr(widget, 'popover_inner_box'):
                    inner_box = widget.popover_inner_box
                    child = inner_box.get_first_child()
                    while child:
                        next_child = child.get_next_sibling()
                        inner_box.remove(child)
                        child = next_child
                    self._populate_box(widget, data, inner_box)
                return

            for w in widget.popover_widgets:
                if w['name'] in devices:
                    dev = devices[w['name']]
                    w['level'].set_value(dev['percentage'])
                    w['percent'].set_text(f"{dev['percentage']}%")
                    w['level'].queue_draw()
                    w['percent'].queue_draw()


module_map = {
    'upower': UPower
}

alias_map = {
    'power_supply': UPower
}
