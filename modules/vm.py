#!/usr/bin/python3 -u
"""
Description: VM module refactored for unified state
Author: thnikk
"""
import glob
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def fetch_data(config):
    try:
        domains = [p.split("/")[-1].rstrip(".xml") for p in glob.glob("/var/run/libvirt/qemu/*.xml")]
        return {
            "text": f" {len(domains)}" if domains else "",
            "domains": domains
        }
    except Exception: return None

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
    box.append(c.label('Running VMs', style='heading'))
    
    ibox = c.box('v', style='box')
    for i, d in enumerate(data['domains']):
        ibox.append(c.label(d, style='inner-box', ha='start'))
        if i < len(data['domains']) - 1: ibox.append(c.sep('h'))
    
    box.append(ibox)
    return box
