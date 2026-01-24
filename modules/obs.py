#!/usr/bin/python3 -u
"""
Description: OBS module refactored for unified state
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

try:
    import obsws_python as obs
except ImportError:
    obs = None

def fetch_data(config):
    if not obs: return None
    host = config.get('host', 'localhost')
    port = config.get('port', 4455)
    pw = config.get('password', 'password')
    
    try:
        cl = obs.ReqClient(host=host, port=port, password=pw)
        status = cl.get_record_status()
        scene = cl.get_current_program_scene().current_program_scene_name
        
        is_recording = status.output_active
        duration = status.output_duration / 1000 if is_recording else 0
        
        return {
            "text": f" {scene}",
            "scene": scene,
            "is_recording": is_recording,
            "duration": duration,
            "class": "green" if is_recording else ""
        }
    except Exception:
        return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    module.set_visible(bool(data['text']))
    module.reset_style()
    if data.get('class'):
        c.add_style(module, data['class'])
