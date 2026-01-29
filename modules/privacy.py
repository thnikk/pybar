#!/usr/bin/python3 -u
"""
Description: Privacy module using process-based device detection
Author: thnikk
"""
import common as c
import re
import os
import gi
import time
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Privacy(c.BaseModule):
    def get_friendly_name(self, device_path):
        """
        Attempts to find a friendlier name for a device node.
        """
        if device_path.startswith('/dev/video'):
            # For video, we can often find the name in sysfs
            index = device_path.replace('/dev/video', '')
            name_path = f'/sys/class/video4linux/video{index}/name'
            if os.path.exists(name_path):
                with open(name_path, 'r', encoding='utf-8') as f:
                    return f"{f.read().strip()} ({device_path})"
            return f"Webcam/Video Device ({device_path})"

        if '/dev/snd/pcm' in device_path:
            # Regex to extract Card and Device numbers from pcmC#D#c
            match = re.search(r'pcmC(\d+)D(\d+)c', device_path)
            if match:
                card, device = match.groups()
                # Look up the card name in /proc/asound/cards
                try:
                    with open('/proc/asound/cards', 'r', encoding='utf-8') as f:
                        cards_info = f.read()
                        # Standard ALSA format: " 0 [PCH]: HDA Intel PCH..."
                        card_match = re.search(
                            rf'^\s*{card}\s+\[(.*?)\s*\]',
                            cards_info, re.MULTILINE)
                        if card_match:
                            return (
                                    f"Audio Input: {card_match.group(1)} "
                                    f"(Card {card}, Dev {device})")
                except FileNotFoundError:
                    pass
                return f"Capture Device (Card {card}, Dev {device})"

        return device_path

    def get_processes_using_devices(self):
        """
        Scans /proc to find processes with open handles to specific devices.
        """
        device_usage = {}

        # Iterate over all named folders in /proc that are numeric (PIDs)
        for pid in [p for p in os.listdir('/proc') if p.isdigit()]:
            fd_dir = os.path.join('/proc', pid, 'fd')
            try:
                for fd in os.listdir(fd_dir):
                    full_fd_path = os.path.join(fd_dir, fd)
                    try:
                        target_path = os.readlink(full_fd_path)

                        is_video = target_path.startswith('/dev/video')
                        is_audio_input = (
                            target_path.startswith('/dev/snd/pcm')
                            and target_path.endswith('c'))

                        if is_video or is_audio_input:
                            with open(
                                f'/proc/{pid}/comm', 'r', encoding='utf-8'
                            ) as f:
                                comm = f.read().strip()

                            friendly_name = self.get_friendly_name(target_path)

                            if friendly_name not in device_usage:
                                device_usage[friendly_name] = {
                                    'path': target_path,
                                    'processes': []
                                }

                            process_info = f"{comm} (PID: {pid})"
                            if process_info not in \
                                    device_usage[friendly_name]['processes']:
                                device_usage[friendly_name][
                                    'processes'].append(process_info)
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                continue

        return device_usage

    def fetch_data(self):
        """ Fetch toggle data """
        try:
            return self.get_processes_using_devices()
        except Exception as e:
            c.print_debug(f"[PRIVACY] Fetch error: {e}")
            return {}

    def build_popover(self, data):
        """ Build privacy popover content """
        # Main container
        main_box = c.box('v', spacing=15, style='small-widget')

        # Header
        main_box.append(c.label('Privacy Monitor', style='heading'))

        # Group by category
        categories = {
            'Audio Recording': {'icon': '', 'devices': {}},
            'Video Recording': {'icon': '', 'devices': {}},
        }

        for friendly_name, info in data.items():
            if not isinstance(info, dict):
                continue
            path = info.get('path', '')
            if path.startswith('/dev/video'):
                categories['Video Recording']['devices'][friendly_name] = info
            else:
                categories['Audio Recording']['devices'][friendly_name] = info

        active_cats = {k: v for k, v in categories.items() if v['devices']}

        if not active_cats:
            main_box.append(
                c.label('No active devices detected', style='inner-box'))
            return main_box

        # Scrollable area for content
        scroll = c.scroll(height=350)
        content_box = c.box('v', spacing=15)

        for cat_name, cat_data in active_cats.items():
            cat_section = c.box('v', spacing=8)

            # Category header with icon
            cat_header = c.box('h', spacing=10)
            cat_header.append(c.label(cat_data['icon']))
            cat_header.append(c.label(cat_name, style='title'))
            cat_section.append(cat_header)

            # Device list
            dev_container = c.box('v', style='box')

            devices = cat_data['devices']
            for i, (name, info) in enumerate(devices.items()):
                dev_box = c.box('v', spacing=5, style='box-item')

                # Device name and path
                dev_box.append(c.label(name, ha='start'))
                dev_box.append(c.label(info.get('path', ''),
                               style='gray', ha='start'))

                # Processes
                for prog in sorted(info.get('processes', [])):
                    prog_row = c.box('h', spacing=8)
                    prog_row.append(c.label('●'))
                    prog_row.append(c.label(prog, ha='start'))
                    dev_box.append(prog_row)

                dev_container.append(dev_box)
                if i != len(devices) - 1:
                    dev_container.append(c.sep('h'))

            cat_section.append(dev_container)
            content_box.append(cat_section)

        scroll.set_child(content_box)
        main_box.append(scroll)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        c.add_style(m.indicator, 'green')
        m.set_visible(False)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        """ Update privacy UI """
        if not data:
            widget.set_visible(False)
            return

        has_audio = False
        has_video = False

        for device_info in data.values():
            if not isinstance(device_info, dict):
                continue
            path = device_info.get('path', '')
            if path.startswith('/dev/video'):
                has_video = True
            elif '/dev/snd/pcm' in path:
                has_audio = True

        icons = []
        if has_audio:
            icons.append('')
        if has_video:
            icons.append('')

        if icons:
            widget.set_label("  ".join(icons))
            widget.set_visible(True)

            # Real-time update without dismissal
            popover = widget.get_popover()
            if not popover:
                widget.set_widget(self.build_popover(data))
            else:
                # Update the existing popover content
                widget_box = popover.get_child()
                if widget_box:
                    # Clear existing content box and replace it
                    main_box = widget_box.get_first_child()
                    if main_box:
                        widget_box.remove(main_box)
                    widget_box.append(self.build_popover(data))
        else:
            widget.set_visible(False)


module_map = {
    'privacy': Privacy
}
