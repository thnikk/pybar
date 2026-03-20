#!/usr/bin/python3 -u
"""
Description: Battery module
Author: thnikk
"""
import common as c
from glob import glob
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Battery(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 60,
            'label': 'Update Interval',
            'description': 'Seconds between battery checks',
            'min': 10,
            'max': 300
        }
    }

    COLORS = [
        (0.64, 0.82, 0.65),  # Greenish
        (0.56, 0.63, 0.75),  # Blueish
        (0.95, 0.74, 0.69),  # Pinkish
        (0.98, 0.89, 0.69),  # Yellowish
    ]

    def fetch_data(self):
        """ Get battery data """
        info = {}
        full = 0
        now = 0

        files_to_read = [
            "energy_now", "energy_full", "energy_full_design",
            "charge_now", "charge_full", "charge_full_design",
            "cycle_count", "capacity", "status"
        ]

        for path in sorted(glob('/sys/class/power_supply/BAT*')):
            battery_info = {}
            for file in files_to_read:
                try:
                    with open(
                            f"{path}/{file}", 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        try:
                            value = int(content)
                        except ValueError:
                            value = content
                        battery_info[file] = value

                        if file in ('energy_now', 'charge_now'):
                            now += battery_info[file]
                        elif file in ('energy_full', 'charge_full'):
                            full += battery_info[file]
                except FileNotFoundError:
                    pass

            if battery_info:
                # Calculate health
                design = battery_info.get(
                    'energy_full_design',
                    battery_info.get('charge_full_design'))
                current_full = battery_info.get(
                    'energy_full',
                    battery_info.get('charge_full'))

                if design and current_full:
                    battery_info['health'] = round(
                        (current_full / design) * 100)

                info[path.split('/')[-1]] = battery_info

        ac_online = 0
        for ac_path in (
            '/sys/class/power_supply/AC/online',
            '/sys/class/power_supply/ADP1/online'
        ):
            try:
                with open(ac_path, 'r', encoding='utf-8') as f:
                    ac_online = int(f.read().strip())
                break
            except FileNotFoundError:
                pass

        percentage = round((now / full) * 100) if full > 0 else 0
        return {
            "percentage": percentage,
            "ac_online": ac_online,
            "devices": info,
            "total_now": now,
            "total_full": full
        }


    def _make_indicator(self, color):
        """ Create a coloured pill indicator box """
        ind = Gtk.Box()
        ind.set_size_request(6, 16)
        r = int(color[0] * 255)
        g = int(color[1] * 255)
        b = int(color[2] * 255)
        css = (
            f"box {{ background-color: rgb({r},{g},{b}); "
            f"border-radius: 999px; }}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode())
        ind.get_style_context().add_provider(
            provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        return ind

    def build_device_rows(self, widget, devices):
        """
        Build per-device rows into battery_box and register their
        widget references into widget.popover_widgets.  Clears any
        previous device widget keys first.
        """
        pw = widget.popover_widgets
        battery_box = pw['battery_box']

        # Remove old device widget refs
        for key in [k for k in pw if k.startswith('dev_')]:
            del pw[key]

        # Clear existing children
        child = battery_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            battery_box.remove(child)
            child = nxt

        sorted_devices = sorted(devices.items())
        for i, (device, info) in enumerate(sorted_devices):
            device_box = c.box('v', style='inner-box', spacing=5)

            # Header row
            header = c.box('h', spacing=10)
            color = self.COLORS[i % len(self.COLORS)]
            header.append(self._make_indicator(color))
            header.append(c.label(device, style='title'))

            now_key = (
                'energy_now' if 'energy_now' in info else 'charge_now')
            full_key = (
                'energy_full' if 'energy_full' in info else 'charge_full')
            percentage = (
                round((info[now_key] / info[full_key]) * 100)
                if info.get(full_key, 0) > 0 else 0
            )
            pct_label = c.label(f'{percentage}%', ha='end', he=True)
            header.append(pct_label)
            pw[f'dev_{device}_pct'] = pct_label
            device_box.append(header)

            # Level bar
            level_bar = c.level(0, 100, percentage)
            level_bar.set_hexpand(True)
            device_box.append(level_bar)
            pw[f'dev_{device}_level'] = level_bar

            # Detail labels
            details = c.box('h', spacing=20)
            if 'energy_full' in info:
                full_wh = info['energy_full'] / 1_000_000
                full_lbl = c.label(
                    f'Full: {full_wh:.1f}Wh', style='dim-label')
                details.append(full_lbl)
                pw[f'dev_{device}_full'] = full_lbl
                if 'energy_full_design' in info:
                    max_wh = info['energy_full_design'] / 1_000_000
                    max_lbl = c.label(
                        f'Max: {max_wh:.1f}Wh', style='dim-label')
                    details.append(max_lbl)
                    pw[f'dev_{device}_max'] = max_lbl
            elif 'charge_full' in info:
                full_ah = info['charge_full'] / 1_000_000
                full_lbl = c.label(
                    f'Full: {full_ah:.1f}Ah', style='dim-label')
                details.append(full_lbl)
                pw[f'dev_{device}_full'] = full_lbl
                if 'charge_full_design' in info:
                    max_ah = info['charge_full_design'] / 1_000_000
                    max_lbl = c.label(
                        f'Max: {max_ah:.1f}Ah', style='dim-label')
                    details.append(max_lbl)
                    pw[f'dev_{device}_max'] = max_lbl

            if 'health' in info:
                health_lbl = c.label(
                    f'Health: {info["health"]}%', style='dim-label')
                details.append(health_lbl)
                pw[f'dev_{device}_health'] = health_lbl

            if info.get('cycle_count', 0) > 0:
                cycle_lbl = c.label(
                    f'Cycles: {info["cycle_count"]}',
                    style='dim-label')
                details.append(cycle_lbl)
                pw[f'dev_{device}_cycles'] = cycle_lbl

            device_box.append(details)
            battery_box.append(device_box)

            if i != len(sorted_devices) - 1:
                battery_box.append(c.sep('h'))


    def build_popover(self, widget, data):
        """ Build popover — called once on first update """
        widget.popover_widgets = {}
        pw = widget.popover_widgets

        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Battery', style='heading'))

        # Summary section
        summary_section = c.box('v', spacing=10)
        summary_section.append(
            c.label('Summary', style='title', ha='start'))
        summary_box = c.box('v', style='box')
        summary_row = c.box('v', spacing=5, style='inner-box')

        summary_labels = c.box('h')
        summary_labels.append(c.label('Combined', ha='start'))
        combined_pct = c.label(
            f'{data.get("percentage", 0)}%', ha='end', he=True)
        summary_labels.append(combined_pct)
        summary_row.append(summary_labels)
        pw['combined_pct'] = combined_pct

        summary_bar = c.PillBar()
        summary_row.append(summary_bar)
        pw['summary_bar'] = summary_bar

        summary_box.append(summary_row)
        summary_section.append(summary_box)
        main_box.append(summary_section)

        # Devices section — battery_box is rebuilt when device set changes
        outer_box = c.box('v', spacing=10)
        outer_box.append(c.label('Devices', style='title', ha='start'))
        battery_box = c.box('v', style='box')
        pw['battery_box'] = battery_box
        outer_box.append(battery_box)
        main_box.append(outer_box)

        # Build initial device rows
        self.build_device_rows(widget, data.get('devices', {}))

        return main_box

    def create_widget(self, bar):
        """ Battery module widget """
        m = super().create_widget(bar)
        m.set_icon('')
        return m

    def update_ui(self, widget, data):
        """ Update battery UI """
        if not data:
            return

        # Always update the bar label and icon
        percentage = data.get('percentage', 0)
        widget.set_label(f'{percentage}%')
        widget.text.set_width_chars(5)

        if data.get('ac_online'):
            widget.set_icon('')
        else:
            icons = ['', '', '', '', '']
            icon_index = min(
                int(percentage // (100 / len(icons))),
                len(icons) - 1)
            widget.set_icon(icons[icon_index])

        # Build popover on first update
        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))
            widget.last_device_keys = sorted(
                data.get('devices', {}).keys())

        if not hasattr(widget, 'popover_widgets'):
            return

        pw = widget.popover_widgets
        devices = data.get('devices', {})

        # Rebuild device rows if the set of batteries has changed
        current_keys = sorted(devices.keys())
        if current_keys != getattr(widget, 'last_device_keys', None):
            self.build_device_rows(widget, devices)
            widget.last_device_keys = current_keys

        # Update summary widgets
        pw['combined_pct'].set_text(f'{percentage}%')

        total_full = data.get('total_full', 0)
        if total_full > 0:
            segments = []
            for i, (name, info) in enumerate(sorted(devices.items())):
                now_key = (
                    'energy_now' if 'energy_now' in info
                    else 'charge_now')
                full_key = (
                    'energy_full' if 'energy_full' in info
                    else 'charge_full')
                seg_pct = (info[now_key] / total_full) * 100
                if seg_pct > 0:
                    dev_pct = round(
                        (info[now_key] / info[full_key]) * 100)
                    segments.append({
                        'percent': seg_pct,
                        'color': self.COLORS[i % len(self.COLORS)],
                        'tooltip': f"{name}: {dev_pct}%"
                    })
            pw['summary_bar'].update(segments)

        # Update per-device widgets in-place
        for device, info in devices.items():
            now_key = (
                'energy_now' if 'energy_now' in info else 'charge_now')
            full_key = (
                'energy_full' if 'energy_full' in info else 'charge_full')
            dev_pct = (
                round((info[now_key] / info[full_key]) * 100)
                if info.get(full_key, 0) > 0 else 0
            )
            key = f'dev_{device}'
            if f'{key}_pct' in pw:
                pw[f'{key}_pct'].set_text(f'{dev_pct}%')
            if f'{key}_level' in pw:
                pw[f'{key}_level'].set_value(dev_pct)


module_map = {
    'battery': Battery
}
