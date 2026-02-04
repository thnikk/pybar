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
    DEFAULT_INTERVAL = 5
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

        # Get top 10 processes
        procs = []
        try:
            for p in sorted(
                psutil.process_iter(['name', 'cmdline', 'memory_info']),
                key=lambda p: p.info['memory_info'].rss,
                reverse=True
            )[:10]:
                try:
                    mem_bytes = p.info['memory_info'].rss
                    if mem_bytes > 1024 ** 3:
                        mem_str = f"{mem_bytes / (1024 ** 3):.1f} GB"
                    else:
                        mem_str = f"{mem_bytes / (1024 ** 2):.0f} MB"

                    cmd = " ".join(p.info['cmdline'] or [])
                    if not cmd:
                        cmd = p.info['name']

                    procs.append({
                        "name": p.info['name'],
                        "cmd": cmd,
                        "mem": mem_str
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            c.print_debug(f"Failed to fetch processes: {e}", self.name)

        return {
            "total": total,
            "used": used,
            "percent": mem.percent,
            "swap_total": total_swap,
            "swap_used": used_swap,
            "swap_percent": swap.percent,
            "text": f"{round(used)}",
            "procs": procs
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

        # Processes section
        proc_section = c.box('v', spacing=10)
        proc_section.append(c.label('Top Processes', style='title', ha='start'))

        scroll = c.scroll(height=250, width=400, style='scroll')
        scroll.set_overflow(Gtk.Overflow.HIDDEN)
        proc_list = c.box('v', style='box')

        # Create 10 rows
        for i in range(10):
            row = c.box('h', spacing=10, style='inner-box')

            # Name
            name = c.label("name", ha='start', length=12)
            name.set_width_chars(12)  # Force fixed width
            name.set_max_width_chars(12)
            name.set_ellipsize(c.Pango.EllipsizeMode.END)
            name.set_xalign(0) # Left justify
            row.append(name)

            # Command (truncated)
            cmd = c.label("cmd", ha='start', he=True, length=20)
            cmd.set_xalign(0) # Left justify
            row.append(cmd)

            # Memory
            mem = c.label("mem", ha='end')
            mem.get_style_context().add_class('dim-label')
            mem.set_xalign(0) # Left justify
            row.append(mem)

            proc_list.append(row)
            
            if i < 9:
                proc_list.append(c.sep('h'))

            widget.popover_widgets[f'p_row_{i}'] = row
            widget.popover_widgets[f'p_name_{i}'] = name
            widget.popover_widgets[f'p_cmd_{i}'] = cmd
            widget.popover_widgets[f'p_mem_{i}'] = mem

        scroll.set_child(proc_list)
        proc_section.append(scroll)
        main_box.append(proc_section)

        widget.popover_widgets.update({
            'ram_val': ram_val, 'ram_lvl': ram_level,
            'swap_val': swap_val, 'swap_lvl': swap_level
        })
        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_icon('')

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(True)

        # Optimization: Don't update if data hasn't changed
        compare_data = data.copy()
        compare_data.pop('timestamp', None)

        if (widget.get_popover() and
                getattr(widget, 'last_popover_data', None) == compare_data):
            return

        widget.last_popover_data = compare_data

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))
        
        # Update values
        if hasattr(widget, 'popover_widgets'):
            # Usage
            widget.popover_widgets['ram_val'].set_text(
                f"{data['used']}GB / {data['total']}GB")
            widget.popover_widgets['ram_lvl'].set_value(data['percent'])
            widget.popover_widgets['swap_val'].set_text(
                f"{data['swap_used']}GB / {data['swap_total']}GB")
            widget.popover_widgets['swap_lvl'].set_value(
                data['swap_percent'])

            # Processes
            procs = data.get('procs', [])
            for i in range(10):
                if i < len(procs):
                    p = procs[i]
                    widget.popover_widgets[f'p_name_{i}'].set_text(p['name'])
                    widget.popover_widgets[f'p_cmd_{i}'].set_text(p['cmd'])
                    widget.popover_widgets[f'p_cmd_{i}'].set_tooltip_text(p['cmd'])
                    widget.popover_widgets[f'p_mem_{i}'].set_text(p['mem'])
                    widget.popover_widgets[f'p_row_{i}'].set_visible(True)
                else:
                    widget.popover_widgets[f'p_row_{i}'].set_visible(False)


module_map = {
    'memory': Memory
}
