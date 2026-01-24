#!/usr/bin/python3 -u
"""
Description: Privacy module refactored for unified state
Author: thnikk
"""
import common as c
import threading
from subprocess import Popen, PIPE, STDOUT, CalledProcessError
from glob import glob
import os
import signal
import gi
import time
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def run_worker(name, config):
    """ Background worker for privacy """
    state = {"devices": {}, "webcams": []}
    
    def update():
        c.state_manager.update(name, state)

    def get_webcams():
        while True:
            devices = []
            for path in glob('/sys/class/video4linux/video*'):
                try:
                    with open(f'{path}/state', 'r') as file:
                        if "capture" in file.read().strip():
                            with open(f'{path}/name', 'r') as name_file:
                                devices.append(name_file.read().strip())
                except FileNotFoundError:
                    pass
            if devices != state["webcams"]:
                state["webcams"] = devices
                update()
            time.sleep(1)

    t = threading.Thread(target=get_webcams, daemon=True)
    t.start()

    while True:
        try:
            with Popen(['pw-mon', '-a'], stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
                device = {}
                for line in p.stdout:
                    line = line.decode('utf-8').rstrip()
                    if 'added' in line or 'changed' in line:
                        try:
                            if 'Stream/Input' in device['properties']['media.class']:
                                state["devices"][device['id']] = device
                                update()
                        except KeyError: pass
                        device = {}
                    if 'removed' in line:
                        try:
                            state["devices"].pop(device['id'])
                            update()
                        except KeyError: pass
                        device = {}
                    if ':' in line:
                        parts = [p.strip().strip('"') for p in line.split(':')]
                        if len(parts) > 1: device[parts[0]] = ":".join(parts[1:])
                    if '=' in line:
                        parts = [p.strip().strip('"') for p in line.split('=')]
                        if 'properties' not in device: device['properties'] = {}
                        device['properties'][parts[0]] = parts[1]
        except Exception:
            time.sleep(1)

def create_widget(bar, config):
    """ Create privacy module widget """
    module = c.Module()
    module.set_position(bar.position)
    c.add_style(module.indicator, 'green')
    module.set_visible(False)
    return module

def update_ui(module, data):
    """ Update privacy UI """
    icons = {'Audio': '', 'Video': ''}
    types = set(d['properties']['media.class'].split('/')[-1] for d in data['devices'].values())
    
    text = [icons[t] for t in types if t in icons]
    if data['webcams']:
        text += [""]

    if text:
        module.text.set_label("  ".join(text))
        module.set_visible(True)
    else:
        module.set_visible(False)
    
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    """ Build privacy popover """
    box = c.box('v', spacing=20, style='small-widget')
    box.append(c.label('Privacy', style='heading'))
    
    categories = {}
    for d in data['devices'].values():
        cat = d['properties']['media.class'].split('/')[-1]
        if cat not in categories: categories[cat] = set()
        name = d['properties'].get('application.process.binary', 
                d['properties'].get('node.name', d['properties'].get('media.name', 'Unknown'))).title()
        categories[cat].add(name)
    
    if data['webcams']:
        categories['Camera'] = set(data['webcams'])

    for cat, progs in categories.items():
        cat_box = c.box('v', spacing=10)
        cat_box.append(c.label(cat, style='title', ha='start'))
        p_box = c.box('v', style='box')
        for i, p in enumerate(progs):
            p_box.append(c.label(p, style='inner-box'))
            if i != len(progs) - 1: p_box.append(c.sep('h'))
        cat_box.append(p_box)
        box.append(cat_box)
        
    return box
