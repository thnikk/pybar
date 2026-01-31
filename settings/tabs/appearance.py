#!/usr/bin/python3 -u
"""
Description: Appearance settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

from settings.schema import FieldType
from settings.widgets.editors import create_editor


class AppearanceTab(Gtk.Box):
    """Appearance and styling settings tab"""

    def __init__(self, config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)

        self.config = config
        self.on_change = on_change

        # Header
        header = Gtk.Label(label='Appearance')
        header.set_halign(Gtk.Align.START)
        self.append(header)

        # Style file path
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
        self.append(self.style_editor)

        # Outputs (which monitors to show bar on)
        outputs_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        outputs_label = Gtk.Label(label='Outputs')
        outputs_label.set_halign(Gtk.Align.START)
        outputs_box.append(outputs_label)

        outputs_desc = Gtk.Label(
            label='Limit bar to specific outputs (leave empty for all)')
        outputs_desc.set_halign(Gtk.Align.START)
        outputs_desc.set_opacity(0.7)
        outputs_box.append(outputs_desc)

        self.outputs_entry = Gtk.Entry()
        outputs = config.get('outputs', [])
        self.outputs_entry.set_text(', '.join(outputs) if outputs else '')
        self.outputs_entry.set_placeholder_text('e.g., DP-1, HDMI-A-1')
        self.outputs_entry.connect('changed', self._on_outputs_change)
        outputs_box.append(self.outputs_entry)

        self.append(outputs_box)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_vexpand(True)
        self.append(spacer)

        # Info
        info = Gtk.Label(
            label='Tip: The style file uses GTK4 CSS syntax.')
        info.set_opacity(0.7)
        info.set_halign(Gtk.Align.START)
        self.append(info)

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
        outputs = [o.strip() for o in text.split(',') if o.strip()] if text \
            else None
        return {
            'style': self.style_editor.get_value(),
            'outputs': outputs
        }
