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
    DEFAULT_INTERVAL = 1

    def fetch_data(self):
        """ Get GPU data from nvtop """
        try:
            res = run(['nvtop', '-s'], capture_output=True,
                      check=True).stdout.decode('utf-8')
            devices = json.loads(res)
            return {"devices": devices}
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

    def build_popover(self, widget, data):
        """ Build the complex original popover layout """
        devices = data.get('devices', [])
        widget.popover_widgets = []

        main_box = c.box('v', spacing=10)
        main_box.append(c.label('GPU info', style="heading"))

        devices_box = c.box('v', spacing=10)

        for i in range(2):
            card_box = c.box('v', spacing=4)

            # Device title
            dev_name = devices[i].get('device_name', f'Device {i}') if i < len(
                devices) else f'Device {i}'
            device_label = c.label(dev_name, style='title', ha='start', he=True)
            card_box.append(device_label)

            info_outer_box = c.box('v', spacing=0, style='box')
            inner_info_box = c.box('v', spacing=10, style='inner-box')

            device_widgets = {'device_label': device_label}

            # Row for GPU and Memory utilization icons inline
            inline_box = c.box('h', spacing=10)
            size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)

            items = [('gpu_util', ''), ('mem_util', '')]
            for idx, (item_key, label_icon) in enumerate(items):
                line_box = c.box('h', spacing=10)
                line_box.set_hexpand(True)
                size_group.add_widget(line_box)
                line_box.append(c.label(label_icon, style='gray'))

                lvl = Gtk.LevelBar.new_for_interval(0, 100)
                lvl.set_min_value(0)
                lvl.set_max_value(100)
                lvl.set_hexpand(True)
                c.add_style(lvl, 'level-horizontal')

                val = self.safe_parse_percent(devices[i].get(
                    item_key)) if i < len(devices) else 0
                lvl.set_value(val)

                pct_label = Gtk.Label.new(f'{val}%')
                pct_label.set_xalign(1)
                pct_label.set_width_chars(4)

                line_box.append(lvl)
                line_box.append(pct_label)
                inline_box.append(line_box)

                if idx < len(items) - 1:
                    inline_box.append(c.sep('v'))

                short_key = 'load' if 'gpu' in item_key else 'mem'
                device_widgets[short_key] = {'level': lvl, 'label': pct_label}

            inner_info_box.append(inline_box)
            info_outer_box.append(inner_info_box)
            card_box.append(info_outer_box)

            # Add graph
            if hasattr(self, 'history') and i < len(self.history):
                h = self.history[i]
                graph_data = [h['load'], h['mem']]
                hover_labels = [f"GPU: {l}%, VRAM: {m}%"
                                for l, m in zip(h['load'], h['mem'])]  # noqa
                colors = [(0.56, 0.63, 0.75), (0.63, 0.75, 0.56)]

                graph_box = c.box('v', style='box')
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

            if i >= len(devices):
                card_box.set_visible(False)

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

        for _ in range(2):
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
            m.bar_gpu_levels.append((l1, l2))
            m.cards_box.append(levels_box)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        """ Update GPU UI including bar and popover """
        if not data:
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
