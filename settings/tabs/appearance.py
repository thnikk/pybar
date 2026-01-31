#!/usr/bin/python3 -u
"""
Description: Appearance settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw

from settings.schema import FieldType
from settings.widgets.editors import create_editor


class AppearanceTab(Adw.PreferencesGroup):
    """Appearance and styling settings tab"""

    def __init__(self, config, on_change):
        super().__init__()
        self.set_title('Appearance')
        self.set_description('Customize the look and feel of the bar')

        self.config = config
        self.on_change = on_change

        style_schema = {
            'type': FieldType.FILE,
            'default': '',
            'label': 'Custom Style File',
            'description': 'Path to custom CSS file for styling the bar'
        }
        self.style_editor = create_editor(
            'style', style_schema,
            config.get('style', ''),
            self._on_field_change
        )
        self.add(self.style_editor)

        outputs_row = Adw.EntryRow()
        outputs_row.set_title('Outputs')
        outputs_row.set_show_apply_button(False)
        outputs = config.get('outputs', [])
        outputs_row.set_text(', '.join(outputs) if outputs else '')
        outputs_row.connect('changed', self._on_outputs_change)
        self.outputs_entry = outputs_row
        self.add(outputs_row)

        info_row = Adw.ActionRow()
        info_row.set_title('Tip')
        info_row.set_subtitle('The style file uses GTK4 CSS syntax')
        self.add(info_row)

    def _on_field_change(self, key, value):
        """Handle field value changes"""
        if self.on_change:
            self.on_change(key, value, None)

    def _on_outputs_change(self, entry):
        """Handle outputs change"""
        text = entry.get_text().strip()
        if text:
            outputs = [o.strip() for o in text.split(',') if o.strip()]
        else:
            outputs = []
        if self.on_change:
            self.on_change('outputs', outputs if outputs else None, None)

    def get_values(self):
        """Get current values"""
        text = self.outputs_entry.get_text().strip()
        outputs = (
            [o.strip() for o in text.split(',') if o.strip()]
            if text else None
        )
        return {
            'style': self.style_editor.get_value(),
            'outputs': outputs
        }
