#!/usr/bin/python3 -u
"""
Description: Disk module showing combined and per-partition usage
Author: thnikk
"""
import common as c
import psutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Disks(c.BaseModule):
    DEFAULT_INTERVAL = 3600
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 3600,
            'label': 'Update Interval',
            'description': 'How often to update disk stats (seconds)',
            'min': 5,
            'max': 86400
        },
        'ignore_mounts': {
            'type': 'list',
            'item_type': 'string',
            'default': ['/boot', '/boot/efi'],
            'label': 'Ignore Mounts',
            'description': 'List of mount points to ignore',
        },
        'show_subvolumes': {
            'type': 'boolean',
            'default': False,
            'label': 'Show Subvolumes',
            'description': 'Show all mount points for Btrfs devices',
        },
        'colorize_usage': {
            'type': 'boolean',
            'default': False,
            'label': 'Colorize Usage',
            'description': 'Color partition bars based on usage (green/red) '
            'instead of white',
        }
    }

    COLORS = [
        (0.56, 0.63, 0.75),  # Blue
        (0.64, 0.75, 0.55),  # Green
        (0.82, 0.53, 0.58),  # Pink/Red
        (0.92, 0.8, 0.55),  # Yellow
        (0.7, 0.56, 0.68),  # Purple
        (0.55, 0.75, 0.74),  # Cyan
        (0.81, 0.62, 0.53),  # Orange
        (0.68, 0.7, 0.8),   # Lavender
    ]

    def __init__(self, name, config):
        super().__init__(name, config)
        self.ignore_mounts = config.get(
            'ignore_mounts', ['/boot', '/boot/efi'])
        self.device_colors = {}

    def format_size(self, bytes):
        """Format bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} PB"

    def fetch_data(self):
        """Get disk usage data"""
        partitions = []
        total_used = 0
        total_size = 0
        show_subvolumes = self.config.get('show_subvolumes', False)

        # Group by physical device
        device_usage = {}  # device -> {'used': int, 'total': int}

        raw_parts = psutil.disk_partitions(all=False)

        # Sort so btrfs subvolumes are likely grouped if we sort by device
        # Also sort by mountpoint depth so / comes before /home
        raw_parts.sort(key=lambda x: (
            x.device, len(x.mountpoint), x.mountpoint))

        seen_list_devices = set()

        for part in raw_parts:
            if part.mountpoint in self.ignore_mounts:
                continue

            if part.device.startswith('/dev/loop') or 'loop' in part.opts:
                continue

            if part.fstype in [
                    'tmpfs', 'devtmpfs', 'devpts',
                    'sysfs', 'proc', 'configfs']:
                continue

            try:
                usage = psutil.disk_usage(part.mountpoint)

                # Assign color to device if not already assigned
                if part.device not in self.device_colors:
                    color_idx = len(self.device_colors) % len(self.COLORS)
                    self.device_colors[part.device] = self.COLORS[color_idx]

                # For combined stats and initial device tracking
                is_new_device = part.device not in device_usage
                if is_new_device:
                    device_usage[part.device] = {
                        'used': usage.used,
                        'total': usage.total,
                        'color': self.device_colors[part.device]
                    }
                    total_used += usage.used
                    total_size += usage.total

                # Filter for the partition list
                if not show_subvolumes and part.device in seen_list_devices:
                    continue

                seen_list_devices.add(part.device)

                partitions.append({
                    'device': part.device,
                    'mount': part.mountpoint,
                    'fstype': part.fstype,
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent,
                    'color': self.device_colors[part.device]
                })
            except (PermissionError, FileNotFoundError):
                continue

        # Calculate segments for combined bar
        segments = []
        if total_size > 0:
            for dev, usage in device_usage.items():
                percent = (usage['used'] / total_size) * 100
                if percent > 0.1:  # Only show visible segments
                    segments.append({
                        'percent': percent,
                        'color': usage['color'],
                        'tooltip': f"{dev}: {self.format_size(usage['used'])}"
                    })

        return {
            "total_size": total_size,
            "total_used": total_used,
            "total_percent": (total_used / total_size * 100)
            if total_size > 0 else 0,
            "partitions": partitions,
            "segments": segments
        }

    def build_popover(self, widget, data):
        """Build popover for Disks"""
        widget.popover_widgets = {}
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Disks', style='heading'))

        # Combined usage section
        combined_section = c.box('v', spacing=10)
        combined_section.append(
            c.label('Combined Storage', style='title', ha='start'))

        combined_box = c.box('v', style='box', spacing=0)

        info_row = c.box('h', style='inner-box')
        used_str = self.format_size(data['total_used'])
        total_str = self.format_size(data['total_size'])
        combined_info_label = c.label(f"Used: {used_str} / {total_str}")
        info_row.append(combined_info_label)
        percent_label = c.label(
            f"{data['total_percent']:.1f}%", ha='end', he=True)
        info_row.append(percent_label)
        combined_box.append(info_row)

        pill_container = c.box('v')
        pill_container.set_margin_start(10)
        pill_container.set_margin_end(10)
        pill_container.set_margin_bottom(10)
        pill_container.set_margin_top(0)

        pill = c.PillBar(height=12)
        pill.set_has_tooltip(False)  # Use HoverPopover only
        pill.update(data['segments'])
        pill_container.append(pill)
        combined_box.append(pill_container)

        widget.popover_widgets['combined_pill'] = pill
        widget.popover_widgets['combined_percent'] = percent_label
        widget.popover_widgets['combined_info'] = combined_info_label

        combined_section.append(combined_box)
        main_box.append(combined_section)

        # Partitions section
        part_section = c.box('v', spacing=10)
        part_section.append(c.label('Partitions', style='title', ha='start'))

        part_list = c.box('v', style='box')

        for i, part in enumerate(data['partitions']):
            row = c.box('h', spacing=10, style='inner-box')

            # Colored indicator for the disk - spans height of the content row
            indicator = Gtk.Box()
            indicator.set_size_request(6, -1)
            indicator.set_vexpand(True)
            indicator.set_valign(Gtk.Align.FILL)
            css = (f"box {{ background-color: "
                   f"rgb({int(part['color'][0]*255)}, "
                   f"{int(part['color'][1]*255)}, "
                   f"{int(part['color'][2]*255)}); "
                   f"border-radius: 999px; }}")
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode())
            indicator.get_style_context().add_provider(
                provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            row.append(indicator)

            # Content container (Label + Pillbar)
            content_box = c.box('v', spacing=5)
            content_box.set_hexpand(True)

            title_row = c.box('h', spacing=8)
            # Shorten device path if it's long
            dev_name = part['device'].split('/')[-1]
            title_row.append(
                c.label(f"{dev_name} ({part['mount']})", ha='start'))

            p_percent_label = c.label(
                f"{part['percent']:.1f}%", ha='end', he=True)
            title_row.append(p_percent_label)
            content_box.append(title_row)

            p_pill = c.PillBar(height=12)
            p_pill.set_has_tooltip(False)

            # Usage-based colors or white
            if self.config.get('colorize_usage', False):
                usage_color = (0.64, 0.75, 0.55) if part['percent'] < 80 else (
                    0.75, 0.38, 0.42)
            else:
                usage_color = (1.0, 1.0, 1.0)

            p_segments = [{
                'percent': part['percent'],
                'color': usage_color,
                'tooltip': f"Used: {self.format_size(part['used'])} / "
                f"{self.format_size(part['total'])}"
            }]
            p_pill.update(p_segments)
            content_box.append(p_pill)

            row.append(content_box)
            part_list.append(row)
            if i < len(data['partitions']) - 1:
                part_list.append(c.sep('h'))

            widget.popover_widgets[f'part_pill_{i}'] = p_pill
            widget.popover_widgets[f'part_percent_{i}'] = p_percent_label

        scroll = c.scroll(height=max(
            100, min(400, len(data['partitions']) * 60)), width=400)
        scroll.set_child(part_list)
        part_section.append(scroll)
        main_box.append(part_section)

        return main_box

    def create_widget(self, bar):
        m = super().create_widget(bar)
        m.set_icon('')
        m.set_label('')
        # Disable regular tooltips
        m.set_has_tooltip(False)
        return m

    def update_ui(self, widget, data):
        if not data:
            return

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))

        if not widget.get_active():
            return

        # Colors
        COLOR_GREEN = (0.64, 0.75, 0.55)
        COLOR_RED = (0.75, 0.38, 0.42)

        # Update in-place
        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            if 'combined_pill' in pw:
                pw['combined_pill'].update(data['segments'])
            if 'combined_percent' in pw:
                pw['combined_percent'].set_text(
                    f"{data['total_percent']:.1f}%")
            if 'combined_info' in pw:
                used_str = self.format_size(data['total_used'])
                total_str = self.format_size(data['total_size'])
                pw['combined_info'].set_text(f"Used: {used_str} / {total_str}")

            colorize = self.config.get('colorize_usage', False)
            for i, part in enumerate(data['partitions']):
                if f'part_pill_{i}' in pw:
                    if colorize:
                        usage_color = COLOR_GREEN if part['percent'] < 80 \
                            else COLOR_RED
                    else:
                        usage_color = (1.0, 1.0, 1.0)
                    pw[f'part_pill_{i}'].update([{
                        'percent': part['percent'],
                        'color': usage_color,
                        'tooltip': f"Used: {self.format_size(part['used'])} / "
                        f"{self.format_size(part['total'])}"
                    }])
                if f'part_percent_{i}' in pw:
                    pw[f'part_percent_{i}'].set_text(f"{part['percent']:.1f}%")


module_map = {'disks': Disks}
