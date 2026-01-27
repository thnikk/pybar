#!/usr/bin/python3 -u
"""
Description: Transmission module refactored for unified state
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

try:
    from transmission_rpc import Client
except ImportError:
    Client = None

def fetch_data(config):
    if not Client: return None
    
    try:
        client = Client(
            host=config.get("host", "localhost"),
            port=config.get("port", 9091)
        )
        torrents = client.get_torrents()
        
        down_list = []
        up_list = []
        for t in torrents:
            if t.status == 'downloading':
                down_list.append(f'{t.name} {int(t.progress)}%')
            elif t.status == 'seeding':
                up_list.append(t.name)
                
        text_parts = []
        if down_list: text_parts.append(f" {len(down_list)}")
        if up_list: text_parts.append(f" {len(up_list)}")
        
        return {
            "text": "  ".join(text_parts),
            "downloading": down_list,
            "uploading": up_list
        }
    except Exception:
        return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    module.set_label(data['text'])
    module.set_visible(bool(data['text']))
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    box = c.box('v', spacing=20, style='small-widget')
    box.append(c.label('Transmission', style='heading'))
    
    for title, items in [("Downloading", data['downloading']), ("Seeding", data['uploading'])]:
        if not items: continue
        sec = c.box('v', spacing=10)
        sec.append(c.label(title, style='title', ha='start'))
        ibox = c.box('v', style='box')
        for i, item in enumerate(items):
            ibox.append(c.label(item, style='inner-box', ha='start'))
            if i < len(items) - 1: ibox.append(c.sep('h'))
        sec.append(ibox)
        box.append(sec)
        
    return box
