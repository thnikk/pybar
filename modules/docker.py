#!/usr/bin/python3 -u
"""
Description: Docker module refactored for unified state
Author: thnikk
"""
from subprocess import run, Popen
import os
import weakref
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Docker(c.BaseModule):
    SCHEMA = {
        'path': {
            'type': 'file',
            'default': '',
            'label': 'Compose Directory',
            'description': 'Path to docker-compose directory'
        },
        'label': {
            'type': 'string',
            'default': 'Docker',
            'label': 'Label',
            'description': 'Label to show in the bar'
        },
        'interval': {
            'type': 'integer',
            'default': 30,
            'label': 'Update Interval',
            'description': 'How often to check docker status (seconds)',
            'min': 5,
            'max': 300
        }
    }

    def fetch_data(self):
        """ Get docker compose status and logs """
        path = os.path.expanduser(self.config.get('path', ''))
        if not path:
            return {}

        try:
            # Get state
            state = run(
                ['docker', 'compose', 'ps', '--format', '"{{.State}}"'],
                check=True, capture_output=True, cwd=path
            ).stdout.decode('utf-8')

            running = 'running' in state
            logs = ""
            if running:
                output = run(
                    ['docker', 'compose', 'logs', '--no-log-prefix'],
                    cwd=path, capture_output=True, check=True
                ).stdout.decode('utf-8').splitlines()
                logs = '\n'.join(output[-14:])

            return {
                "running": running,
                "logs": logs,
                "path": path,
                "label": self.config.get('label', 'Docker')
            }
        except Exception:
            return {}

    def build_popover(self, widget, data):
        container = c.box('v', spacing=10, style='small-widget')
        container.append(
            c.label(
                os.path.basename(data['path'].rstrip('/')), style='heading'))

        log_view = Gtk.TextView()
        log_view.set_editable(False)
        c.add_style(log_view, 'text-box')
        log_view.get_buffer().set_text(data['logs'])

        scrollable = c.scroll(width=600, height=300)
        c.add_style(scrollable, 'scroll-box')
        scrollable.set_child(log_view)
        container.append(scrollable)

        funcs = {"": ["up", "-d"], "": ["down"], "": ["restart"]}
        btn_box = c.box('h', spacing=10)
        for icon, func in funcs.items():
            btn = c.button(label=icon, style='normal')
            btn.connect(
                'clicked', lambda _b, f=func: Popen(
                    ['docker', 'compose'] + f, cwd=data['path']))
            btn_box.append(btn)
        container.append(btn_box)

        widget.popover_widgets = {'log_view': log_view}
        return container

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_label(self.config.get('label', 'Docker'))

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
        if data.get('running'):
            widget.set_icon('')
            widget.add_indicator_style('green')
        else:
            widget.set_icon('')
            widget.reset_style()

        # Optimization: Don't update if data hasn't changed
        compare_data = data.copy()
        compare_data.pop('timestamp', None)

        if (widget.get_popover() and
                getattr(widget, 'last_popover_data', None) == compare_data):
            return

        widget.last_popover_data = compare_data

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))
        else:
            if hasattr(widget, 'popover_widgets'):
                buffer = widget.popover_widgets['log_view'].get_buffer()
                if buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False) != data['logs']:
                    buffer.set_text(data['logs'])


module_map = {
    'docker': Docker
}
