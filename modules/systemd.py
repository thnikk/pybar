#!/usr/bin/python3 -u
"""
Description: Systemd module refactored for unified state
Author: thnikk
"""
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def get_failed(user=False):
    cmd = ['systemctl', '--failed', '--legend=no']
    if user: cmd.insert(1, '--user')
    try:
        res = run(cmd, check=True, capture_output=True).stdout.decode('utf-8').strip().splitlines()
        return [line.split()[1] for line in res if len(line.split()) > 1]
    except Exception: return []

def fetch_data(config):
    blacklist = config.get('blacklist', [])
    
    failed_sys = [s for s in get_failed() if s.split('.')[0] not in blacklist]
    failed_user = [s for s in get_failed(user=True) if s.split('.')[0] not in blacklist]
    
    total = len(failed_sys) + len(failed_user)
    return {
        "text": f' {total}' if total else "",
        "failed_system": failed_sys,
        "failed_user": failed_user
    }

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    module.set_visible(bool(data['text']))
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    box = c.box('v', spacing=20, style='small-widget')
    box.append(c.label('Failed Services', style='heading'))
    
    sections = [("System", data['failed_system']), ("User", data['failed_user'])]
    for name, failed in sections:
        if not failed: continue
        sec_box = c.box('v', spacing=10)
        sec_box.append(c.label(name, style='title', ha='start'))
        items_box = c.box('v', style='box')
        for i, s in enumerate(failed):
            items_box.append(c.label(s, style='inner-box', ha='start'))
            if i < len(failed) - 1: items_box.append(c.sep('h'))
        sec_box.append(items_box)
        box.append(sec_box)
        
    return box
