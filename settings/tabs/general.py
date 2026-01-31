#!/usr/bin/python3 -u
"""
Description: General settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

from settings.schema import GLOBAL_SCHEMA
from settings.widgets.editors import create_editor


class GeneralTab(Gtk.Box):
    """General bar settings tab"""

    def __init__(self, config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)

        self.config = config
        self.on_change = on_change
        self.editors = {}

        # Header
        header = Gtk.Label(label='General Settings')
        header.set_halign(Gtk.Align.START)
        self.append(header)

        # Scrollable content
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)

        # Create editors for each global setting
        for key, schema_field in GLOBAL_SCHEMA.items():
            value = config.get(key, schema_field.get('default'))
            editor = create_editor(key, schema_field, value, self._on_field_change)
            self.editors[key] = editor
            content.append(editor)

        scroll.set_child(content)
        self.append(scroll)

    def _on_field_change(self, key, value):
        """Handle field value changes"""
        if self.on_change:
            self.on_change(key, value, None)  # None = global config

    def get_values(self):
        """Get all current values"""
        return {key: editor.get_value() for key, editor in self.editors.items()}
