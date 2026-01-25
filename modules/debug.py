#!/usr/bin/python3 -u
"""
Description: Debug module to open GTK Inspector
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


def create_widget(bar, config):
    """ Create debug widget """
    module = c.Module(icon=True, text=False)
    module.set_icon(config.get('icon', ''))

    # Create the content box for the popover
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

    # Inspector button
    inspector_btn = c.button(label="Open Inspector", style="normal")
    
    def open_inspector(btn):
        Gtk.Window.set_interactive_debugging(True)
        
    inspector_btn.connect('clicked', open_inspector)
    box.append(inspector_btn)

    # Debug Popovers button (toggle)
    toggle_btn = Gtk.ToggleButton(label="Debug Popovers")
    toggle_btn.get_style_context().add_class("normal")

    def on_toggled(btn):
        state = btn.get_active()
        if c.state_manager.get('debug_popovers') != state:
            c.state_manager.update('debug_popovers', state)

    toggle_btn.connect('toggled', on_toggled)

    # Initialize state and subscribe
    def on_state_changed(state):
        if toggle_btn.get_active() != state:
            toggle_btn.set_active(state)
            
    current_state = c.state_manager.get('debug_popovers') or False
    toggle_btn.set_active(current_state)
    
    c.state_manager.subscribe('debug_popovers', on_state_changed)

    box.append(toggle_btn)

    module.set_widget(box)

    return module
