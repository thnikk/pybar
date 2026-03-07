#!/usr/bin/python3 -u
"""
Description: UPower module using Gio.DBusProxy directly (no dasbus)
Author: thnikk
"""
import weakref
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Gio  # noqa

UPOWER_SERVICE = 'org.freedesktop.UPower'
UPOWER_PATH = '/org/freedesktop/UPower'
UPOWER_IFACE = 'org.freedesktop.UPower'
DEVICE_IFACE = 'org.freedesktop.UPower.Device'

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
    2: "",   # Battery
    3: "",   # UPS
    5: "",   # Mouse
    7: "",   # Keyboard
    13: "",  # Controller
    18: "",  # Headset
    19: "",  # Speakers
    20: "",  # Headphones
    29: "",  # Bluetooth
}

# UPower BatteryLevel enum mapping to 0-4 (critical to full)
BATT_LEVEL_MAP = {
    3: 0,  # Critical
    2: 1,  # Low
    4: 2,  # Normal
    5: 3,  # High
    6: 4,  # Full
}


def _get_prop(proxy, prop, default=None):
    """ Safely get a cached DBus property """
    try:
        var = proxy.get_cached_property(prop)
        return var.unpack() if var is not None else default
    except Exception:
        return default


class UPower(c.BaseModule):
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
        # path -> Gio.DBusProxy
        self._device_proxies = {}

    def get_device_data(self, proxy):
        """ Extract relevant data from a device proxy """
        try:
            if _get_prop(proxy, 'IsPresent', default=True) is False:
                return None

            dev_type = _get_prop(proxy, 'Type', default=0)
            if dev_type in (0, 1):
                return None

            vendor = _get_prop(proxy, 'Vendor', default='') or ''
            model = _get_prop(proxy, 'Model', default='') or ''
            name = ''
            if vendor and vendor != 'Unknown':
                name += vendor + ' '
            if model and model != 'Unknown':
                name += model
            name = name.strip() or TYPE_MAP.get(dev_type, 'Unknown Device')

            if any(i in name.lower() for i in self.ignore):
                return None

            percentage = _get_prop(proxy, 'Percentage', default=0) or 0
            battery_level = _get_prop(proxy, 'BatteryLevel', default=0) or 0

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
                icon = ''

            return {
                'name': name,
                'level': level,
                'percentage': int(round(percentage)),
                'icon': icon,
                'type': dev_type
            }
        except Exception as e:
            c.print_debug(f"UPower error getting device data: {e}")
            return None

    def update_state(self):
        """ Collect all device data and push to state manager """
        devices = []
        icons = []
        for proxy in self._device_proxies.values():
            data = self.get_device_data(proxy)
            if data:
                devices.append(data)
                icons.append(data['icon'])
        text = '  '.join(sorted(set(icons)))
        c.state_manager.update(self.name, {'text': text, 'devices': devices})

    def _on_device_properties_changed(
            self, _proxy, _changed, _invalidated, _data):
        """ Handle property changes on a device proxy """
        self.update_state()

    def _setup_device(self, path):
        """ Create a proxy for a device path and connect signals """
        if path in self._device_proxies:
            return
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                UPOWER_SERVICE, path, DEVICE_IFACE,
                None
            )
            proxy.connect(
                'g-properties-changed',
                self._on_device_properties_changed,
                None
            )
            self._device_proxies[path] = proxy
            c.print_debug(
                f"UPower: Monitoring device {path}", color='green')
        except Exception as e:
            c.print_debug(
                f"UPower error setting up device {path}: {e}")

    def _on_upower_signal(
            self, _proxy, _sender, signal_name, params, *_args):
        """ Handle DeviceAdded / DeviceRemoved signals """
        path = params[0] if params else None
        if not path:
            return
        if signal_name == 'DeviceAdded':
            self._setup_device(path)
            self.update_state()
        elif signal_name == 'DeviceRemoved':
            self._device_proxies.pop(path, None)
            self.update_state()

    def run_worker(self):
        """ Background worker to monitor UPower via Gio """
        try:
            upower_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                UPOWER_SERVICE, UPOWER_PATH, UPOWER_IFACE,
                None
            )
        except Exception as e:
            c.print_debug(f"UPower worker failed: {e}", color='red')
            return

        # g-signal covers DeviceAdded and DeviceRemoved
        upower_proxy.connect('g-signal', self._on_upower_signal)

        # Enumerate existing devices
        try:
            result = upower_proxy.call_sync(
                'EnumerateDevices', None,
                Gio.DBusCallFlags.NONE, -1, None
            )
            for path in result[0]:
                self._setup_device(path)
        except Exception as e:
            c.print_debug(f"UPower EnumerateDevices error: {e}")

        self.update_state()

        # Keep thread alive; updates arrive via GLib signal dispatch
        import time
        while True:
            time.sleep(60)
            # Periodic refresh in case signals were missed
            try:
                result = upower_proxy.call_sync(
                    'EnumerateDevices', None,
                    Gio.DBusCallFlags.NONE, -1, None
                )
                current = set(result[0])
                known = set(self._device_proxies.keys())
                for path in current - known:
                    self._setup_device(path)
                for path in known - current:
                    self._device_proxies.pop(path, None)
                if current != known:
                    self.update_state()
            except Exception:
                pass

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
