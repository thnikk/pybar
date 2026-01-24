#!/usr/bin/python3 -u
"""
Description: MPC module refactored for unified state
Author: thnikk
"""
from subprocess import run, DEVNULL, CalledProcessError
import common as c
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Pango  # noqa

def get_mpc_status():
    try:
        output = run(['mpc', 'status'], capture_output=True, check=True).stdout.decode('utf-8').splitlines()
        if len(output) < 2:
            return {"status": "stopped", "song": "Stopped", "artist": ""}
            
        song_line = output[0]
        status_line = output[1]
        
        artist = song_line.split(' - ')[0].strip() if ' - ' in song_line else ""
        song = song_line.split(' - ')[-1].strip()
        status = status_line.split(']')[0].lstrip('[')
        
        return {
            "status": status,
            "song": song,
            "artist": artist,
            "text": song
        }
    except Exception:
        return None

def run_worker(name, config):
    """ Background worker for mpc """
    def update():
        data = get_mpc_status()
        if data:
            c.state_manager.update(name, data)

    update()
    while True:
        try:
            run(['mpc', 'idle'], stdout=DEVNULL, stderr=DEVNULL)
            update()
        except Exception:
            time.sleep(5)
            update()

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.text.set_max_width_chars(20)
    module.text.set_ellipsize(Pango.EllipsizeMode.END)
    return module

def update_ui(module, data):
    status = data['status']
    if status == 'playing':
        module.icon.set_text('')
    elif status == 'paused':
        module.icon.set_text('')
    else:
        module.icon.set_text('')
    module.text.set_text(data['song'])
