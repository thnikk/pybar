#!/usr/bin/python3 -u
"""
Description: NVTop module restored to original customized layout
Author: thnikk
"""
import json
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class NVTop(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 1,
            'label': 'Update Interval',
            'description': 'How often to update GPU stats (seconds)',
            'min': 1,
            'max': 10
        }
    }

    DEFAULT_INTERVAL = 1

    def fetch_data(self):
        """ Get GPU data from nvtop """
        try:
            res = run(['nvtop', '-s'], capture_output=True,
                      check=True).stdout.decode('utf-8')
            devices = json.loads(res)
            return {"devices": devices}
        except FileNotFoundError:
            return {"error": "command_not_found"}
        except Exception:
            return {}

    def safe_parse_percent(self, val):
        """ Safely parse percentage string to int """
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            return int(str(val).strip('%'))
        except (ValueError, TypeError):
            return 0

    def safe_parse_temp(self, val):
        """ Safely parse temperature string to int """
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            return int(str(val).strip('C'))
        except (ValueError, TypeError):
            return 0

    def bytes_to_gb(self, bytes_val):
        """ Convert bytes to GB as float """
        if bytes_val is None:
            return 0.0
        try:
            return round(int(bytes_val) / (1024 ** 3), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    def build_popover(self, widget, data):
        """ Build the complex original popover layout """
        devices = data.get('devices', [])
        widget.popover_widgets = []

        main_box = c.box('v', spacing=10)
        main_box.append(c.label('GPU info', style="heading"))

        devices_box = c.box('v', spacing=10)

        for i in range(len(devices)):
            card_box = c.box('v', spacing=0)

            # Device title
            dev_name = devices[i].get('device_name', f'Device {i}')
            device_label = c.label(dev_name, style='title', ha='start', he=True)
            card_box.append(device_label)

            info_outer_box = c.box('v', spacing=0, style='gpu-info')
            inner_info_box = c.box('v', spacing=10, style='inner-box')

            device_widgets = {'device_label': device_label}

            inline_box = c.box('h', spacing=10)

            # Size groups for alignment
            icon_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
            levelbar_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
            side_size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)

            # Left side: GPU load and temp
            left_box = c.box('v', spacing=5)
            left_box.set_hexpand(True)
            side_size_group.add_widget(left_box)

            # GPU load row
            load_box = c.box('h', spacing=10)
            load_box.set_hexpand(True)
            load_icon = c.label('', style='gray')
            icon_size_group.add_widget(load_icon)
            load_box.append(load_icon)
            load_lvl = Gtk.LevelBar.new_for_interval(0, 100)
            load_lvl.set_min_value(0)
            load_lvl.set_max_value(100)
            load_lvl.set_hexpand(True)
            c.add_style(load_lvl, 'level-horizontal')
            levelbar_size_group.add_widget(load_lvl)
            load_val = self.safe_parse_percent(devices[i].get('gpu_util'))
            load_lvl.set_value(load_val)
            load_label = Gtk.Label.new(f'{load_val}%')
            load_label.set_xalign(1)
            load_label.set_width_chars(4)
            load_box.append(load_lvl)
            load_box.append(load_label)
            left_box.append(load_box)
            device_widgets['load'] = {'level': load_lvl, 'label': load_label}

            # Temp row
            temp_box = c.box('h', spacing=10)
            temp_box.set_hexpand(True)
            temp_icon = c.label('', style='gray')
            icon_size_group.add_widget(temp_icon)
            temp_box.append(temp_icon)
            temp_lvl = Gtk.LevelBar.new_for_interval(0, 100)
            temp_lvl.set_min_value(0)
            temp_lvl.set_max_value(100)
            temp_lvl.set_hexpand(True)
            c.add_style(temp_lvl, 'level-horizontal')
            levelbar_size_group.add_widget(temp_lvl)
            temp_val = self.safe_parse_temp(devices[i].get('temp'))
            temp_lvl.set_value(temp_val)
            temp_label = Gtk.Label.new(f'{temp_val}°C')
            temp_label.set_xalign(1)
            temp_label.set_width_chars(4)
            temp_box.append(temp_lvl)
            temp_box.append(temp_label)
            left_box.append(temp_box)
            device_widgets['temp'] = {'level': temp_lvl, 'label': temp_label}

            inline_box.append(left_box)

            # Vertical separator
            inline_box.append(c.sep('v'))

            # Right side: Memory and Memory GB
            right_box = c.box('v', spacing=5)
            right_box.set_hexpand(True)
            side_size_group.add_widget(right_box)

            # Memory util row
            mem_box = c.box('h', spacing=10)
            mem_box.set_hexpand(True)
            mem_icon = c.label('', style='gray')
            icon_size_group.add_widget(mem_icon)
            mem_box.append(mem_icon)
            mem_lvl = Gtk.LevelBar.new_for_interval(0, 100)
            mem_lvl.set_min_value(0)
            mem_lvl.set_max_value(100)
            mem_lvl.set_hexpand(True)
            c.add_style(mem_lvl, 'level-horizontal')
            levelbar_size_group.add_widget(mem_lvl)
            mem_val = self.safe_parse_percent(devices[i].get('mem_util'))
            mem_lvl.set_value(mem_val)
            mem_label = Gtk.Label.new(f'{mem_val}%')
            mem_label.set_xalign(1)
            mem_label.set_width_chars(4)
            mem_box.append(mem_lvl)
            mem_box.append(mem_label)
            right_box.append(mem_box)
            device_widgets['mem'] = {'level': mem_lvl, 'label': mem_label}

            # Memory GB row - only if data available
            if devices[i].get('mem_total') is not None:
                mem_gb_box = c.box('h', spacing=10)
                mem_gb_box.set_hexpand(True)
                mem_gb_icon = c.label('', style='gray')
                icon_size_group.add_widget(mem_gb_icon)
                mem_gb_box.append(mem_gb_icon)
                mem_used = self.bytes_to_gb(devices[i].get('mem_used'))
                mem_total = round(
                        self.bytes_to_gb(devices[i].get('mem_total')))
                mem_gb_label = Gtk.Label.new(f'{mem_used} / {mem_total}GB')
                mem_gb_label.set_hexpand(True)
                mem_gb_box.append(mem_gb_label)
                right_box.append(mem_gb_box)
                device_widgets['mem_gb'] = mem_gb_label

            inline_box.append(right_box)

            inner_info_box.append(inline_box)
            info_outer_box.append(inner_info_box)
            card_box.append(info_outer_box)

            # Add graph
            if hasattr(self, 'history'):
                h = self.history[i]
                graph_data = [h['load'], h['mem']]
                hover_labels = [f"GPU: {l}%, VRAM: {m}%"
                                for l, m in zip(h['load'], h['mem'])]  # noqa
                colors = [(0.56, 0.63, 0.75), (0.63, 0.75, 0.56)]

                graph_box = c.box('v', style='gpu-graph')
                graph_box.set_overflow(Gtk.Overflow.HIDDEN)
                graph = c.Graph(
                    graph_data,
                    height=80,
                    min_config=0,
                    max_config=100,
                    colors=colors,
                    hover_labels=hover_labels,
                    smooth=False,
                )
                graph_box.append(graph)
                card_box.append(graph_box)
                device_widgets['graph'] = graph

            devices_box.append(card_box)
            widget.popover_widgets.append(device_widgets)

        main_box.append(devices_box)
        return main_box

    def create_widget(self, bar):
        """ Create GPU module widget """
        m = c.Module(text=False)
        m.set_position(bar.position)

        # Store UI elements for updating
        m.bar_gpu_levels = []  # List of (load_bar, mem_bar) pairs
        m.popover_widgets = []
        self.history = []  # Store history in class instance

        # Bar icon structure
        m.cards_box = c.box('h', spacing=15)
        m.cards_box.set_margin_start(5)
        m.box.append(m.cards_box)

        m.set_icon('')
        m.box.set_spacing(5)
        m.set_visible(True)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """ Update GPU UI including bar and popover """
        if not data:
            return

        if data.get('error') == 'command_not_found':
            widget.cards_box.set_visible(False)
            widget.set_icon('⚠')
            widget.set_label('Install nvtop')
            c.add_style(widget, 'red')
            widget.set_visible(True)
            return

        devices = data.get('devices', [])

        if devices:
            widget.set_visible(True)
        else:
            widget.set_visible(False)
            return

        # Initialize history if needed
        while len(self.history) < len(devices):
            self.history.append({'load': [0] * 100, 'mem': [0] * 100})

        # Dynamically manage level bars
        while len(widget.bar_gpu_levels) < len(devices):
            levels_box = c.box('h', spacing=4)
            l1 = Gtk.LevelBar.new_for_interval(0, 100)
            l1.set_min_value(0)
            l1.set_max_value(100)
            Gtk.Orientable.set_orientation(l1, Gtk.Orientation.VERTICAL)
            l1.set_inverted(True)

            l2 = Gtk.LevelBar.new_for_interval(0, 100)
            l2.set_min_value(0)
            l2.set_max_value(100)
            Gtk.Orientable.set_orientation(l2, Gtk.Orientation.VERTICAL)
            l2.set_inverted(True)

            levels_box.append(l1)
            levels_box.append(l2)
            widget.bar_gpu_levels.append((l1, l2))
            widget.cards_box.append(levels_box)

        # Hide excess level bars
        while len(widget.bar_gpu_levels) > len(devices):
            l1, l2 = widget.bar_gpu_levels.pop()
            l1.get_parent().set_visible(False)

        # Update bar icons and history
        for i, (l1, l2) in enumerate(widget.bar_gpu_levels):
            if i < len(devices):
                dev = devices[i]
                load = self.safe_parse_percent(dev.get('gpu_util'))
                mem = self.safe_parse_percent(dev.get('mem_util'))

                # Update history
                h = self.history[i]
                h['load'].append(load)
                h['mem'].append(mem)
                h['load'] = h['load'][-100:]
                h['mem'] = h['mem'][-100:]

                l1.set_value(load)
                l2.set_value(mem)
                l1.get_parent().set_visible(True)
                widget._update_spacing()
            else:
                l1.get_parent().set_visible(False)

        # Rebuild or update popover
        try:
            if not widget.get_active():
                widget.set_widget(self.build_popover(widget, data))
            else:
                for i, device_widgets in enumerate(widget.popover_widgets):
                    if i < len(devices):
                        dev = devices[i]
                        load = self.safe_parse_percent(dev.get('gpu_util'))
                        mem = self.safe_parse_percent(dev.get('mem_util'))

                        device_widgets['load']['level'].set_value(load)
                        device_widgets['load']['label'].set_text(f"{load}%")
                        device_widgets['mem']['level'].set_value(mem)
                        device_widgets['mem']['label'].set_text(f"{mem}%")

                        temp = self.safe_parse_temp(dev.get('temp'))
                        device_widgets['temp']['level'].set_value(temp)
                        device_widgets['temp']['level'].set_hexpand(True)
                        device_widgets['temp']['label'].set_text(f'{temp}°C')

                        if ('mem_gb' in device_widgets and
                                dev.get('mem_total') is not None):
                            mem_used = self.bytes_to_gb(dev.get('mem_used'))
                            mem_total = round(
                                    self.bytes_to_gb(dev.get('mem_total')))
                            device_widgets['mem_gb'].set_text(
                                f'{mem_used} / {mem_total}GB')

                        if 'device_label' in device_widgets:
                            device_widgets['device_label'].set_text(
                                dev.get('device_name', f'Device {i}'))

                        # Update graph
                        if 'graph' in device_widgets:
                            h = self.history[i]
                            hover_labels = [
                                f"GPU: {l}%, VRAM: {m}%"
                                for l, m in zip(h['load'], h['mem'])]
                            device_widgets['graph'].hover_labels = hover_labels
                            device_widgets['graph'].update_data(
                                [h['load'], h['mem']], None)
        except Exception as e:
            c.print_debug(f"NVTop popover update failed: {e}")


module_map = {
    'nvtop': NVTop
}
