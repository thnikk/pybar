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


def fetch_data(config):
    ip = config.get('ip') or config.get('host')
    port = config.get('port')
    secret = config.get('api_secret')

    if not all([ip, port, secret]):
        c.print_debug(
            "XDrip config missing ip/host, port, or secret", color='red')
        return None

    try:
        url = f"http://{ip}:{port}/sgv.json"
        res = requests.get(
            url, headers={"api-secret": secret}, timeout=5).json()
        if not res:
            return None

        sgv = res[0]["sgv"]
        last_sgv = res[1]["sgv"] if len(res) > 1 else sgv
        delta = sgv - last_sgv
        direction = res[0]["direction"]
        dt = datetime.strptime(res[0]["dateString"], "%Y-%m-%dT%H:%M:%S.%f%z")
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
            f"{item['sgv']}\n{datetime.fromtimestamp(item['date']/1000).strftime('%I:%M %p')}"
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
            "min": config.get('min'),
            "max": config.get('max')
        }
    except Exception as e:
        c.print_debug(f"XDrip fetch failed: {e}", color='red')
        return None


def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    return module


def update_ui(module, data):
    module.set_label(data['text'])
    module.reset_style()
    if data.get('class'):
        c.add_style(module, data['class'])

    if not module.get_active():
        module.set_widget(build_popover(data))


def build_popover(data):
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
