#!/usr/bin/python3 -u
"""
Description: Docker module refactored for unified state
Author: thnikk
"""
from subprocess import run, Popen
import os
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def fetch_data(config):
    """ Get docker compose status and logs """
    path = os.path.expanduser(config.get('path', ''))
    if not path: return None
    
    try:
        # Get state
        state = run(
            ['docker', 'compose', 'ps', '--format', '"{{.State}}"'],
            check=True, capture_output=True, cwd=path
        ).stdout.decode('utf-8')
        
        running = 'running' in state
        logs = ""
        if running:
            output = run(
                ['docker', 'compose', 'logs', '--no-log-prefix'],
                cwd=path, capture_output=True, check=True
            ).stdout.decode('utf-8').splitlines()
            logs = '\n'.join(output[-14:])
            
        return {
            "running": running,
            "logs": logs,
            "path": path,
            "label": config.get('label', 'Docker')
        }
    except Exception:
        return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.text.set_label(config.get('label', 'Docker'))
    return module

def update_ui(module, data):
    if data['running']:
        module.icon.set_label('')
        c.add_style(module.indicator, 'green')
    else:
        module.icon.set_label('')
        module.reset_style()
        
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    container = c.box('v', spacing=10, style='small-widget')
    container.append(c.label(os.path.basename(data['path'].rstrip('/')), style='heading'))
    
    log_view = Gtk.TextView()
    log_view.set_editable(False)
    c.add_style(log_view, 'text-box')
    log_view.get_buffer().set_text(data['logs'])
    
    scrollable = c.scroll(width=600, height=300)
    c.add_style(scrollable, 'scroll-box')
    scrollable.set_child(log_view)
    container.append(scrollable)
    
    funcs = {"": ["up", "-d"], "": ["down"], "": ["restart"]}
    btn_box = c.box('h', spacing=10)
    for icon, func in funcs.items():
        btn = c.button(label=icon, style='normal')
        btn.connect('clicked', lambda b, f=func: Popen(['docker', 'compose'] + f, cwd=data['path']))
        btn_box.append(btn)
    container.append(btn_box)
    
    return container
