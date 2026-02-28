#!/usr/bin/python3 -u
"""
Description: Debug module to open GTK Inspector
Author: thnikk
"""
import common as c
import os
import gi
import re
import weakref
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib, Pango  # noqa


class Debug(c.BaseModule):
    EMPTY_IS_ERROR = False
    DEFAULT_INTERVAL = 2
    LOG_RE = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) \[(\w+)\] (.*)$')

    SCHEMA = {
        'log_font_size': {
            'type': 'integer',
            'default': 13,
            'label': 'Log Font Size',
            'description': 'Font size for the log display'
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.last_mtime = 0
        self.last_lines = []
        self._pad_data([])
        self.last_lines_empty = True

    def _pad_data(self, lines):
        """ Parse lines and pad to exactly 10 """
        processed = []
        for line in lines:
            line = line.rstrip('\n')
            if not line:
                continue
            match = self.LOG_RE.match(line)
            if match:
                processed.append({
                    'level': match.group(2).upper(),
                    'text': match.group(3)
                })
            else:
                processed.append({'level': 'INFO', 'text': line})

        # Take last 10
        processed = processed[-10:]
        while len(processed) < 10:
            processed.append({'level': 'INFO', 'text': ""})

        self.last_lines = processed
        return processed

    def fetch_data(self):
        """ Read the last 10 lines of the log file efficiently """
        log_path = os.path.expanduser('~/.cache/pybar/pybar.log')
        try:
            if not os.path.exists(log_path):
                data = [{'level': 'INFO', 'text': "Log file not found."}]
                return {'lines': self._pad_data(data), 'is_empty': True}

            # Check modification time to avoid redundant reads
            mtime = os.path.getmtime(log_path)
            if mtime <= self.last_mtime:
                return {
                    'lines': self.last_lines,
                    'is_empty': self.last_lines_empty}
            self.last_mtime = mtime

            # Read only the end of the file
            with open(log_path, 'rb') as f:
                f.seek(0, os.SEEK_END)
                filesize = f.tell()
                if filesize == 0:
                    data = [{'level': 'INFO', 'text': "Empty log"}]
                    self.last_lines_empty = True
                    return {'lines': self._pad_data(data), 'is_empty': True}

                # Read last 4KB, usually enough for 10 lines
                buffer_size = min(filesize, 4096)
                f.seek(max(0, filesize - buffer_size))

                content = f.read().decode('utf-8', errors='replace')
                lines = content.splitlines()

                self.last_lines = self._pad_data(lines)
                self.last_lines_empty = False
                return {'lines': self.last_lines, 'is_empty': False}

        except Exception as e:
            c.print_debug(f"Error reading log: {e}", color='red')
            data = [{'level': 'ERROR', 'text': f"Error: {e}"}]
            self.last_lines_empty = True
            return {'lines': self._pad_data(data), 'is_empty': True}

    def open_inspector(self, _btn):
        Gtk.Window.set_interactive_debugging(True)

    def create_widget(self, bar):
        m = c.Module(icon=True, text=False)
        m.set_position(bar.position)
        m.set_icon(self.config.get('icon', ''))

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)

        # Debug Heading
        main_box.append(c.label("Debug", style="heading"))

        # Log title
        main_box.append(c.label("Log", style="title", ha='start'))

        # Log display in scrollbox
        # Height 0 allows it to grow to fit its content (exactly 10 labels)

        # Inner box for padding
        log_inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        log_inner.get_style_context().add_class('inner-box')

        # Container for the 10 lines
        lines_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        m.log_labels = []
        for _ in range(10):
            lbl = c.label("", ha='start', va='start')
            lbl.set_use_markup(True)
            lbl.set_wrap(False)
            lines_box.append(lbl)
            m.log_labels.append(lbl)

        log_inner.append(lines_box)
        log_scroll_wrapper = c.HScrollGradientBox(log_inner, max_width=400)
        c.add_style(log_scroll_wrapper, 'box')
        main_box.append(log_scroll_wrapper)

        # Convert vertical scroll to horizontal scroll
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)

        def on_scroll(_, _dx, dy):
            log_scroll_wrapper.scroll_by(dy * 50)
            return True

        scroll_controller.connect("scroll", on_scroll)
        log_scroll_wrapper._scroll.add_controller(scroll_controller)

        # Inspector button at the bottom
        inspector_btn = c.button(label=" Open Inspector", style="normal")
        inspector_btn.connect('clicked', self.open_inspector)
        main_box.append(inspector_btn)

        # Get font size from config
        font_size = self.config.get('log_font_size', 13)

        # Use weak references for the state change callback
        labels_ref = [weakref.ref(lbl) for lbl in m.log_labels]

        def on_state_changed(data):
            if isinstance(data, dict) and 'lines' in data:
                is_empty = data.get('is_empty', False)
                colors = {
                    'DEBUG': '#a3be8c',
                    'INFO': '#d8dee9',
                    'WARNING': '#ebcb8b',
                    'ERROR': '#bf616a'
                }

                for i, entry in enumerate(data['lines']):
                    if i < len(labels_ref):
                        label = labels_ref[i]()
                        if label:
                            level = entry.get('level', 'INFO')
                            text = entry.get('text', '')
                            color = colors.get(level, '#d8dee9')

                            # Basic escaping for pango
                            escaped = text.replace(
                                '&', '&amp;').replace(
                                '<', '&lt;').replace(
                                '>', '&gt;')

                            # Use non-breaking space for empty lines to
                            # preserve height
                            if not escaped.strip():
                                escaped = "&#160;"

                            markup = (f"<span font_family='monospace' "
                                      f"size='{font_size * 1024}'>")

                            if is_empty and escaped.strip() and escaped != "&#160;":
                                markup += f"<span foreground='#888'><i>{escaped}</i></span>"
                            else:
                                markup += f"<span foreground='{color}'>{escaped}</span>"

                            markup += "</span>"
                            label.set_markup(markup)

        sub_id = c.state_manager.subscribe(self.name, on_state_changed)
        m._subscriptions.append(sub_id)

        m.set_widget(main_box)
        return m


module_map = {
    'debug': Debug
}
