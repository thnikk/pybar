#!/usr/bin/python3 -u
"""
Description: UPower module for tracking device battery levels via DBus
Author: thnikk
"""
import weakref
import common as c
from dasbus.connection import SystemMessageBus
from dasbus.client.proxy import disconnect_proxy
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

# UPower device types
TYPE_MAP = {
    0: "Unknown",
    1: "Line Power",
    2: "Battery",
    3: "UPS",
    4: "Monitor",
    5: "Mouse",
    6: "Touchpad",
    7: "Keyboard",
    8: "PDA",
    9: "Phone",
    10: "Media Player",
    11: "Tablet",
    12: "Computer",
    13: "Controller",
    14: "Pen",
    15: "Touchpad",
    16: "Modem",
    17: "Network",
    18: "Headset",
    19: "Speakers",
    20: "Headphones",
    21: "Video",
    22: "Audio",
    23: "Remote",
    24: "Printer",
    25: "Scanner",
    26: "Camera",
    27: "Wearable",
    28: "Toy",
    29: "Bluetooth"
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


def unwrap(val):
    if hasattr(val, 'unpack'):
        val = val.unpack()
    if hasattr(val, 'value'):
        val = val.value
    return val


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
        self.bus = SystemMessageBus()
        self.proxies = {}
        self.devices_data = {}
        self.ignore = [i.lower() for i in config.get('ignore', [])]

    def get_device_data(self, proxy):
        """ Extract relevant data from a device proxy """
        try:
            # Check if device is present
            if not unwrap(proxy.IsPresent):
                return None

            dev_type = unwrap(proxy.Type)
            # Skip line power (AC adapters)
            if dev_type == 1:
                return None

            model = unwrap(proxy.Model)
            vendor = unwrap(proxy.Vendor)

            # Try to get a decent name
            name = ""
            if vendor and vendor != "Unknown":
                name += vendor + " "
            if model and model != "Unknown":
                name += model

            name = name.strip() or TYPE_MAP.get(dev_type, "Unknown Device")

            if any(i in name.lower() for i in self.ignore):
                return None

            percentage = unwrap(proxy.Percentage)
            battery_level = unwrap(proxy.BatteryLevel)

            # If percentage is 0 or missing, but we have a battery level enum,
            # use the enum to estimate a percentage for the bar
            if (not percentage or percentage <= 0) and \
                    battery_level in BATT_LEVEL_MAP:
                # Map 0-4 to 10, 30, 60, 85, 100
                est_map = {0: 10, 1: 30, 2: 60, 3: 85, 4: 100}
                percentage = est_map.get(BATT_LEVEL_MAP[battery_level], 0)

            # Map level to 0-4
            if battery_level in BATT_LEVEL_MAP:
                level = BATT_LEVEL_MAP[battery_level]
            else:
                level = int(percentage // 20) - 1
                level = max(0, min(level, 4))

            icon = ICON_LOOKUP.get(dev_type, "")
            if "xbox" in name.lower() or "controller" in name.lower():
                icon = ""

            return {
                "name": name,
                "level": level,
                "percentage": int(round(percentage)),
                "icon": icon,
                "type": dev_type
            }
        except Exception as e:
            c.print_debug(f"UPower error getting device data: {e}")
            return None

    def update_state(self):
        """ Collect all device data and update state manager """
        devices = []
        icons = []

        for path, proxy in self.proxies.items():
            data = self.get_device_data(proxy)
            if data:
                devices.append(data)
                icons.append(data['icon'])

        # Unique set of icons to show in the bar
        text = "  ".join(sorted(list(set(icons))))

        c.state_manager.update(self.name, {
            "text": text,
            "devices": devices
        })

    def on_properties_changed(self, proxy, interface, changed, invalidated):
        """ Handle property changes on a device """
        if interface == 'org.freedesktop.UPower.Device':
            self.update_state()

    def setup_device(self, path):
        """ Setup proxy and signals for a device path """
        if path in self.proxies:
            return

        try:
            proxy = self.bus.get_proxy('org.freedesktop.UPower', path)
            # Connect to PropertiesChanged signal
            # dasbus doesn't directly expose PropertiesChanged for all proxies
            # in a simple way
            # We use the underlying DBus.Properties interface
            props_proxy = self.bus.get_proxy(
                'org.freedesktop.UPower', path,
                interface_name='org.freedesktop.DBus.Properties'
            )

            def cb(interface, changed, invalidated, p=proxy):
                self.on_properties_changed(p, interface, changed, invalidated)

            props_proxy.PropertiesChanged.connect(cb)

            # Store both to prevent GC and for cleanup
            self.proxies[path] = proxy
            self.proxies[f"{path}_props"] = props_proxy

            c.print_debug(f"UPower: Monitoring device {path}", color='green')
        except Exception as e:
            c.print_debug(f"UPower error setting up device {path}: {e}")

    def run_worker(self):
        """ Background worker to monitor UPower """
        try:
            upower_proxy = self.bus.get_proxy(
                'org.freedesktop.UPower', '/org/freedesktop/UPower')

            def on_device_added(path):
                self.setup_device(path)
                self.update_state()

            def on_device_removed(path):
                if path in self.proxies:
                    disconnect_proxy(self.proxies.pop(path))
                    disconnect_proxy(self.proxies.pop(f"{path}_props"))
                    self.update_state()

            upower_proxy.DeviceAdded.connect(on_device_added)
            upower_proxy.DeviceRemoved.connect(on_device_removed)

            # Initial devices
            for path in upower_proxy.EnumerateDevices():
                self.setup_device(path)

            self.update_state()

        except Exception as e:
            c.print_debug(f"UPower worker failed: {e}", color='red')
            return

        # Keep alive
        while True:
            import time
            time.sleep(60)
            # Occasionally refresh list in case signals were missed
            try:
                current_paths = upower_proxy.EnumerateDevices()
                changed = False
                for path in current_paths:
                    if path not in self.proxies:
                        self.setup_device(path)
                        changed = True

                # Check for removed
                to_remove = [p for p in self.proxies if p.startswith(
                    '/') and p not in current_paths]
                for p in to_remove:
                    disconnect_proxy(self.proxies.pop(p))
                    disconnect_proxy(self.proxies.pop(f"{p}_props"))
                    changed = True

                if changed:
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

        for i, dev in enumerate(devices):
            device_box = c.box('v', spacing=10)

            # Name and icon above the bar box
            name_label = c.label(
                f"{dev['icon']}  {dev['name']}", ha="start", style='title')
            device_box.append(name_label)

            # Box containing level bar and percentage
            outer = c.box('v', spacing=10, style='box')
            row = c.box('h', spacing=10, style="inner-box")

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
            # Live update
            devices = {d['name']: d for d in data.get('devices', [])}
            # We might need to rebuild if devices changed significantly
            current_names = {w['name'] for w in widget.popover_widgets}
            new_names = set(devices.keys())

            if current_names != new_names:
                # Device list changed, update the EXISTING popover's box
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
