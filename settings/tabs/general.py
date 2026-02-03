#!/usr/bin/python3 -u
"""
Description: General settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from settings.schema import GLOBAL_SCHEMA
from settings.widgets.editors import create_editor


class GeneralTab(Adw.PreferencesGroup):
    """General bar settings tab"""

    def __init__(self, config, on_change):
        super().__init__()
        self.set_title('General Settings')
        self.set_description('Configure global bar behavior')
        self.set_focusable(True)

        self.config = config
        self.on_change = on_change
        self.editors = {}
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.add(self.box)

        for key, schema_field in GLOBAL_SCHEMA.items():
            value = config.get(key, schema_field.get('default'))
            editor = create_editor(
                key, schema_field, value, self._on_field_change
            )
            self.editors[key] = editor
            self.box.append(editor)

    def _on_field_change(self, key, value):
        """Handle field value changes"""
        if self.on_change:
            self.on_change(key, value, None)

    def get_values(self):
        """Get all current values"""
        return {
            key: editor.get_value() for key, editor in self.editors.items()
        }
