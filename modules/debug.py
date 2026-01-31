#!/usr/bin/python3 -u
"""
Description: Debug module to open GTK Inspector
Author: thnikk
"""
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Debug(c.BaseModule):
    EMPTY_IS_ERROR = False

    def fetch_data(self):
        """ Debug module doesn't need external data """
        return {}

    def open_inspector(self, _btn):
        Gtk.Window.set_interactive_debugging(True)

    def on_debug_toggled(self, btn):
        state = btn.get_active()
        if c.state_manager.get('debug_popovers') != state:
            c.state_manager.update('debug_popovers', state)

    def build_popover(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        # Inspector button
        inspector_btn = c.button(label="Open Inspector", style="normal")
        inspector_btn.connect('clicked', self.open_inspector)
        box.append(inspector_btn)

        # Debug Popovers button (toggle)
        toggle_btn = Gtk.ToggleButton(label="Debug Popovers")
        toggle_btn.get_style_context().add_class("normal")
        toggle_btn.connect('toggled', self.on_debug_toggled)

        # Initialize state and subscribe
        def on_state_changed(state):
            if toggle_btn.get_active() != state:
                toggle_btn.set_active(state)

        current_state = c.state_manager.get('debug_popovers') or False
        toggle_btn.set_active(current_state)

        c.state_manager.subscribe('debug_popovers', on_state_changed)
        box.append(toggle_btn)

        return box

    def create_widget(self, bar):
        m = c.Module(icon=True, text=False)
        m.set_position(bar.position)
        m.set_icon(self.config.get('icon', ''))
        m.set_widget(self.build_popover())
        return m


module_map = {
    'debug': Debug
}
