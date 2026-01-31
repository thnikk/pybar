#!/usr/bin/python3 -u
"""
Description: Privacy module using PipeWire device detection
Author: thnikk
"""
import common as c
import os
import gi
import json
import subprocess
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Privacy(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 3,
            'label': 'Update Interval',
            'description': 'How often to check for active devices (seconds)',
            'min': 1,
            'max': 30
        }
    }

    DEFAULT_INTERVAL = 3
    EMPTY_IS_ERROR = False

    def get_friendly_name(self, device_path):
        """
        Attempts to find a friendlier name for a device node.
        Only used for /dev/video* devices.
        """
        if device_path.startswith('/dev/video'):
            index = device_path.replace('/dev/video', '')
            name_path = f'/sys/class/video4linux/video{index}/name'
            if os.path.exists(name_path):
                with open(name_path, 'r', encoding='utf-8') as f:
                    return f"{f.read().strip()} ({device_path})"
            return f"Webcam/Video Device ({device_path})"

        return device_path

    def get_webcam_processes_using_devices(self):
        """
        Scans /proc to find processes with open webcam devices.
        Only scans for /dev/video* devices.
        """
        device_usage = {}

        for pid in [p for p in os.listdir('/proc') if p.isdigit()]:
            fd_dir = os.path.join('/proc', pid, 'fd')
            try:
                for fd in os.listdir(fd_dir):
                    full_fd_path = os.path.join(fd_dir, fd)
                    try:
                        target_path = os.readlink(full_fd_path)

                        if target_path.startswith('/dev/video'):
                            with open(
                                f'/proc/{pid}/comm', 'r', encoding='utf-8'
                            ) as f:
                                comm = f.read().strip()

                            friendly_name = self.get_friendly_name(target_path)

                            if friendly_name not in device_usage:
                                device_usage[friendly_name] = {
                                    'path': target_path,
                                    'processes': [],
                                    'type': 'video'
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

    def get_process_name_from_pid(self, pid):
        """
        Get process name from PID via /proc
        """
        if not pid:
            return None
        try:
            with open(f'/proc/{pid}/comm', 'r', encoding='utf-8') as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            return None

    def get_pipewire_device_usage(self):
        """
        Detect active audio/video devices using PipeWire
        Returns dict with same format as get_processes_using_devices()
        """
        device_usage = {}
        try:
            result = subprocess.run(
                ['pw-dump', '-N'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return {}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return {}
        except Exception:
            return {}

        try:
            pw_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return {}

        # Build maps for quick lookup
        nodes_map = {}
        links_map = {}

        for obj in pw_data:
            obj_type = obj.get('type')
            obj_id = obj.get('id')
            info = obj.get('info', {})

            if obj_type == 'PipeWire:Interface:Node':
                nodes_map[obj_id] = {
                    'props': info.get('props', {}),
                    'state': info.get('state'),
                    'max_input_ports': info.get('max-input-ports'),
                    'n_input_ports': info.get('n-input-ports'),
                }
            elif obj_type == 'PipeWire:Interface:Link':
                link_info = info
                if link_info.get('state') == 'active':
                    links_map[obj_id] = {
                        'output_node': link_info.get('output-node-id'),
                        'input_node': link_info.get('input-node-id'),
                    }

        # Process active links to find device usage
        for link_id, link in links_map.items():
            source_id = link['output_node']
            target_id = link['input_node']

            source_node = nodes_map.get(source_id)
            target_node = nodes_map.get(target_id)

            if not source_node or not target_node:
                continue

            source_props = source_node['props']
            target_props = target_node['props']

            media_class = source_props.get('media.class', '')
            media_role = source_props.get('media.role', '')
            node_name = source_props.get('node.name', '')
            node_desc = source_props.get('node.description', '')
            factory = source_props.get('factory.name', '')

            # Determine device type
            device_type = None
            device_name = None

            if media_class == 'Audio/Source':
                device_type = 'audio'
                device_name = node_desc or node_name or 'Unknown Audio Source'
            elif media_class == 'Video/Source':
                if 'portal' in node_name.lower() or 'xdg-desktop' in node_name.lower():
                    device_type = 'screen_share'
                    device_name = f"Screen Share ({node_name})"
                # Webcam detection handled by /proc scanning

            if not device_type:
                continue

            # Get process info from target node
            app_name = target_props.get('application.name')
            app_pid = target_props.get('application.process.id')
            target_node_name = target_props.get('node.name')
            process_name = self.get_process_name_from_pid(app_pid)

            if app_name:
                proc_info = app_name
            elif process_name:
                proc_info = process_name
            elif target_node_name:
                # Fallback to target node name (e.g., for portal streams)
                proc_info = target_node_name
            else:
                continue

            if app_pid:
                proc_info = f"{proc_info} (PID: {app_pid})"

            path = f"pipewire:node:{source_id}"
            friendly_key = f"{device_name}"

            if friendly_key not in device_usage:
                device_usage[friendly_key] = {
                    'path': path,
                    'processes': [],
                    'type': device_type
                }

            if proc_info not in device_usage[friendly_key]['processes']:
                device_usage[friendly_key]['processes'].append(proc_info)

        return device_usage

    def fetch_data(self):
        """ Fetch privacy data using hybrid approach """
        device_usage = {}

        try:
            pipewire_result = self.get_pipewire_device_usage()
            # if pipewire_result:
            #     c.print_debug("[PRIVACY] PipeWire detection found devices")
            device_usage.update(pipewire_result)
        except Exception as e:
            c.print_debug(f"[PRIVACY] PipeWire error: {e}")

        try:
            webcam_result = self.get_webcam_processes_using_devices()
            # if webcam_result:
            #     c.print_debug("[PRIVACY] /proc webcam detection found devices")
            device_usage.update(webcam_result)
        except Exception as e:
            c.print_debug(f"[PRIVACY] /proc webcam error: {e}")

        return device_usage

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
            'Screen Sharing': {'icon': '', 'devices': {}},
        }

        for friendly_name, info in data.items():
            if not isinstance(info, dict):
                continue
            device_type = info.get('type')

            if device_type == 'audio':
                categories['Audio Recording']['devices'][friendly_name] = info
            elif device_type == 'video':
                categories['Video Recording']['devices'][friendly_name] = info
            elif device_type == 'screen_share':
                categories['Screen Sharing']['devices'][friendly_name] = info

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
        m.add_indicator_style('green')
        m.set_visible(False)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        """ Update privacy UI """
        if not data:
            widget.set_visible(False)
            widget.set_label('')
            # Hide and clear any existing popover when no data
            popover = widget.get_popover()
            if popover:
                popover.popdown()
            return

        has_audio = False
        has_video = False
        has_screen_share = False

        for device_info in data.values():
            if not isinstance(device_info, dict):
                continue
            device_type = device_info.get('type')

            if device_type == 'audio':
                has_audio = True
            elif device_type == 'video':
                has_video = True
            elif device_type == 'screen_share':
                has_screen_share = True

        icons = []
        if has_audio:
            icons.append('')
        if has_video:
            icons.append('')
        if has_screen_share:
            icons.append('')

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
