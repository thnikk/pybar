#!/usr/bin/python3 -u
"""
Description: CyberPower UPS module refactored for unified state
Author: thnikk
"""
import hid
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class CyberPower:
    def __init__(self, device, offset) -> None:
        self.device = device
        self.offset = offset
        try:
            self.status_report = self.device.get_feature_report(0x0b, 3)[1]
        except Exception:
            self.status_report = 0

    def load_watts(self) -> int:
        return round(
            self.capacity() * (self.load_percent() / 100) / 10) * 10

    def offset_watts(self) -> int:
        return self.load_watts() - self.offset

    def load_percent(self) -> int:
        try:
            return self.device.get_feature_report(0x13, 2)[1]
        except Exception:
            return 0

    def capacity(self) -> int:
        try:
            report = self.device.get_feature_report(0x18, 6)
            return report[2] * 256 + report[1]
        except Exception:
            return 0

    def runtime(self) -> int:
        try:
            report = self.device.get_feature_report(0x08, 6)
            return int((report[3] * 256 + report[2]) / 60)
        except Exception:
            return 0

    def battery_percent(self) -> int:
        try:
            return self.device.get_feature_report(0x08, 6)[1]
        except Exception:
            return 0

    def ac(self) -> bool:
        return bool(self.status_report & 1)

    def charging(self) -> bool:
        return bool(self.status_report & 2)

    def full(self) -> bool:
        return bool((self.status_report & 16) > 0)


class UPS(c.BaseModule):
    def fetch_data(self):
        vendor = int(self.config.get('vendor', "0764"), 16)
        product = int(self.config.get('product', "0501"), 16)
        offset = self.config.get('offset', 0)

        try:
            devices = hid.enumerate(vendor, product)
            if not devices:
                return {}

            with hid.Device(path=devices[0]['path']) as device:
                ups = CyberPower(device, offset)
                ac = ups.ac()
                watts = ups.offset_watts()

                return {
                    "text": f" {watts}W",
                    "load_offset": watts,
                    "runtime": ups.runtime(),
                    "load_watts": ups.load_watts(),
                    "load_percent": ups.load_percent(),
                    "battery": ups.battery_percent(),
                    "ac_power": ac,
                    "charging": ups.charging(),
                    "battery_full": ups.full(),
                    "class": "" if ac else "red"
                }
        except Exception as e:
            c.print_debug(f"UPS fetch failed: {e}", color='red')
            return {}

    def build_popover(self, data):
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('UPS stats', style='heading'))

        wide_box = c.box('h', spacing=20)
        wide_box.append(c.label(
            f"{data['load_percent']}%", style='large-text'))

        detail_box = c.box('v')
        detail_box.append(c.label(
            f"{data['runtime']} minutes", ha='end', he=True))
        detail_box.append(
                c.label("runtime", style='gray', ha='end', he=True))
        wide_box.append(detail_box)
        main_box.append(wide_box)

        info_box = c.box('v', style='box')
        info_line = c.box('h')

        items = []
        if data['ac_power']:
            items.append(" AC")
        if data['charging']:
            items.append(" Charging")
        items.append(f" {data['battery']}%")
        items.append(f"{data['load_watts']}W")

        for i, item in enumerate(items):
            info_line.append(c.label(item, style='inner-box', he=True))
            if i < len(items) - 1:
                info_line.append(c.sep('v'))

        info_box.append(info_line)
        main_box.append(info_box)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.reset_style()
        if data.get('class'):
            c.add_style(widget, data['class'])

        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'ups': UPS
}
