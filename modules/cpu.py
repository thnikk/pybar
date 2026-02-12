#!/usr/bin/python3 -u
"""
Description: CPU module showing total and per-core usage
Author: thnikk
"""
import common as c
import psutil
import gi
import colorsys
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class CPU(c.BaseModule):
    DEFAULT_INTERVAL = 2
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 2,
            'label': 'Update Interval',
            'description': 'How often to update CPU stats (seconds)',
            'min': 1,
            'max': 60
        },
        'history_length': {
            'type': 'integer',
            'default': 60,
            'label': 'History Length',
            'description': 'Number of data points to keep in history',
            'min': 10,
            'max': 300
        },
        'compact_cores': {
            'type': 'boolean',
            'default': False,
            'label': 'Compact Cores',
            'description': 'Show cores in a compact grid',
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.history = []
        self.per_cpu_history = []
        self.max_history = config.get('history_length', 60)
        self.cpu_name = self._get_cpu_name()

    def _get_cpu_name(self):
        """Get CPU model name from /proc/cpuinfo"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if 'model name' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return "Unknown CPU"

    def _get_cpu_temp(self):
        """Try to get a meaningful CPU temperature"""
        if not hasattr(psutil, "sensors_temperatures"):
            return None

        temps = psutil.sensors_temperatures()
        # Common CPU sensor names
        for name in ['k10temp', 'coretemp', 'cpu_thermal', 'soc_thermal']:
            if name in temps:
                for sensor in temps[name]:
                    if sensor.label in ['Tctl', 'Package id 0', '']:
                        return sensor.current

        # Fallback: first available temperature
        for name, sensor_list in temps.items():
            if sensor_list:
                return sensor_list[0].current
        return None

    def get_colors(self, count):
        """Generate distinct colors for CPU cores"""
        colors = []
        for i in range(count):
            hue = i / count
            # Use fixed lightness and saturation for a consistent pastel look
            rgb = colorsys.hls_to_rgb(hue, 0.75, 0.6)
            colors.append(rgb)
        return colors

    def toggle_compact(self, _btn, widget):
        """Toggle compact cores mode"""
        compact = not self.config.get('compact_cores', False)
        self.config['compact_cores'] = compact

        # Update toggle button icon
        if hasattr(widget, 'compact_toggle_btn'):
            widget.compact_toggle_btn.set_label('' if compact else '')

        # Rebuild only the cores list
        data = c.state_manager.get(self.name)
        if data and hasattr(widget, 'cores_scroll'):
            # Clear old popover widget references for cores
            if hasattr(widget, 'popover_widgets'):
                keys_to_del = [k for k in widget.popover_widgets.keys()
                               if k.startswith('core_')]
                for k in keys_to_del:
                    del widget.popover_widgets[k]

            # Rebuild cores UI and swap child
            cores_ui = self.build_cores_ui(widget, data)
            widget.cores_scroll.set_child(cores_ui)

            # Update with current data
            self.update_ui(widget, data)

    def fetch_data(self):
        """Get CPU usage data"""
        total_percent = psutil.cpu_percent(interval=0.5)
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        freq = psutil.cpu_freq()
        temp = self._get_cpu_temp()

        self.history.append(total_percent)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        if not self.per_cpu_history:
            self.per_cpu_history = [[] for _ in range(len(per_cpu))]

        for i, cpu_percent in enumerate(per_cpu):
            if i < len(self.per_cpu_history):
                self.per_cpu_history[i].append(cpu_percent)
                if len(self.per_cpu_history[i]) > self.max_history:
                    self.per_cpu_history[i].pop(0)

        return {
            "text": f"{round(total_percent)}",
            "total": total_percent,
            "per_cpu": per_cpu,
            "history": self.history.copy(),
            "per_cpu_history": [h.copy() for h in self.per_cpu_history],
            "cpu_count": len(per_cpu),
            "freq": freq.current if freq else None,
            "temp": temp,
            "model": self.cpu_name
        }

    def build_cores_ui(self, widget, data):
        """Build the cores list or grid based on current mode"""
        compact = self.config.get('compact_cores', False)
        cpu_count = data.get('cpu_count', 0)
        colors = self.get_colors(cpu_count)

        if compact:
            # Compact grid mode using Gtk.Grid for perfect alignment
            grid = Gtk.Grid()
            grid.get_style_context().add_class('box')
            grid.set_column_homogeneous(False)
            grid.set_row_homogeneous(False)
            grid.set_vexpand(True)
            grid.set_hexpand(True)
            grid.set_valign(Gtk.Align.FILL)
            grid.set_halign(Gtk.Align.FILL)

            cols = 4
            num_rows = (cpu_count + cols - 1) // cols

            # Use size group to keep core columns equal width without making
            # separators wide
            size_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)

            # Add vertical separators between columns
            for c_idx in range(1, cols):
                v_sep = c.sep('v')
                v_sep.set_halign(Gtk.Align.CENTER)
                v_sep.set_vexpand(True)
                grid.attach(v_sep, c_idx * 2 - 1, 0, 1, num_rows * 2 - 1)

            # Add horizontal separators between rows
            for r_idx in range(1, num_rows):
                h_sep = c.sep('h')
                h_sep.set_valign(Gtk.Align.CENTER)
                h_sep.set_hexpand(True)
                grid.attach(h_sep, 0, r_idx * 2 - 1, cols * 2 - 1, 1)

            for i in range(cpu_count):
                row_idx = (i // cols) * 2
                col_idx = (i % cols) * 2

                core_item = c.box('h', spacing=8)
                core_item.set_margin_start(10)
                core_item.set_margin_end(10)
                core_item.set_margin_top(5)
                core_item.set_margin_bottom(5)
                core_item.set_vexpand(True)
                core_item.set_valign(Gtk.Align.FILL)
                size_group.add_widget(core_item)

                color_idx = i % len(colors)
                indicator = Gtk.Box()
                indicator.set_size_request(6, 14)
                indicator.set_valign(Gtk.Align.CENTER)
                css = (f"box {{ background-color: "
                       f"rgb({int(colors[color_idx][0]*255)}, "
                       f"{int(colors[color_idx][1]*255)}, "
                       f"{int(colors[color_idx][2]*255)}); "
                       f"border-radius: 999px; }}")
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                indicator.get_style_context().add_provider(
                    provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                core_item.append(indicator)

                name = c.label(f"{i}:", ha='start')
                core_item.append(name)

                val = c.label("0%", ha='end', he=True)
                val.set_width_chars(4)
                core_item.append(val)
                widget.popover_widgets[f'core_val_{i}'] = val

                grid.attach(core_item, col_idx, row_idx, 1, 1)

            return grid
        else:
            # Normal list mode
            cores_list = c.box('v', style='box')
            for i in range(cpu_count):
                row = c.box('h', style='inner-box')

                color_idx = i % len(colors)
                indicator = Gtk.Box()
                indicator.set_size_request(6, 16)
                css = (f"box {{ background-color: "
                       f"rgb({int(colors[color_idx][0]*255)}, "
                       f"{int(colors[color_idx][1]*255)}, "
                       f"{int(colors[color_idx][2]*255)}); "
                       f"border-radius: 999px; }}")
                provider = Gtk.CssProvider()
                provider.load_from_data(css.encode())
                indicator.get_style_context().add_provider(
                    provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                row.append(indicator)

                name = c.label(f"Core {i}", ha='start')
                name.set_margin_start(10)
                row.append(name)

                level_bar = c.level(min=0, max=100, value=0)
                level_bar.set_hexpand(True)
                level_bar.set_margin_start(10)
                level_bar.set_margin_end(10)
                row.append(level_bar)

                val = c.label("0%", ha='end')
                val.set_width_chars(5)
                row.append(val)

                cores_list.append(row)
                if i < cpu_count - 1:
                    cores_list.append(c.sep('h'))

                widget.popover_widgets[f'core_level_{i}'] = level_bar
                widget.popover_widgets[f'core_val_{i}'] = val
            return cores_list

    def build_popover(self, widget, data):
        """Build popover for CPU"""
        widget.popover_widgets = {}
        main_box = c.box('v', spacing=20)
        main_box.append(c.label('CPU', style='heading'))

        usage_section = c.box('v', spacing=10)
        usage_section.append(
            c.label('Usage', style='title', ha='start'))

        usage_box = c.box('v', style='box')

        total_row = c.box('v', spacing=5, style='inner-box')
        total_top = c.box('h')
        total_top.append(c.label('Total'))
        total_val = c.label(
            f"{data['total']:.1f}%", ha='end', he=True)
        total_top.append(total_val)
        total_row.append(total_top)

        # Info row above graph
        info_row = c.box('h', spacing=0)

        # Model section
        model_sec = c.box('h', spacing=10, style='box-item')
        model_icon = c.label('')
        model_sec.append(model_icon)

        model_lbl = c.label(
            data.get('model', 'Unknown CPU'), length=20)
        model_sec.append(model_lbl)

        # Temp section
        temp_sec = c.box('h', spacing=10, style='box-item')
        temp_icon = c.label('')
        temp_sec.append(temp_icon)

        temp_lbl = c.label("--°C", ha='center')
        temp_lbl.set_width_chars(6)
        temp_sec.append(temp_lbl)

        # Speed section
        speed_sec = c.box('h', spacing=10, style='box-item')
        speed_icon = c.label('')
        speed_sec.append(speed_icon)

        speed_lbl = c.label("-- MHz", ha='center')
        speed_lbl.set_width_chars(8)
        speed_sec.append(speed_lbl)

        # Build info row
        info_row.append(model_sec)

        vsep1 = c.sep('v')
        vsep1.set_vexpand(True)
        vsep1.set_valign(Gtk.Align.FILL)
        info_row.append(vsep1)

        info_row.append(temp_sec)

        vsep2 = c.sep('v')
        vsep2.set_vexpand(True)
        vsep2.set_valign(Gtk.Align.FILL)
        info_row.append(vsep2)

        info_row.append(speed_sec)

        usage_box.append(info_row)
        usage_box.append(c.sep('h'))
        widget.popover_widgets['model_lbl'] = model_lbl
        widget.popover_widgets['temp_lbl'] = temp_lbl
        widget.popover_widgets['speed_lbl'] = speed_lbl

        cpu_count = data.get('cpu_count', 0)
        colors = self.get_colors(cpu_count)

        multi_data = []
        if data.get('per_cpu_history'):
            for cpu_hist in data['per_cpu_history']:
                if cpu_hist:
                    multi_data.append(cpu_hist)

        graph = c.Graph(
            data=multi_data if multi_data else [[0]],
            state=round(data['total']),
            unit='%',
            height=180,
            width=300,
            smooth=False,
            min_config=0,
            max_config=100,
            colors=colors
        )
        usage_box.append(graph)
        widget.popover_widgets['graph'] = graph

        usage_section.append(usage_box)
        main_box.append(usage_section)

        cores_section = c.box('v', spacing=10)
        cores_header = c.box('h')
        cores_header.append(
            c.label('Per Core', style='title', ha='start', he=True))

        compact = self.config.get('compact_cores', False)
        toggle_btn = c.button('' if compact else '', style='minimal')
        toggle_btn.set_tooltip_text("Toggle compact mode")
        toggle_btn.connect('clicked', self.toggle_compact, widget)
        widget.compact_toggle_btn = toggle_btn
        cores_header.append(toggle_btn)
        cores_section.append(cores_header)

        cpu_count = data.get('cpu_count', 0)
        num_rows = (cpu_count + 3) // 4
        # Calculate height based on compact view: ~34px per row
        compact_height = max(100, num_rows * 34)
        compact_height = min(compact_height, 600)

        scroll = c.scroll(height=compact_height, width=400, style='scroll')
        scroll.set_overflow(Gtk.Overflow.HIDDEN)
        scroll.set_propagate_natural_height(True)
        widget.cores_scroll = scroll

        cores_ui = self.build_cores_ui(widget, data)
        scroll.set_child(cores_ui)

        cores_section.append(scroll)
        main_box.append(cores_section)

        widget.popover_widgets['total_val'] = total_val
        return main_box

    def create_widget(self, bar):
        m = super().create_widget(bar)
        m.set_icon('')
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        if not widget.text:
            return
        percentage = data.get('text', '')
        widget.set_label(f"{percentage}%")
        widget.text.set_width_chars(4)

        # Ensure popover exists so it can be opened
        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))

        if not widget.get_active():
            # Optimization: don't update internal widgets if not visible
            compare_data = data.copy()
            compare_data.pop('timestamp', None)
            compare_data.pop('history', None)
            compare_data.pop('per_cpu_history', None)
            widget.last_popover_data = compare_data
            return

        # Update in-place (always while active to keep graph moving)
        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            pw['total_val'].set_text(f"{data['total']:.1f}%")

            if 'model_lbl' in pw:
                pw['model_lbl'].set_text(data.get('model', 'Unknown CPU'))
            if 'temp_lbl' in pw:
                temp = data.get('temp')
                pw['temp_lbl'].set_text(
                    f"{temp:.1f}°C" if temp is not None else "--°C")
            if 'speed_lbl' in pw:
                freq = data.get('freq')
                if freq:
                    if freq > 1000:
                        pw['speed_lbl'].set_text(f"{freq/1000:.2f} GHz")
                    else:
                        pw['speed_lbl'].set_text(f"{freq:.0f} MHz")
                else:
                    pw['speed_lbl'].set_text("-- MHz")

            if 'graph' in pw:
                multi_data = []
                if data.get('per_cpu_history'):
                    for cpu_hist in data['per_cpu_history']:
                        if cpu_hist:
                            multi_data.append(cpu_hist)

                pw['graph'].update_data(
                    multi_data if multi_data else [[0]],
                    round(data['total']))

            per_cpu = data.get('per_cpu', [])
            for i, percent in enumerate(per_cpu):
                if f'core_level_{i}' in pw:
                    pw[f'core_level_{i}'].set_value(percent)
                if f'core_val_{i}' in pw:
                    pw[f'core_val_{i}'].set_text(f"{percent:.0f}%")

        # Update comparison data
        compare_data = data.copy()
        compare_data.pop('timestamp', None)
        compare_data.pop('history', None)
        compare_data.pop('per_cpu_history', None)
        widget.last_popover_data = compare_data


module_map = {'cpu': CPU}
