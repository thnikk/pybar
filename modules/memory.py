#!/usr/bin/python3 -u
"""
Description: Memory module refactored for unified state
Author: thnikk
"""
import common as c
import psutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Memory(c.BaseModule):
    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 5,
            'label': 'Update Interval',
            'description': 'How often to update memory stats (seconds)',
            'min': 1,
            'max': 60
        }
    }

    def fetch_data(self):
        """ Get memory usage """
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        total = round(mem.total / (1024.0 ** 3), 1)
        used = round(mem.used / (1024.0 ** 3), 1)

        total_swap = round(swap.total / (1024.0 ** 3), 1)
        used_swap = round(swap.used / (1024.0 ** 3), 1)

        return {
            "total": total,
            "used": used,
            "percent": mem.percent,
            "swap_total": total_swap,
            "swap_used": used_swap,
            "swap_percent": swap.percent,
            "text": f"{round(used)}"
        }

    def build_popover(self, widget, data):
        """ Build popover for memory """
        widget.popover_widgets = {}
        main_box = c.box('v', spacing=20, style='small-widget')
        main_box.append(c.label('Memory', style='heading'))

        usage_section = c.box('v', spacing=10)
        usage_section.append(c.label('Usage', style='title', ha='start'))

        usage_box = c.box('v', style='box')

        # RAM row
        ram_row = c.box('v', spacing=5, style='inner-box')
        ram_top = c.box('h')
        ram_top.append(c.label('RAM'))
        ram_val = c.label(
            f"{data['used']}GB / {data['total']}GB", ha='end', he=True)
        ram_top.append(ram_val)
        ram_row.append(ram_top)
        ram_level = Gtk.LevelBar.new_for_interval(0, 100)
        ram_level.set_min_value(0)
        ram_level.set_max_value(100)
        ram_level.set_value(data['percent'])
        ram_row.append(ram_level)
        usage_box.append(ram_row)

        usage_box.append(c.sep('h'))

        # Swap row
        swap_row = c.box('v', spacing=5, style='inner-box')
        swap_top = c.box('h')
        swap_top.append(c.label('Swap'))
        swap_val = c.label(
            f"{data['swap_used']}GB / {data['swap_total']}GB",
            ha='end', he=True)
        swap_top.append(swap_val)
        swap_row.append(swap_top)
        swap_level = Gtk.LevelBar.new_for_interval(0, 100)
        swap_level.set_min_value(0)
        swap_level.set_max_value(100)
        swap_level.set_value(data['swap_percent'])
        swap_row.append(swap_level)
        usage_box.append(swap_row)

        usage_section.append(usage_box)
        main_box.append(usage_section)

        widget.popover_widgets = {
            'ram_val': ram_val, 'ram_lvl': ram_level,
            'swap_val': swap_val, 'swap_lvl': swap_level
        }
        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(True)

        if not widget.get_active():
            widget.set_widget(self.build_popover(widget, data))
        else:
            if hasattr(widget, 'popover_widgets'):
                widget.popover_widgets['ram_val'].set_text(
                    f"{data['used']}GB / {data['total']}GB")
                widget.popover_widgets['ram_lvl'].set_value(data['percent'])
                widget.popover_widgets['swap_val'].set_text(
                    f"{data['swap_used']}GB / {data['swap_total']}GB")
                widget.popover_widgets['swap_lvl'].set_value(
                    data['swap_percent'])


module_map = {
    'memory': Memory
}
