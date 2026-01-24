#!/usr/bin/python3 -u
"""
Description: Test module refactored for unified state
Author: thnikkk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

# Global counter for test
counter = 0

def fetch_data(config):
    global counter
    counter += 1
    return {"text": str(counter), "val": counter}

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.icon.set_label('')
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    box = c.box('v', spacing=10, style='small-widget')
    box.append(c.label('Test Module', style='heading'))
    box.append(c.label(f"Counter: {data['val']}", style='title'))
    return box
