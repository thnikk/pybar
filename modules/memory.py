#!/usr/bin/python3 -u
"""
Description: Memory module with grouping and colorized process breakdown
Author: thnikk
"""
import common as c
import psutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class MemoryBar(c.PillBar):
    """ Custom drawing area for memory usage breakdown """

    def __init__(self, height=12, radius=6):
        super().__init__(height=height, radius=radius, wrap_width=40, hover_delay=0)
        self.set_has_tooltip(False)

    def update(self, percent, procs=None, proc_percent=None):
        procs = procs or []
        segments = []

        # 1. Add process segments
        for p in procs:
            if 'rgb' in p:
                segments.append({
                    'percent': p['percent'],
                    'color': p['rgb'],
                    'tooltip': p.get('cmd', p.get('name', ''))
                })

        # 2. Add remaining used memory
        top_percent = sum(p['percent'] for p in procs)

        if proc_percent is not None:
            # Calculate other processes (all processes - top processes)
            other_proc_percent = max(0, proc_percent - top_percent)

            # Calculate available space in the bar (total used - top processes)
            available_percent = max(0, percent - top_percent)

            # Determine how much of "Other Processes" fits
            visible_other = min(available_percent, other_proc_percent)

            # The rest is "Unaccounted"
            visible_unaccounted = max(0, available_percent - visible_other)

            if visible_other > 0:
                segments.append({
                    'percent': visible_other,
                    'color': (1.0, 1.0, 1.0),
                    'tooltip': "Other Processes"
                })

            if visible_unaccounted > 0:
                segments.append({
                    'percent': visible_unaccounted,
                    'color': (0.5, 0.5, 0.5),
                    'tooltip': "Unaccounted"
                })
        else:
            # Fallback for swap or if proc_percent is missing
            other_percent = max(0, percent - top_percent)
            if other_percent > 0:
                segments.append({
                    'percent': other_percent,
                    'color': (1.0, 1.0, 1.0),
                    'tooltip': "Other Processes"
                })

        super().update(segments)


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
        },
        'group_processes': {
            'type': 'boolean',
            'default': True,
            'label': 'Group Processes',
            'description': 'Group child process memory into parent processes'
        },
        'colorize_processes': {
            'type': 'boolean',
            'default': True,
            'label': 'Colorize Processes',
            'description': 'Show color breakdown for top processes'
        },
        'show_kill_button': {
            'type': 'boolean',
            'default': False,
            'label': 'Show Kill Button',
            'description': 'Show a button to terminate top processes'
        },
        'show_unaccounted': {
            'type': 'boolean',
            'default': True,
            'label': 'Show Unaccounted',
            'description': 'Show separate section for unaccounted memory'
        }
    }

    COLORS = [
        '#f28fad', '#f8bd96', '#fae3b0', '#abe9b3', '#89dceb',
        '#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#f2cdcd'
    ]

    def fetch_data(self):
        """ Get memory usage """
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()

        total = round(mem.total / (1024.0 ** 3), 1)
        used = round(mem.used / (1024.0 ** 3), 1)
        total_bytes = mem.total

        total_swap = round(swap.total / (1024.0 ** 3), 1)
        used_swap = round(swap.used / (1024.0 ** 3), 1)

        procs = []
        total_proc_rss = 0
        try:
            if self.config.get('group_processes', True):
                all_procs = {}
                for p in psutil.process_iter(
                        ['name', 'ppid', 'exe', 'cmdline', 'memory_info']):
                    try:
                        info = p.info
                        info['pid'] = p.pid
                        info['rss'] = (info['memory_info'].rss
                                       if info['memory_info'] else 0)
                        total_proc_rss += info['rss']
                        info['cmd'] = " ".join(info['cmdline'] or [])
                        all_procs[p.pid] = info
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                repr_cache = {}

                def get_repr(pid, depth=0):
                    if pid in repr_cache:
                        return repr_cache[pid]
                    if depth > 10:
                        return pid
                    curr = all_procs.get(pid)
                    if not curr:
                        return pid
                    ppid = curr['ppid']
                    parent = all_procs.get(ppid)
                    if not parent or ppid <= 1:
                        return pid

                    shared_exe = (curr['exe'] and parent['exe'] and
                                  curr['exe'] == parent['exe'])
                    name_in_cmd = (parent['name'].lower() in
                                   curr['cmd'].lower())
                    if shared_exe or name_in_cmd:
                        res = get_repr(ppid, depth + 1)
                        repr_cache[pid] = res
                        return res
                    repr_cache[pid] = pid
                    return pid

                aggregates = {}
                for pid in all_procs:
                    r_pid = get_repr(pid)
                    if r_pid not in aggregates:
                        root = all_procs[r_pid]
                        aggregates[r_pid] = {
                            'pid': r_pid,
                            'name': root['name'],
                            'cmd': root['cmd'] or root['name'],
                            'rss': 0
                        }
                    aggregates[r_pid]['rss'] += all_procs[pid]['rss']

                top_items = sorted(aggregates.values(),
                                   key=lambda x: x['rss'],
                                   reverse=True)[:10]
            else:
                top_items = []
                procs_list = list(psutil.process_iter(
                    ['name', 'cmdline', 'memory_info']))

                # Sum total RSS
                for p in procs_list:
                    try:
                        total_proc_rss += p.info['memory_info'].rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                        pass

                for p in sorted(
                    procs_list,
                    key=lambda p: p.info['memory_info'].rss,
                    reverse=True
                )[:10]:
                    try:
                        top_items.append({
                            'pid': p.pid,
                            'name': p.info['name'],
                            'cmd': " ".join(p.info['cmdline'] or []) or p.info['name'],
                            'rss': p.info['memory_info'].rss
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            for i, g in enumerate(top_items):
                mem_bytes = g['rss']
                mem_str = (f"{mem_bytes / (1024 ** 3):.1f} GB"
                           if mem_bytes > 1024 ** 3
                           else f"{mem_bytes / (1024 ** 2):.0f} MB")

                proc_data = {
                    "pid": g['pid'],
                    "name": g['name'],
                    "cmd": g['cmd'],
                    "mem": mem_str,
                    "percent": (mem_bytes / total_bytes) * 100
                }

                if self.config.get('colorize_processes', True):
                    color_hex = self.COLORS[i % len(self.COLORS)]
                    proc_data["color"] = color_hex
                    h = color_hex.lstrip('#')
                    proc_data["rgb"] = tuple(
                        int(h[j:j+2], 16)/255.0 for j in (0, 2, 4))

                procs.append(proc_data)

        except Exception as e:
            c.print_debug(f"Failed to fetch processes: {e}", self.name)

        return {
            "total": total,
            "used": used,
            "percent": mem.percent,
            "proc_percent": (total_proc_rss / total_bytes) * 100,
            "swap_total": total_swap,
            "swap_used": used_swap,
            "swap_percent": swap.percent,
            "text": f"{round(used)}",
            "procs": procs
        }

    def _on_kill_btn_clicked(self, btn):
        """ Handler for the kill button """
        pid = getattr(btn, '_target_pid', None)
        if not pid:
            return

        # Turn button grey and show spinner
        btn.set_sensitive(False)
        spinner = Gtk.Spinner()
        spinner.start()
        btn.set_child(spinner)

        def run_pkexec(p_id):
            import subprocess
            try:
                subprocess.run(
                    ['pkexec', 'kill', '-15', str(p_id)], check=True)
                c.print_debug(
                    f"Terminated process {p_id} with pkexec", self.name)
            except Exception as e:
                c.print_debug(f"pkexec kill failed: {e}", self.name)

        try:
            p = psutil.Process(pid)
            p.terminate()
            c.print_debug(f"Terminated process {pid}", self.name)
        except psutil.AccessDenied:
            import threading
            c.print_debug(
                f"Access denied for {pid}, prompting for root", self.name)
            threading.Thread(
                target=run_pkexec, args=(pid,), daemon=True).start()
        except Exception as e:
            c.print_debug(f"Failed to kill process {pid}: {e}", self.name)

    def _on_row_enter(self, controller, x, y, data):
        """ Show kill button on hover """
        row, revealer = data
        if self.config.get("show_kill_button", False):
            row.add_css_class("hovered")
            revealer.set_reveal_child(True)

    def _on_row_leave(self, controller, data):
        """ Hide kill button when not hovering """
        row, revealer = data
        row.remove_css_class("hovered")
        revealer.set_reveal_child(False)

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

        ram_bar = MemoryBar()
        ram_bar.update(data['percent'], data.get('procs', []))
        ram_row.append(ram_bar)
        widget.popover_widgets['ram_bar'] = ram_bar

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

        swap_bar = MemoryBar()
        swap_bar.update(data['swap_percent'])
        swap_row.append(swap_bar)
        widget.popover_widgets['swap_bar'] = swap_bar

        usage_box.append(swap_row)

        usage_section.append(usage_box)
        main_box.append(usage_section)

        # Processes section
        proc_section = c.box('v', spacing=10)
        proc_section.append(
            c.label('Top Processes', style='title', ha='start'))

        scroll = c.scroll(height=250, width=400, style='scroll')
        scroll.set_overflow(Gtk.Overflow.HIDDEN)
        proc_list = c.box('v', style='box')

        for i in range(10):
            row = c.box('h', style='p-row')

            # Info side
            info = c.box('h', spacing=10, style='inner-box')
            info.set_hexpand(True)

            # Indicator (Pill shape)
            ind = Gtk.Box()
            ind.set_size_request(6, 16)
            ind.set_visible(False)
            ind._provider = Gtk.CssProvider()
            ind.get_style_context().add_provider(
                ind._provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            info.append(ind)

            # Name
            name = c.label("name", ha='start', length=12)
            name.set_width_chars(12)
            name.set_max_width_chars(12)
            name.set_ellipsize(c.Pango.EllipsizeMode.END)
            name.set_xalign(0)
            info.append(name)

            # Command
            cmd = c.label("cmd", ha='start', he=True, length=20)
            cmd.set_xalign(0)
            c.set_hover_popover(cmd, lambda l_cmd=cmd: getattr(
                l_cmd, '_hover_text', ''), delay=500, wrap_width=40)
            info.append(cmd)

            # Memory
            mem = c.label("mem", ha='end')
            mem.get_style_context().add_class('dim-label')
            info.append(mem)

            row.append(info)

            # Action side (Swipe)
            rev = Gtk.Revealer()
            rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
            rev.set_transition_duration(250)
            rev.set_valign(Gtk.Align.FILL)

            action_box = c.box('h', style='p-action')
            action_box.set_valign(Gtk.Align.FILL)

            p_sep = c.sep('v', style='p-sep')
            p_sep.set_valign(Gtk.Align.FILL)
            action_box.append(p_sep)

            kill_btn = c.button('', style='kill-btn')
            kill_btn.set_valign(Gtk.Align.FILL)
            kill_btn.connect('clicked', self._on_kill_btn_clicked)
            action_box.append(kill_btn)

            rev.set_child(action_box)
            row.append(rev)

            # Hover controller
            motion = Gtk.EventControllerMotion.new()
            motion.connect("enter", self._on_row_enter, (row, rev))
            motion.connect("leave", self._on_row_leave, (row, rev))
            row.add_controller(motion)

            proc_list.append(row)
            if i < 9:
                proc_list.append(c.sep('h'))

            widget.popover_widgets[f'p_row_{i}'] = row
            widget.popover_widgets[f'p_info_{i}'] = info
            widget.popover_widgets[f'p_ind_{i}'] = ind
            widget.popover_widgets[f'p_name_{i}'] = name
            widget.popover_widgets[f'p_cmd_{i}'] = cmd
            widget.popover_widgets[f'p_mem_{i}'] = mem
            widget.popover_widgets[f'p_rev_{i}'] = rev
            widget.popover_widgets[f'p_kill_{i}'] = kill_btn

        scroll.set_child(proc_list)
        proc_section.append(scroll)
        main_box.append(proc_section)

        widget.popover_widgets.update({
            'ram_val': ram_val,
            'swap_val': swap_val
        })
        return main_box

    def create_widget(self, bar):
        # Use base class create_widget to benefit from weakref-protected subscription
        m = super().create_widget(bar)
        m.set_icon('')
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))

        compare_data = data.copy()
        compare_data.pop('timestamp', None)
        if (widget.get_popover() and
                getattr(widget, 'last_popover_data', None) == compare_data):
            return
        widget.last_popover_data = compare_data

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))

        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            pw['ram_val'].set_text(f"{data['used']}GB / {data['total']}GB")
            if 'ram_bar' in pw:
                show_unaccounted = self.config.get('show_unaccounted', False)
                proc_percent = data.get(
                    'proc_percent') if show_unaccounted else None
                pw['ram_bar'].update(
                    data['percent'], data.get('procs', []), proc_percent)

            pw['swap_val'].set_text(
                f"{data['swap_used']}GB / {data['total_swap'] if 'total_swap' in data else data['swap_total']}GB")
            if 'swap_bar' in pw:
                pw['swap_bar'].update(data['swap_percent'])

            procs = data.get('procs', [])
            show_kill = self.config.get('show_kill_button', False)

            for i in range(10):
                if i < len(procs):
                    p = procs[i]
                    pw[f'p_name_{i}'].set_text(p['name'])
                    pw[f'p_cmd_{i}'].set_text(p['cmd'])
                    pw[f'p_cmd_{i}']._hover_text = p['cmd']
                    pw[f'p_mem_{i}'].set_text(p['mem'])

                    ind = pw[f'p_ind_{i}']
                    if 'color' in p:
                        css = f"box {{ background-color: {p['color']}; border-radius: 999px; }}"
                        ind._provider.load_from_data(css.encode())
                        ind.set_visible(True)
                    else:
                        ind.set_visible(False)

                    kill_btn = pw[f'p_kill_{i}']
                    if show_kill:
                        kill_btn._target_pid = p['pid']
                        if not kill_btn.get_sensitive():
                            kill_btn.set_sensitive(True)
                            kill_btn.set_label('')

                    pw[f'p_row_{i}'].set_visible(True)
                else:
                    pw[f'p_row_{i}'].set_visible(False)


module_map = {'memory': Memory}
