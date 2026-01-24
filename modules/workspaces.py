#!/usr/bin/python3 -u
"""
Description: Properly threaded workspace module refactored for unified state
Author: thnikk
"""
from subprocess import Popen, PIPE, STDOUT, DEVNULL, run, CalledProcessError
import threading
import socket
import json
import os
import signal
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject  # noqa

def get_wm():
    try:
        run(['swaymsg', '-t', 'get_version'], capture_output=False, check=True, stdout=DEVNULL, stderr=DEVNULL)
        return 'sway'
    except CalledProcessError:
        return 'hypr'

def get_workspaces_data(wm):
    """ Get current workspace info """
    if wm == 'sway':
        try:
            raw = json.loads(run(['swaymsg', '-t', 'get_workspaces'], check=True, capture_output=True).stdout.decode('utf-8'))
            workspaces = [workspace['name'] for workspace in raw]
            workspaces.sort()
            focused = next((workspace['name'] for workspace in raw if workspace['focused']), None)
            return {'workspaces': workspaces, 'focused': focused}
        except Exception:
            return None
    else:
        try:
            workspaces = [w['name'] for w in json.loads(run(['hyprctl', '-j', 'workspaces'], check=True, capture_output=True).stdout.decode('utf-8'))]
            focused = json.loads(run(['hyprctl', '-j', 'activeworkspace'], check=True, capture_output=True).stdout.decode('utf-8'))['name']
            return {"workspaces": workspaces, "focused": focused}
        except Exception:
            return None

def run_worker(name, config):
    """ Worker thread for workspaces """
    wm = get_wm()
    
    def update():
        data = get_workspaces_data(wm)
        if data:
            c.state_manager.update(name, data)

    update()

    if wm == 'sway':
        while True:
            with Popen(['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'], stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
                for line in p.stdout:
                    update()
    else:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(f"{os.getenv('XDG_RUNTIME_DIR')}/hypr/{os.getenv('HYPRLAND_INSTANCE_SIGNATURE')}/.socket2.sock")
            while True:
                data = sock.recv(1024).decode('utf-8')
                if 'focus' in data or 'workspace' in data:
                    update()

def create_widget(bar, config):
    """ Create workspaces widget """
    box = c.box('h', style='workspaces')
    box.set_halign(Gtk.Align.CENTER)
    box.buttons = []
    
    for n in range(1, 11):
        label = config.get('icons', {}).get(str(n), config.get('icons', {}).get('default', str(n)))
        button = c.button(label=label, style='workspace')
        button.set_visible(False)
        button.connect('clicked', lambda b, wn=n: switch_workspace(wn))
        box.buttons.append(button)
        box.append(button)
        
    return box

def switch_workspace(n):
    run(['swaymsg', 'workspace', 'number', str(n)], stdout=DEVNULL, stderr=DEVNULL, check=False)

def update_ui(box, data):
    """ Update workspaces UI """
    workspaces = data['workspaces']
    focused = data['focused']
    
    for n, button in enumerate(box.buttons):
        name = str(n+1)
        if name in workspaces:
            button.set_visible(True)
        else:
            button.set_visible(False)
            
        if name == focused:
            c.add_style(button, 'focused')
        else:
            c.del_style(button, 'focused')
