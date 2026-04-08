#!/usr/bin/python3 -u
"""
Description: NVTop module restored to original customized layout
Author: thnikk
"""
import json
import weakref
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class GpuVramBar(c.PillBar):
    """Custom drawing area for per-process VRAM usage breakdown."""

    def __init__(self, height=12, radius=6):
        super().__init__(
            height=height, radius=radius, wrap_width=40, hover_delay=0)
        self.set_has_tooltip(False)

    def update(self, mem_util, procs=None):
        """
        Build bar segments from process gpu_mem_usage percentages.
        mem_util is the total device memory utilisation (0-100 int).
        procs is a list of dicts that already carry 'gpu_mem_pct' and
        'rgb' keys (added by NVTop.build_proc_data).
        """
        procs = procs or []
        segments = []

        for p in procs:
            if 'rgb' not in p:
                continue
            segments.append({
                'percent': p['gpu_mem_pct'],
                'color': p['rgb'],
                'tooltip': p.get('cmdline', ''),
            })

        top_total = sum(p['gpu_mem_pct'] for p in procs if 'rgb' in p)
        other = max(0, mem_util - top_total)
        if other > 0:
            segments.append({
                'percent': other,
                'color': (1.0, 1.0, 1.0),
                'tooltip': 'Other Processes',
            })

        super().update(segments)


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

    # Colour palette for process indicators (matches memory module)
    COLORS = [
        '#f28fad', '#f8bd96', '#fae3b0', '#abe9b3', '#89dceb',
        '#89b4fa', '#b4befe', '#cba6f7', '#f5c2e7', '#f2cdcd'
    ]

    def fetch_data(self):
        """Get GPU data from nvtop."""
        try:
            res = run(
                ['nvtop', '-s'], capture_output=True,
                check=True).stdout.decode('utf-8')
            devices = json.loads(res)
            return {"devices": devices}
        except FileNotFoundError:
            return {"error": "command_not_found"}
        except Exception:
            return {}

    def safe_parse_percent(self, val):
        """Safely parse percentage string to int."""
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            return int(str(val).strip('%'))
        except (ValueError, TypeError):
            return 0

    def safe_parse_temp(self, val):
        """Safely parse temperature string to int."""
        if val is None:
            return 0
        if isinstance(val, int):
            return val
        try:
            return int(str(val).strip('C'))
        except (ValueError, TypeError):
            return 0

    def bytes_to_gb(self, bytes_val):
        """Convert bytes to GB as float."""
        if bytes_val is None:
            return 0.0
        try:
            return round(int(bytes_val) / (1024 ** 3), 1)
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0

    def build_proc_data(self, raw_procs):
        """
        Convert raw process dicts from nvtop into display-ready dicts,
        sorted descending by gpu_mem_usage.  Attaches colour info.
        Returns up to 10 entries.
        """
        parsed = []
        for p in (raw_procs or []):
            gpu_mem_pct = self.safe_parse_percent(
                p.get('gpu_mem_usage'))
            gpu_pct = self.safe_parse_percent(p.get('gpu_usage'))
            parsed.append({
                'pid': p.get('pid', ''),
                'cmdline': p.get('cmdline', ''),
                'gpu_pct': gpu_pct,
                'gpu_mem_pct': gpu_mem_pct,
            })

        parsed.sort(key=lambda x: x['gpu_mem_pct'], reverse=True)
        top = parsed[:10]

        for i, proc in enumerate(top):
            color_hex = self.COLORS[i % len(self.COLORS)]
            proc['color'] = color_hex
            h = color_hex.lstrip('#')
            proc['rgb'] = tuple(
                int(h[j:j + 2], 16) / 255.0 for j in (0, 2, 4))

        return top

    # ------------------------------------------------------------------
    # Kill-button / hover handlers (mirrors memory module)
    # ------------------------------------------------------------------

    def _on_kill_btn_clicked(self, btn):
        """Handler for the process kill button."""
        pid = getattr(btn, '_target_pid', None)
        if not pid:
            return

        btn.set_sensitive(False)
        spinner = Gtk.Spinner()
        spinner.start()
        btn.set_child(spinner)

        def run_pkexec(p_id):
            import subprocess
            try:
                subprocess.run(
                    ['pkexec', 'kill', '-15', str(p_id)],
                    check=True)
                c.print_debug(
                    f"Terminated process {p_id} with pkexec",
                    self.name)
            except Exception as e:
                c.print_debug(
                    f"pkexec kill failed: {e}", self.name)

        try:
            import psutil
            p = psutil.Process(int(pid))
            p.terminate()
            c.print_debug(f"Terminated process {pid}", self.name)
        except Exception:
            import threading
            threading.Thread(
                target=run_pkexec, args=(pid,), daemon=True).start()

    def _on_row_enter(self, controller, x, y, data):
        """Show kill button on hover."""
        row, revealer = data
        row.add_css_class('hovered')
        revealer.set_reveal_child(True)

    def _on_row_leave(self, controller, data):
        """Hide kill button when not hovering."""
        row, revealer = data
        row.remove_css_class('hovered')
        revealer.set_reveal_child(False)

    # ------------------------------------------------------------------
    # Popover builder
    # ------------------------------------------------------------------

    def build_popover(self, widget, data):
        """Build the complex original popover layout."""
        devices = data.get('devices', [])
        widget.popover_widgets = []

        main_box = c.box('v', spacing=20)
        main_box.append(c.label('GPU info', style="heading"))

        devices_box = c.box('v', spacing=20)

        for i in range(len(devices)):
            card_box = c.box('v', spacing=10)

            # Device title
            dev_name = devices[i].get('device_name', f'Device {i}')
            device_label = c.label(
                dev_name, style='title', ha='start', he=True)
            card_box.append(device_label)

            # Box for stats and graph
            stat_box = c.box('v')

            info_outer_box = c.box('v', spacing=0, style='gpu-info')
            inner_info_box = c.box('v', spacing=10, style='inner-box')

            device_widgets = {'device_label': device_label}

            inline_box = c.box('h', spacing=10)

            # Size groups for alignment
            icon_size_group = Gtk.SizeGroup.new(
                Gtk.SizeGroupMode.HORIZONTAL)
            levelbar_size_group = Gtk.SizeGroup.new(
                Gtk.SizeGroupMode.HORIZONTAL)
            side_size_group = Gtk.SizeGroup.new(
                Gtk.SizeGroupMode.HORIZONTAL)

            # Left side: GPU load and temp
            left_box = c.box('v', spacing=5)
            left_box.set_hexpand(True)
            side_size_group.add_widget(left_box)

            # GPU load row
            load_box = c.box('h', spacing=10)
            load_box.set_hexpand(True)
            load_icon = c.label('\uf629', style='gray')
            icon_size_group.add_widget(load_icon)
            load_box.append(load_icon)
            load_lvl = Gtk.LevelBar.new_for_interval(0, 100)
            load_lvl.set_min_value(0)
            load_lvl.set_max_value(100)
            load_lvl.set_hexpand(True)
            c.add_style(load_lvl, 'level-horizontal')
            levelbar_size_group.add_widget(load_lvl)
            load_val = self.safe_parse_percent(
                devices[i].get('gpu_util'))
            load_lvl.set_value(load_val)
            load_label = Gtk.Label.new(f'{load_val}%')
            load_label.set_xalign(1)
            load_label.set_width_chars(4)
            load_box.append(load_lvl)
            load_box.append(load_label)
            left_box.append(load_box)
            device_widgets['load'] = {
                'level': load_lvl, 'label': load_label}

            # Temp row
            temp_box = c.box('h', spacing=10)
            temp_box.set_hexpand(True)
            temp_icon = c.label('\uf2c9', style='gray')
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
            device_widgets['temp'] = {
                'level': temp_lvl, 'label': temp_label}

            inline_box.append(left_box)

            # Vertical separator
            inline_box.append(c.sep('v'))

            # Right side: Memory util and Memory GB
            right_box = c.box('v', spacing=5)
            right_box.set_hexpand(True)
            side_size_group.add_widget(right_box)

            # Memory util row
            mem_box = c.box('h', spacing=10)
            mem_box.set_hexpand(True)
            mem_icon = c.label('\uf538', style='gray')
            icon_size_group.add_widget(mem_icon)
            mem_box.append(mem_icon)
            mem_lvl = Gtk.LevelBar.new_for_interval(0, 100)
            mem_lvl.set_min_value(0)
            mem_lvl.set_max_value(100)
            mem_lvl.set_hexpand(True)
            c.add_style(mem_lvl, 'level-horizontal')
            levelbar_size_group.add_widget(mem_lvl)
            mem_val = self.safe_parse_percent(
                devices[i].get('mem_util'))
            mem_lvl.set_value(mem_val)
            mem_label = Gtk.Label.new(f'{mem_val}%')
            mem_label.set_xalign(1)
            mem_label.set_width_chars(4)
            mem_box.append(mem_lvl)
            mem_box.append(mem_label)
            right_box.append(mem_box)
            device_widgets['mem'] = {
                'level': mem_lvl, 'label': mem_label}

            # Memory GB row — only if data available
            if devices[i].get('mem_total') is not None:
                mem_gb_box = c.box('h', spacing=10)
                mem_gb_box.set_hexpand(True)
                mem_used = self.bytes_to_gb(devices[i].get('mem_used'))
                mem_total = round(
                    self.bytes_to_gb(devices[i].get('mem_total')))
                mem_gb_label = Gtk.Label.new(
                    f'{mem_used} / {mem_total}GB')
                mem_gb_label.set_hexpand(True)
                mem_gb_box.append(mem_gb_label)
                right_box.append(mem_gb_box)
                device_widgets['mem_gb'] = mem_gb_label

            inline_box.append(right_box)

            inner_info_box.append(inline_box)
            info_outer_box.append(inner_info_box)
            stat_box.append(info_outer_box)

            # Graph
            if hasattr(self, 'history'):
                h = self.history[i]
                graph_data = [h['load'], h['mem']]
                hover_labels = [
                    f"GPU: {lv}%, VRAM: {m}%"
                    for lv, m in zip(h['load'], h['mem'])]
                colors = [
                    (0.56, 0.63, 0.75), (0.63, 0.75, 0.56)]

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
                stat_box.append(graph_box)
                device_widgets['graph'] = graph

            card_box.append(stat_box)

            # ----------------------------------------------------------
            # Process list — only when nvtop provides process data
            # ----------------------------------------------------------
            raw_procs = devices[i].get('processes')
            if raw_procs is not None:
                procs = self.build_proc_data(raw_procs)
                mem_util = self.safe_parse_percent(
                    devices[i].get('mem_util'))

                proc_section = c.box('v', spacing=10)
                proc_section.append(
                    c.label('Processes', style='title', ha='start'))

                # VRAM breakdown bar
                vram_bar = GpuVramBar()
                vram_bar.update(mem_util, procs)
                proc_section.append(vram_bar)
                device_widgets['vram_bar'] = vram_bar

                proc_list = c.box('v')
                proc_widgets = {}

                for j in range(10):
                    row = c.box('h', style='p-row')

                    info = c.box('h', spacing=10, style='inner-box')
                    info.set_hexpand(True)

                    # Colour indicator pill
                    ind = Gtk.Box()
                    ind.set_size_request(6, 16)
                    ind.set_visible(False)
                    ind._provider = Gtk.CssProvider()
                    ind.get_style_context().add_provider(
                        ind._provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                    info.append(ind)

                    # Command label
                    cmd = c.label(
                        '', ha='start', he=True, length=24)
                    cmd.set_xalign(0)
                    info.append(cmd)

                    # GPU usage
                    gpu_val = c.label('', ha='end')
                    gpu_val.set_width_chars(5)
                    gpu_val.get_style_context().add_class('dim-label')
                    info.append(gpu_val)

                    # VRAM usage
                    mem_val = c.label('', ha='end')
                    mem_val.set_width_chars(5)
                    mem_val.get_style_context().add_class('dim-label')
                    info.append(mem_val)

                    row.append(info)

                    # Kill revealer
                    rev = Gtk.Revealer()
                    rev.set_transition_type(
                        Gtk.RevealerTransitionType.SLIDE_LEFT)
                    rev.set_transition_duration(250)
                    rev.set_valign(Gtk.Align.FILL)

                    action_box = c.box('h', style='p-action')
                    action_box.set_valign(Gtk.Align.FILL)

                    p_sep = c.sep('v', style='p-sep')
                    p_sep.set_valign(Gtk.Align.FILL)
                    action_box.append(p_sep)

                    kill_btn = c.button('\uf1f8', style='kill-btn')
                    kill_btn.set_valign(Gtk.Align.FILL)
                    kill_btn.connect(
                        'clicked', self._on_kill_btn_clicked)
                    action_box.append(kill_btn)
                    rev.set_child(action_box)
                    row.append(rev)

                    # Hover controller for kill revealer
                    motion = Gtk.EventControllerMotion.new()
                    motion.connect(
                        'enter', self._on_row_enter, (row, rev))
                    motion.connect(
                        'leave', self._on_row_leave, (row, rev))
                    row.add_controller(motion)

                    proc_list.append(row)
                    if j < 9:
                        proc_list.append(c.sep('h'))

                    proc_widgets[f'row_{j}'] = row
                    proc_widgets[f'ind_{j}'] = ind
                    proc_widgets[f'cmd_{j}'] = cmd
                    proc_widgets[f'gpu_{j}'] = gpu_val
                    proc_widgets[f'mem_{j}'] = mem_val
                    proc_widgets[f'rev_{j}'] = rev
                    proc_widgets[f'kill_{j}'] = kill_btn

                # Populate rows with initial data
                for j in range(10):
                    if j < len(procs):
                        p = procs[j]
                        proc_widgets[f'cmd_{j}'].set_text(
                            p.get('cmdline', ''))
                        proc_widgets[f'gpu_{j}'].set_text(
                            f"{p['gpu_pct']}%")
                        proc_widgets[f'mem_{j}'].set_text(
                            f"{p['gpu_mem_pct']}%")
                        ind = proc_widgets[f'ind_{j}']
                        if 'color' in p:
                            css = (
                                f"box {{ background-color: {p['color']};"
                                " border-radius: 999px; }")
                            ind._provider.load_from_data(css.encode())
                            ind.set_visible(True)
                        kill_btn = proc_widgets[f'kill_{j}']
                        kill_btn._target_pid = p.get('pid', '')
                        proc_widgets[f'row_{j}'].set_visible(True)
                    else:
                        proc_widgets[f'row_{j}'].set_visible(False)

                vsgb = c.VScrollGradientBox(
                    proc_list, height=130, width=400)
                c.add_style(vsgb, 'box')
                proc_section.append(vsgb)
                card_box.append(proc_section)
                device_widgets['proc_widgets'] = proc_widgets

            devices_box.append(card_box)
            widget.popover_widgets.append(device_widgets)

        main_box.append(devices_box)
        return main_box

    def create_widget(self, bar):
        """Create GPU module widget."""
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

        m.set_icon('\uf03e')
        m.box.set_spacing(5)
        m.set_visible(True)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        """Update GPU UI including bar and popover."""
        if not data:
            return

        if widget.box is None:
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

        # Initialise history if needed
        while len(self.history) < len(devices):
            self.history.append({'load': [0] * 100, 'mem': [0] * 100})

        # Dynamically manage level bars
        while len(widget.bar_gpu_levels) < len(devices):
            levels_box = c.box('h', spacing=4, style='levels-box')
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
            compare_data = data.copy()
            compare_data.pop('timestamp', None)

            if (widget.get_popover() and
                    getattr(widget, 'last_popover_data', None)
                    == compare_data):
                return

            widget.last_popover_data = compare_data

            # Determine whether a full rebuild is needed:
            # device count changed, or process-list presence changed.
            needs_rebuild = (
                not widget.get_popover()
                or len(widget.popover_widgets) != len(devices)
            )
            if not needs_rebuild:
                for i, dev in enumerate(devices):
                    dw = widget.popover_widgets[i]
                    has_proc_ui = 'proc_widgets' in dw
                    has_proc_data = dev.get('processes') is not None
                    if has_proc_ui != has_proc_data:
                        needs_rebuild = True
                        break

            if needs_rebuild:
                widget.set_widget(self.build_popover(widget, data))
                return

            # In-place update
            for i, device_widgets in enumerate(widget.popover_widgets):
                if i >= len(devices):
                    break
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

                if ('mem_gb' in device_widgets
                        and dev.get('mem_total') is not None):
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
                        f"GPU: {lv}%, VRAM: {m}%"
                        for lv, m in zip(h['load'], h['mem'])]
                    device_widgets['graph'].hover_labels = hover_labels
                    device_widgets['graph'].update_data(
                        [h['load'], h['mem']], None)

                # Update process list
                raw_procs = dev.get('processes')
                if raw_procs is not None and \
                        'proc_widgets' in device_widgets:
                    procs = self.build_proc_data(raw_procs)
                    mem_util = self.safe_parse_percent(
                        dev.get('mem_util'))

                    if 'vram_bar' in device_widgets:
                        device_widgets['vram_bar'].update(
                            mem_util, procs)

                    pw = device_widgets['proc_widgets']
                    for j in range(10):
                        if j < len(procs):
                            p = procs[j]
                            pw[f'cmd_{j}'].set_text(
                                p.get('cmdline', ''))
                            pw[f'gpu_{j}'].set_text(
                                f"{p['gpu_pct']}%")
                            pw[f'mem_{j}'].set_text(
                                f"{p['gpu_mem_pct']}%")
                            ind = pw[f'ind_{j}']
                            if 'color' in p:
                                css = (
                                    "box { background-color: "
                                    f"{p['color']};"
                                    " border-radius: 999px; }")
                                ind._provider.load_from_data(
                                    css.encode())
                                ind.set_visible(True)
                            kill_btn = pw[f'kill_{j}']
                            kill_btn._target_pid = p.get('pid', '')
                            if not kill_btn.get_sensitive():
                                kill_btn.set_sensitive(True)
                                kill_btn.set_label('')
                            pw[f'row_{j}'].set_visible(True)
                        else:
                            pw[f'row_{j}'].set_visible(False)

        except Exception as e:
            c.print_debug(f"NVTop popover update failed: {e}")


module_map = {
    'nvtop': NVTop
}
