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
                    with open(f"{path}/{file}", 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        try:
                            value = int(content)
                        except ValueError:
                            value = content
                        battery_info[file] = value
                        
                        if file == 'energy_now' or file == 'charge_now':
                            now += battery_info[file]
                        elif file == 'energy_full' or file == 'charge_full':
                            full += battery_info[file]
                except FileNotFoundError:
                    pass
            
            if battery_info:
                # Calculate health
                design = battery_info.get(
                    'energy_full_design', battery_info.get('charge_full_design'))
                current_full = battery_info.get(
                    'energy_full', battery_info.get('charge_full'))
                
                if design and current_full:
                    battery_info['health'] = round((current_full / design) * 100)
                
                info[path.split('/')[-1]] = battery_info

        ac_online = 0
        try:
            with open(
                    '/sys/class/power_supply/AC/online', 'r',
                    encoding='utf-8') as file:
                ac_online = int(file.read().strip())
        except FileNotFoundError:
            try:
                with open(
                        '/sys/class/power_supply/ADP1/online', 'r',
                        encoding='utf-8') as file:
                    ac_online = int(file.read().strip())
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

    def build_popover_content(self, widget, data):
        """ Build popover for battery """
        widget.popover_widgets = {}
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Battery', style='heading'))

        # Summary section with PillBar
        summary_section = c.box('v', spacing=10)
        summary_section.append(c.label('Summary', style='title', ha='start'))
        
        summary_box = c.box('v', style='box')
        summary_row = c.box('v', spacing=5, style='inner-box')
        
        # Combined labels
        summary_labels = c.box('h')
        summary_labels.append(c.label('Combined', ha='start'))
        combined_pct_label = c.label(f'{data.get("percentage", 0)}%', ha='end', he=True)
        summary_labels.append(combined_pct_label)
        summary_row.append(summary_labels)
        widget.popover_widgets['combined_pct_label'] = combined_pct_label
        
        summary_bar = c.PillBar()
        summary_row.append(summary_bar)
        widget.popover_widgets['summary_bar'] = summary_bar
        
        summary_box.append(summary_row)
        summary_section.append(summary_box)
        main_box.append(summary_section)

        # Devices section
        outer_box = c.box('v', spacing=10)
        outer_box.append(c.label('Devices', style='title', ha='start'))
        battery_box = c.box('v', style='box')

        devices = sorted(data.get('devices', {}).items())
        for i, (device, info) in enumerate(devices):
            device_box = c.box('v', style='inner-box', spacing=5)
            
            # Header row
            header = c.box('h', spacing=10)
            
            # Indicator
            color = self.COLORS[i % len(self.COLORS)]
            ind = Gtk.Box()
            ind.set_size_request(6, 16)
            ind._provider = Gtk.CssProvider()
            rgb_str = f"rgb({int(color[0]*255)}, {int(color[1]*255)}, {int(color[2]*255)})"
            css = f"box {{ background-color: {rgb_str}; border-radius: 999px; }}"
            ind._provider.load_from_data(css.encode())
            ind.get_style_context().add_provider(
                ind._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            header.append(ind)

            header.append(c.label(device, style='title'))
            
            # Percentage
            now_key = 'energy_now' if 'energy_now' in info else 'charge_now'
            full_key = 'energy_full' if 'energy_full' in info else 'charge_full'
            percentage = round((
                info[now_key] / info[full_key]
            ) * 100) if info.get(full_key, 0) > 0 else 0
            header.append(c.label(f'{percentage}%', ha='end', he=True))
            
            device_box.append(header)
            
            # Level bar
            level = c.level(0, 100, percentage)
            level.set_hexpand(True)
            device_box.append(level)

            # Details grid-like layout
            details = c.box('h', spacing=20)
            
            # Capacity info
            if 'energy_full' in info:
                full_wh = info['energy_full'] / 1_000_000
                details.append(c.label(f'Full: {full_wh:.1f}Wh', style='dim-label'))
                if 'energy_full_design' in info:
                    max_wh = info['energy_full_design'] / 1_000_000
                    details.append(c.label(f'Max: {max_wh:.1f}Wh', style='dim-label'))
            elif 'charge_full' in info:
                full_ah = info['charge_full'] / 1_000_000
                details.append(c.label(f'Full: {full_ah:.1f}Ah', style='dim-label'))
                if 'charge_full_design' in info:
                    max_ah = info['charge_full_design'] / 1_000_000
                    details.append(c.label(f'Max: {max_ah:.1f}Ah', style='dim-label'))
                
            # Health info
            if 'health' in info:
                details.append(c.label(f'Health: {info["health"]}%', style='dim-label'))
                
            # Cycle count
            if info.get('cycle_count', 0) > 0:
                details.append(c.label(f'Cycles: {info["cycle_count"]}', style='dim-label'))
                
            device_box.append(details)
            battery_box.append(device_box)

            if i != len(devices) - 1:
                battery_box.append(c.sep('h'))
        
        outer_box.append(battery_box)
        main_box.append(outer_box)
        return main_box

    def create_widget(self, bar):
        """ Battery module widget """
        m = super().create_widget(bar)
        c.add_style(m, 'module-fixed')
        m.set_icon('')
        return m

    def update_ui(self, widget, data):
        """ Update battery UI """
        if not data:
            return
        
        percentage = data.get('percentage', 0)
        widget.set_label(f'{percentage}%')
        
        if data.get('ac_online'):
            widget.set_icon('')
        else:
            icons = ['', '', '', '', '']
            icon_index = int(percentage // (100 / len(icons)))
            icon_index = min(icon_index, len(icons) - 1)
            widget.set_icon(icons[icon_index])

        compare_data = data.copy()
        compare_data.pop('timestamp', None)
        if (widget.get_popover() and
                getattr(widget, 'last_popover_data', None) == compare_data):
            return
        widget.last_popover_data = compare_data

        if not widget.get_popover():
            widget.set_widget(self.build_popover_content(widget, data))

        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            if 'combined_pct_label' in pw:
                pw['combined_pct_label'].set_text(f'{percentage}%')
                
            if 'summary_bar' in pw:
                segments = []
                devices = data.get('devices', {})
                total_full = data.get('total_full', 0)
                
                if total_full > 0:
                    for i, (name, info) in enumerate(sorted(devices.items())):
                        now_key = 'energy_now' if 'energy_now' in info else 'charge_now'
                        full_key = 'energy_full' if 'energy_full' in info else 'charge_full'
                        
                        # Contribution to total bar
                        seg_percent = (info[now_key] / total_full) * 100
                        
                        if seg_percent > 0:
                            segments.append({
                                'percent': seg_percent,
                                'color': self.COLORS[i % len(self.COLORS)],
                                'tooltip': f"{name}: {round((info[now_key]/info[full_key])*100)}%"
                            })
                
                pw['summary_bar'].update(segments)


module_map = {
    'battery': Battery
}
