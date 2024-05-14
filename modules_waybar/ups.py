#!/usr/bin/python3 -u
"""
Description: CyberPower UPS waybar module. Inspired by
https://github.com/bjonnh/cyberpower-usb-watcher
Author: thnikk
"""
import json
import argparse
import sys
import os
import hid
from modules_waybar.common import Cache
import modules_waybar.tooltip as tt


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser(description="CyberPower UPS module")
    parser.add_argument('vendor', action='store', type=str, help='Vendor ID')
    parser.add_argument('product', action='store', type=str, help='Product ID')
    parser.add_argument(
        '-o', '--offset', type=int, default=0, help='Wattage offset')
    return parser.parse_args()


class CyberPower:
    """ Class for CyberPower UPS """
    def __init__(self, vendor, product, offset) -> None:
        self.device = hid.Device(
            path=hid.enumerate(vendor, product)[0]['path'])
        self.offset = offset
        self.status_report = self.device.get_feature_report(0x0b, 3)[1]

    def load_watts(self) -> int:
        """ Get load """
        return round(self.capacity() * (self.load_percent()/100) / 10) * 10

    def offset_watts(self) -> int:
        """ Get offset watts """
        return self.load_watts() - self.offset

    def load_percent(self) -> int:
        """ Get load percentage """
        return self.device.get_feature_report(0x13, 2)[1]

    def capacity(self) -> int:
        """ Get capacity in watts """
        report = self.device.get_feature_report(0x18, 6)
        return report[2] * 256 + report[1]

    def runtime(self) -> int:
        """ Battery runtime """
        report = self.device.get_feature_report(0x08, 6)
        return int((report[3]*256+report[2])/60)

    def battery_percent(self) -> int:
        """ Battery percentage """
        return self.device.get_feature_report(0x08, 6)[1]

    def ac(self) -> bool:
        """ AC status """
        return bool(self.status_report & 1)

    def charging(self) -> bool:
        """ Charging status """
        return bool(self.status_report & 2)

    def full(self) -> bool:
        """ Full status """
        return bool((self.status_report & 16) > 0)

    def close(self) -> None:
        """ Close device """
        self.device.close()


def module(config):
    """ Module """
    cache = Cache(os.path.expanduser("~/.cache/ups.json"))
    if 'vendor' not in config:
        config['vendor'] = "0764"
    if 'product' not in config:
        config['product'] = "0501"
    if 'offset' not in config:
        config['offset'] = 0
    try:
        try:
            ups = CyberPower(
                int(config['vendor'], 16),
                int(config['product'], 16),
                config['offset']
            )
        except IndexError as e:
            print(e)
            sys.exit(1)
        output = {
            "text": f" {ups.offset_watts()}W",
            "tooltip": "\n".join([
                tt.heading('UPS stats'),
                f"Runtime: {ups.runtime()} minutes",
                f"Load: {ups.load_watts()} Watts ({ups.load_percent()}%)",
                f"Battery: {ups.battery_percent()}%",
                f"AC power: {ups.ac()}",
                f"Charging: {ups.charging()}",
                f"Battery full: {ups.full()}",
            ]),
            "widget": {
                "load_offset": ups.offset_watts(),
                "runtime": ups.runtime(),
                "load_watts": ups.load_watts(),
                "load_percent": ups.load_percent(),
                "battery": ups.battery_percent(),
                "ac_power": ups.ac(),
                "charging": ups.charging(),
                "battery_full": ups.full()
            }
        }
        if not ups.ac():
            output['class'] = 'red'
        cache.save(json.dumps(output))
        ups.close()
        return output
    except hid.HIDException:
        return cache.load()


def main():
    """ Main function """
    args = parse_args()
    print(json.dumps(
        module(args.vendor, args.product, args.offset), indent=4
    ))


if __name__ == "__main__":
    main()
