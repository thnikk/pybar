#!/usr/bin/python3 -u
"""
Description: CPU module showing total and per-core usage
Author: thnikk
"""
import common as c
import psutil
import gi
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
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.history = []
        self.per_cpu_history = []
        self.max_history = config.get('history_length', 60)

    def fetch_data(self):
        """Get CPU usage data"""
        total_percent = psutil.cpu_percent(interval=0.5)
        per_cpu = psutil.cpu_percent(interval=None, percpu=True)

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
            "cpu_count": len(per_cpu)
        }

    def build_popover(self, widget, data):
        """Build popover for CPU"""
        widget.popover_widgets = {}
        main_box = c.box('v', spacing=20, style='small-widget')
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

        colors = [
            (0.96, 0.56, 0.68),
            (0.97, 0.74, 0.59),
            (0.98, 0.89, 0.69),
            (0.67, 0.91, 0.70),
            (0.54, 0.86, 0.92),
            (0.54, 0.71, 0.98),
            (0.71, 0.73, 0.99),
            (0.80, 0.65, 0.97),
        ]

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
            width=400,
            smooth=False,
            min_config=0,
            max_config=100,
            colors=colors
        )
        # total_row.append(graph)
        usage_box.append(graph)
        widget.popover_widgets['graph'] = graph

        # usage_box.append(total_row)
        usage_section.append(usage_box)
        main_box.append(usage_section)

        cores_section = c.box('v', spacing=10)
        cores_section.append(
            c.label('Per Core', style='title', ha='start'))

        scroll = c.scroll(height=200, width=400, style='scroll')
        scroll.set_overflow(Gtk.Overflow.HIDDEN)
        cores_list = c.box('v', style='box')

        cpu_count = data.get('cpu_count', 0)
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

        scroll.set_child(cores_list)
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
        percentage = data.get('text', '')
        widget.set_label(f"{percentage}%")
        widget.text.set_width_chars(4)

        compare_data = data.copy()
        compare_data.pop('timestamp', None)
        if (widget.get_popover() and
                getattr(widget, 'last_popover_data', None) ==
                compare_data):
            return
        widget.last_popover_data = compare_data

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))

        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            pw['total_val'].set_text(f"{data['total']:.1f}%")

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


module_map = {'cpu': CPU}
