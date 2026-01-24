#!/usr/bin/python3 -u
"""
Description: Home Assistant dashboard module refactored for unified state
Author: thnikk
"""
import requests
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def get_ha_state(server, entity, token):
    try:
        res = requests.get(f"http://{server}/api/states/{entity}", 
                           headers={"Authorization": token, "content-type": "application/json"},
                           timeout=3).json()
        return res
    except Exception: return None

def fetch_data(config):
    server = config.get('server')
    token = config.get('bearer_token')
    devices_config = config.get('devices', {})
    
    if not server or not token: return None
    
    # We fetch states for all configured devices
    sections = {}
    for section, entities in devices_config.items():
        sections[section] = []
        for name, eid in entities.items():
            state_data = get_ha_state(server, eid, token)
            if state_data:
                sections[section].append({
                    "name": name,
                    "id": eid,
                    "state": state_data.get('state'),
                    "unit": state_data.get('attributes', {}).get('unit_of_measurement', '')
                })
                
    return {
        "sections": sections,
        "server": server,
        "token": token
    }

def create_widget(bar, config):
    module = c.Module(1, 0)
    module.set_position(bar.position)
    module.icon.set_label('')
    return module

def update_ui(module, data):
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    box = c.box('v', spacing=20, style='small-widget')
    box.append(c.label('Home Assistant', style='heading'))
    
    for section, devices in data['sections'].items():
        sec_box = c.box('v', spacing=10)
        sec_box.append(c.label(section, style='title', ha='start'))
        ibox = c.box('v', style='box')
        
        for i, dev in enumerate(devices):
            row = c.box('h', spacing=20, style='inner-box')
            row.append(c.label(dev['name'], ha="start", he=True))
            
            eid_type = dev['id'].split('.')[0]
            if eid_type == 'sensor':
                val = dev['state']
                if '.' in val: val = val.split('.')[0]
                row.append(c.label(f"{val}{dev['unit']}", ha="end"))
            elif eid_type in ['switch', 'light']:
                sw = Gtk.Switch.new()
                sw.set_active(dev['state'] == 'on')
                sw.connect('state-set', lambda s, st, d=data, eid=dev['id']: toggle_ha(d, eid, st))
                row.append(sw)
            
            ibox.append(row)
            if i < len(devices) - 1: ibox.append(c.sep('v'))
            
        sec_box.append(ibox)
        box.append(sec_box)
        
    return box

def toggle_ha(data, eid, state):
    try:
        domain = eid.split('.')[0]
        # Always use toggle service for simplicity
        requests.post(f"http://{data['server']}/api/services/{domain}/toggle",
                      headers={"Authorization": data['token'], "content-type": "application/json"},
                      json={"entity_id": eid}, timeout=3)
    except Exception: pass
    return False
