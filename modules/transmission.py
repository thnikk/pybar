#!/usr/bin/python3 -u
"""
Description: Transmission module refactored for unified state
Author: thnikk
"""
import weakref
import common as c
import gi
import shutil
import subprocess
import threading
import time
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

try:
    from transmission_rpc import Client
except ImportError:
    Client = None


class Transmission(c.BaseModule):
    SCHEMA = {
        'host': {
            'type': 'string',
            'default': 'localhost',
            'label': 'Host',
            'description': 'Transmission RPC host'
        },
        'port': {
            'type': 'integer',
            'default': 9091,
            'label': 'Port',
            'description': 'Transmission RPC port',
            'min': 1,
            'max': 65535
        },
        'interval': {
            'type': 'integer',
            'default': 30,
            'label': 'Update Interval',
            'description': 'How often to check torrent status (seconds)',
            'min': 10,
            'max': 300
        },
        'hide_empty': {
            'type': 'boolean',
            'default': True,
            'label': 'Hide When Empty',
            'description': 'Hide the module when no torrents are active'
        }
    }

    def fetch_data(self):
        if not Client:
            return {}

        try:
            client = Client(
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", 9091)
            )
            torrents = client.get_torrents()

            down_list = []
            up_list = []
            for t in torrents:
                item = {
                    'id': t.id,
                    'name': t.name,
                    'progress': t.progress,
                    'ratio': t.ratio,
                    'status': t.status
                }
                if t.status == 'downloading':
                    down_list.append(item)
                elif t.status == 'seeding':
                    up_list.append(item)

            text_parts = []
            if down_list:
                text_parts.append(str(len(down_list)))
            if up_list:
                text_parts.append(str(len(up_list)))

            return {
                "icon": "",
                "text": "  ".join(text_parts),
                "downloading": down_list,
                "uploading": up_list
            }
        except Exception:
            return {}

    def open_transmission(self, _button):
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 9091)

        if shutil.which("transmission-remote-gtk"):
            subprocess.Popen(["transmission-remote-gtk"])
        else:
            url = f"http://{host}:{port}/transmission/web/"
            subprocess.Popen(["xdg-open", url])

    def _on_torrent_action_clicked(self, btn):
        if not Client:
            return
        t_id = getattr(btn, '_torrent_id', None)
        action = getattr(btn, '_action', 'stop')
        row = getattr(btn, '_row', None)
        ibox = getattr(btn, '_ibox', None)
        sec = getattr(btn, '_sec', None)

        if t_id is None:
            return

        # Immediate feedback: hide the row
        if row:
            row.set_visible(False)

        # Update state manager immediately with estimated data
        data = c.state_manager.get(self.name)
        if data and action == 'stop':
            new_data = data.copy()
            # Remove the torrent from the lists
            down_list = [t for t in data.get(
                'downloading', []) if t['id'] != t_id]
            up_list = [t for t in data.get('uploading', []) if t['id'] != t_id]

            new_data['downloading'] = down_list
            new_data['uploading'] = up_list

            # Rebuild the text string
            parts = []
            if down_list:
                parts.append(str(len(down_list)))
            if up_list:
                parts.append(str(len(up_list)))
            new_data['text'] = "  ".join(parts)

            # This triggers update_ui on all bar widgets
            c.state_manager.update(self.name, new_data)

        # If it was the last visible row in the section, hide the section too
        if ibox and sec:
            has_visible = False
            child = ibox.get_first_child()
            while child:
                if child.get_visible() and \
                        not isinstance(child, Gtk.Separator):
                    has_visible = True
                    break
                child = child.get_next_sibling()

            if not has_visible:
                sec.set_visible(False)

        def run_action():
            try:
                client = Client(
                    host=self.config.get("host", "localhost"),
                    port=self.config.get("port", 9091)
                )
                if action == 'stop':
                    client.stop_torrent(t_id)
                elif action == 'start':
                    client.start_torrent(t_id)

                # Fetch fresh data and update state manager
                time.sleep(0.3)  # Give Transmission a moment to sync state
                new_data = self.fetch_data()
                c.state_manager.update(self.name, new_data)
            except Exception as e:
                c.print_debug(f"Transmission action failed: {e}", self.name)

        threading.Thread(target=run_action, daemon=True).start()

    def _on_row_enter(self, controller, x, y, data):
        row, revealer = data
        row.add_css_class("hovered")
        revealer.set_reveal_child(True)

    def _on_row_leave(self, controller, data):
        row, revealer = data
        row.remove_css_class("hovered")
        revealer.set_reveal_child(False)

    def build_popover(self, data):
        box = c.box('v', spacing=20, style='small-widget')
        box.append(c.label('Transmission', style='heading'))

        sections = [
            ("Downloading", data.get('downloading', [])),
            ("Seeding", data.get('uploading', []))
        ]
        for title, items in sections:
            if not items:
                continue
            sec = c.box('v', spacing=10)
            sec.append(c.label(title, style='title', ha='start'))
            ibox = c.box('v')
            ibox.set_overflow(Gtk.Overflow.HIDDEN)
            ibox.set_size_request(350, -1)
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue

                item_row = c.box('h', style='p-row')
                item_row.set_overflow(Gtk.Overflow.HIDDEN)
                item_row.set_size_request(350, -1)

                # Info side
                info = c.box('v', spacing=5, style='inner-box')
                info.set_hexpand(True)
                info.set_size_request(300, -1)

                # Top row: Name
                name_label = c.label(
                    item['name'], ha='start', he=True, length=28)
                name_label.set_xalign(0)
                name_label.set_width_chars(28)
                info.append(name_label)

                # Bottom row: Progress bar and Ratio
                bottom = c.box('h', spacing=10)
                prog = c.level(0, 100, item['progress'])
                prog.set_hexpand(True)
                prog.set_size_request(10, -1)
                bottom.append(prog)
                bottom.append(c.label(
                    f"{item['ratio']:.2f}", style='small'))
                info.append(bottom)

                item_row.append(info)

                # Action side (Swipe)
                rev = Gtk.Revealer()
                rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
                rev.set_transition_duration(250)
                rev.set_valign(Gtk.Align.FILL)
                rev.set_hexpand(False)

                action_box = c.box('h', style='p-action')
                action_box.set_valign(Gtk.Align.FILL)
                action_box.set_hexpand(False)

                p_sep = c.sep('v', style='p-sep')
                p_sep.set_valign(Gtk.Align.FILL)
                action_box.append(p_sep)

                # Pause/Play button
                is_active = item['status'] in ['downloading', 'seeding']
                action_icon = '' if is_active else ''
                action_type = 'stop' if is_active else 'start'

                btn = c.button(action_icon, style='kill-btn')
                btn.set_valign(Gtk.Align.FILL)
                btn._torrent_id = item['id']
                btn._action = action_type
                btn._row = item_row
                btn._ibox = ibox
                btn._sec = sec
                btn.connect('clicked', self._on_torrent_action_clicked)
                action_box.append(btn)

                rev.set_child(action_box)
                item_row.append(rev)

                # Hover controller
                motion = Gtk.EventControllerMotion.new()
                motion.connect("enter", self._on_row_enter, (item_row, rev))
                motion.connect("leave", self._on_row_leave, (item_row, rev))
                item_row.add_controller(motion)

                ibox.append(item_row)
                if i < len(items) - 1:
                    ibox.append(c.sep('h'))
            large = len(items) > 3
            vsgb = c.VScrollGradientBox(
                ibox, max_height=200 if large else None)
            c.add_style(vsgb, 'box')
            sec.append(vsgb)
            box.append(sec)

        # Bottom button
        btn = c.button("Open Transmission", style='normal')
        btn.connect("clicked", self.open_transmission)
        box.append(btn)

        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_visible(False)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_icon(data.get('icon', ''))
        widget.set_label(data.get('text', ''))

        hide_empty = self.config.get('hide_empty', True)
        if hide_empty:
            widget.set_visible(bool(data.get('text')))
        else:
            widget.set_visible(bool(data.get('text') or data.get('icon')))

        if data.get('stale'):
            c.add_style(widget, 'stale')

        if widget.get_active():
            return

        # Optimization: Don't rebuild popover if data hasn't changed
        compare_data = data.copy()
        compare_data.pop('timestamp', None)

        if getattr(widget, 'last_popover_data', None) == compare_data:
            return

        widget.last_popover_data = compare_data
        widget.set_widget(self.build_popover(data))


module_map = {
    'transmission': Transmission
}
