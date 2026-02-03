#!/usr/bin/python3 -u
"""
Description: XDrip module refactored for unified state
Author: thnikk
"""
import requests
from datetime import datetime, timezone
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class XDrip(c.BaseModule):
    SCHEMA = {
        'ip': {
            'type': 'string',
            'default': '',
            'label': 'IP Address',
            'description': 'XDrip+ server IP address or hostname'
        },
        'port': {
            'type': 'integer',
            'default': 17580,
            'label': 'Port',
            'description': 'XDrip+ web service port',
            'min': 1,
            'max': 65535
        },
        'api_secret': {
            'type': 'string',
            'default': '',
            'label': 'API Secret',
            'description': 'XDrip+ API secret'
        },
        'min': {
            'type': 'integer',
            'default': 40,
            'label': 'Graph Minimum',
            'description': 'Minimum value for glucose graph',
            'min': 0,
            'max': 100
        },
        'max': {
            'type': 'integer',
            'default': 200,
            'label': 'Graph Maximum',
            'description': 'Maximum value for glucose graph',
            'min': 100,
            'max': 400
        },
        'interval': {
            'type': 'integer',
            'default': 60,
            'label': 'Update Interval',
            'description': 'How often to fetch glucose data (seconds)',
            'min': 30,
            'max': 300
        }
    }

    def fetch_data(self):
        ip = self.config.get('ip') or self.config.get('host')
        port = self.config.get('port')
        secret = self.config.get('api_secret')

        if not all([ip, port, secret]):
            c.print_debug(
                "XDrip config missing ip/host, port, or secret", color='red')
            return {}

        try:
            url = f"http://{ip}:{port}/sgv.json"
            res = requests.get(
                url, headers={"api-secret": secret}, timeout=5).json()
            if not res:
                return {}

            sgv = res[0]["sgv"]
            last_sgv = res[1]["sgv"] if len(res) > 1 else sgv
            delta = sgv - last_sgv
            direction = res[0]["direction"]
            dt = datetime.strptime(
                res[0]["dateString"], "%Y-%m-%dT%H:%M:%S.%f%z")
            since_last = int(
                (datetime.now(timezone.utc) - dt).total_seconds() / 60)

            arrows = {
                "DoubleUp": "↑↑", "SingleUp": "↑", "FortyFiveUp": "↗️",
                "Flat": "→", "FortyFiveDown": "↘️", "SingleDown": "↓",
                "DoubleDown": "↓↓"
            }
            arr = arrows.get(direction, direction)

            cls = ""
            if sgv < 80:
                cls = "red"
            elif sgv > 180:
                cls = "orange"
            if since_last > 15:
                cls = "gray"

            history = [item["sgv"] for item in res[::-1]]
            history_labels = [
                f"{item['sgv']}\n"
                f"{datetime.fromtimestamp(item['date'] / 1000).strftime('%I:%M %p')}"
                for item in res[::-1]
            ]

            return {
                "text": f" {sgv} {arr}",
                "sgv": sgv,
                "delta": delta,
                "direction": arr,
                "date": dt.strftime("%m/%d/%y %I:%M:%S %p"),
                "since_last": since_last,
                "class": cls,
                "history": history,
                "history_labels": history_labels,
                "min": self.config.get('min'),
                "max": self.config.get('max')
            }
        except Exception as e:
            c.print_debug(f"XDrip fetch failed: {e}", color='red')
            return {}

    def build_popover(self, data):
        box = c.box('v', spacing=20, style='small-widget')

        # Header section
        box.append(c.label('XDrip+', style='heading', he=True))

        # SGV with Arrow to top right
        wide = c.box('h', spacing=20)
        sgv_box = c.box('h', spacing=5)
        sgv_box.append(c.label(str(data['sgv']), style='large-text'))
        sgv_box.append(c.label(data['direction'], style='arrow', va='start'))
        wide.append(sgv_box)

        # Time ago aligned with top of SGV and arrow
        wide.append(c.label(f"{data['since_last']}m ago",
                    style='gray', ha='end', va='start', he=True))
        box.append(wide)

        if data.get('history'):
            graph_box = c.box('v', style='box')
            graph_box.set_overflow(Gtk.Overflow.HIDDEN)

            # Use values from config or intelligent defaults
            min_val = data.get('min', 40)
            max_val = data.get('max', max(max(data['history']), 200))

            graph_box.append(c.Graph(
                data['history'],
                height=100,
                min_config=min_val,
                max_config=max_val,
                hover_labels=data.get('history_labels'),
                smooth=True
            ))
            box.append(graph_box)

        # Bottom box with padding around items
        bot = c.box('h', style='box')
        bot.append(c.label(f" {data['delta']}", style='inner-box', he=True))
        bot.append(c.sep('v'))
        bot.append(c.label(f" {data['date']}", style='inner-box', he=True))
        box.append(bot)

        return box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.reset_style()
        if data.get('class'):
            c.add_style(widget, data['class'])
        if data.get('stale'):
            c.add_style(widget, 'stale')

        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'xdrip': XDrip
}
