#!/usr/bin/python3 -u
"""
Description: Toggle module refactored for unified state
Author: thnikkk
"""
import common as c
from subprocess import Popen, DEVNULL
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

# Toggle module state is mostly local to each instance but we follow the pattern
# Actually, if we want shared toggle state, we should use a worker to track the process.

procs = {} # Global procs map {name: proc}

def fetch_data(config):
    """ Fetch toggle data (is the process alive?) """
    name = config.get('name', 'default')
    proc = procs.get(name)
    alive = False
    if proc:
        if proc.poll() is None:
            alive = True
        else:
            del procs[name]
    
    return {
        "alive": alive,
        "icon": config.get('icon', '')
    }

def create_widget(bar, config):
    """ Create toggle widget """
    name = config.get('name', 'default')
    icon = config.get('icon', '')
    command = config.get('program', ['tail', '-f', '/dev/null'])
    
    box = c.box('h', style='module', spacing=5)
    box.append(c.label(icon))
    
    switch_box = c.box('v')
    sw = Gtk.Switch.new()
    c.add_style(sw, 'switch')
    switch_box.append(sw)
    box.append(switch_box)
    
    def on_state_set(s, state):
        if state:
            if name not in procs or procs[name].poll() is not None:
                procs[name] = Popen(command, stdout=DEVNULL, stderr=DEVNULL)
        else:
            if name in procs:
                procs[name].terminate()
        return False # Don't inhibit signal
        
    sw.connect('state-set', on_state_set)
    box.sw = sw
    return box

def update_ui(box, data):
    """ Update toggle UI """
    # Block signals during update to avoid loops
    box.sw.set_state(data['alive'])
