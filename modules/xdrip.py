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
    ip = config.get('ip')
    port = config.get('port')
    secret = config.get('api_secret')
    
    if not all([ip, port, secret]): return None
    
    try:
        url = f"http://{ip}:{port}/sgv.json"
        res = requests.get(url, headers={"api-secret": secret}, timeout=5).json()
        if not res: return None
        
        sgv = res[0]["sgv"]
        last_sgv = res[1]["sgv"] if len(res) > 1 else sgv
        delta = sgv - last_sgv
        direction = res[0]["direction"]
        dt = datetime.strptime(res[0]["dateString"], "%Y-%m-%dT%H:%M:%S.%f%z")
        since_last = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
        
        arrows = {
            "DoubleUp": "↑↑", "SingleUp": "↑", "FortyFiveUp": "↗️",
            "Flat": "→", "FortyFiveDown": "↘️", "SingleDown": "↓", "DoubleDown": "↓↓"
        }
        arr = arrows.get(direction, direction)
        
        cls = ""
        if sgv < 80: cls = "red"
        elif sgv > 180: cls = "orange"
        if since_last > 5: cls = "gray"
        
        return {
            "text": f" {sgv} {arr}",
            "sgv": sgv,
            "delta": delta,
            "direction": arr,
            "date": dt.strftime("%m/%d/%y %I:%M:%S %p"),
            "since_last": since_last,
            "class": cls
        }
    except Exception:
        return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    module.reset_style()
    if data.get('class'):
        c.add_style(module, data['class'])
        
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    box = c.box('v', spacing=20, style='small-widget')
    box.append(c.label('XDrip+', style='heading'))

    wide = c.box('h', spacing=20)
    sgv_box = c.box('h', spacing=5)
    sgv_box.append(c.label(str(data['sgv']), style='large-text'))
    sgv_box.append(c.label(data['direction']))
    wide.append(sgv_box)
    
    wide.append(c.label(f"{data['since_last']}m ago", ha='end', he=True))
    box.append(wide)

    bot = c.box('h', style='box')
    items = [f" {data['delta']}", f" {data['date']}"]
    for i, item in enumerate(items):
        bot.append(c.label(item))
        if i < len(items) - 1:
            bot.append(c.sep('v'))
    box.append(bot)

    return box
