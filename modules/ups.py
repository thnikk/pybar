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
        return round(self.capacity() * (self.load_percent()/100) / 10) * 10

    def offset_watts(self) -> int:
        return self.load_watts() - self.offset

    def load_percent(self) -> int:
        try: return self.device.get_feature_report(0x13, 2)[1]
        except Exception: return 0

    def capacity(self) -> int:
        try:
            report = self.device.get_feature_report(0x18, 6)
            return report[2] * 256 + report[1]
        except Exception: return 0

    def runtime(self) -> int:
        try:
            report = self.device.get_feature_report(0x08, 6)
            return int((report[3]*256+report[2])/60)
        except Exception: return 0

    def battery_percent(self) -> int:
        try: return self.device.get_feature_report(0x08, 6)[1]
        except Exception: return 0

    def ac(self) -> bool:
        return bool(self.status_report & 1)

    def charging(self) -> bool:
        return bool(self.status_report & 2)

    def full(self) -> bool:
        return bool((self.status_report & 16) > 0)

def fetch_data(config):
    vendor = int(config.get('vendor', "0764"), 16)
    product = int(config.get('product', "0501"), 16)
    offset = config.get('offset', 0)
    
    try:
        devices = hid.enumerate(vendor, product)
        if not devices: return None
        
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
    except Exception:
        return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    return module

def update_ui(module, data):
    module.set_label(data['text'])
    module.reset_style()
    if data.get('class'):
        c.add_style(module, data['class'])
        
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('UPS stats', style='heading'))

    wide_box = c.box('h', spacing=20)
    wide_box.append(c.label(f"{data['load_percent']}%", style='large-text'))
    
    detail_box = c.box('v')
    detail_box.append(c.label(f"{data['runtime']} minutes", ha='start'))
    detail_box.append(c.label("runtime", style='gray', ha='start'))
    wide_box.append(detail_box)
    main_box.append(wide_box)

    icons = {"load_watts": "W", "charging": "", "ac_power": "", "battery": ""}
    
    info_box = c.box('v', style='box')
    info_line = c.box('h')
    
    items = []
    if data['ac_power']: items.append(" AC")
    if data['charging']: items.append(" Charging")
    items.append(f" {data['battery']}%")
    items.append(f"{data['load_watts']}W")
    
    for i, item in enumerate(items):
        info_line.append(c.label(item))
        if i < len(items) - 1:
            info_line.append(c.sep('v'))
            
    info_box.append(info_line)
    main_box.append(info_box)

    return main_box
