#!/usr/bin/python3 -u
"""
Description: Power supply module refactored for unified state
Author: thnikk
"""
from glob import glob
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

icon_lookup = {"Mouse": "", "Controller": ""}
capacity_lookup = ["critical", "low", "normal", "high", "full"]


class PowerSupply(c.BaseModule):
    def parse_uevent(self, uevent):
        output = {}
        for line in uevent.splitlines():
            if '=' not in line:
                continue
            left = line.split('=')[0].replace(
                'POWER_SUPPLY_', '').replace('_', ' ').capitalize()
            right = line.split('=')[-1]
            output[left] = right
        return output

    def fetch_data(self):
        icons = []
        devices = []
        ignore = self.config.get('ignore', [])

        for path in glob('/sys/class/power_supply/*'):
            try:
                with open(f"{path}/uevent") as file:
                    parsed = self.parse_uevent(file.read())

                    if "Model name" in parsed:
                        dev_name = parsed["Model name"]
                    elif "Name" in parsed:
                        dev_name = parsed["Name"].split(
                            "battery")[0].replace('-', ' ').strip().title()
                    else:
                        dev_name = "Unknown"

                    if any(i in dev_name.lower() for i in ignore):
                        continue

                    try:
                        if "Capacity level" in parsed:
                            level = capacity_lookup.index(
                                parsed["Capacity level"].lower())
                        elif "Capacity" in parsed:
                            level = (int(parsed["Capacity"]) // 20) - 1
                        else:
                            level = -1
                    except ValueError:
                        level = -1

                    dev_icon = ""
                    for name, icon in icon_lookup.items():
                        if name.lower() in dev_name.lower():
                            dev_icon = icon
                            break

                    icons.append(dev_icon)
                    devices.append({"name": dev_name, "level": level})
            except Exception:
                continue

        return {
            "text": "  ".join(set(icons)),
            "devices": devices
        }

    def build_popover(self, widget, data):
        widget.popover_widgets = []
        box = c.box('v', spacing=20, style='small-widget')
        box.append(c.label('Power Supply', style='heading'))

        outer = c.box('v', style='box')
        for i, dev in enumerate(data['devices']):
            row = c.box('h', spacing=10, style="inner-box")
            row.append(c.label(dev['name'], ha="start", he=True))

            lvl = Gtk.LevelBar.new_for_interval(0, 4)
            lvl.set_min_value(0)
            lvl.set_max_value(4)
            lvl.set_value(dev['level'] + 1)
            row.append(lvl)

            percent = (dev['level'] + 1) * 25
            pct_label = c.label(f"{percent}%", style='percent')
            row.append(pct_label)

            widget.popover_widgets.append({
                'name': dev['name'],
                'level': lvl,
                'percent': pct_label
            })

            outer.append(row)
            if i < len(data['devices']) - 1:
                outer.append(c.sep('h'))

        box.append(outer)
        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.popover_widgets = []

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
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
            for w in widget.popover_widgets:
                if w['name'] in devices:
                    dev = devices[w['name']]
                    w['level'].set_value(dev['level'] + 1)
                    w['percent'].set_text(f"{(dev['level'] + 1) * 25}%")


module_map = {
    'power_supply': PowerSupply
}
