#!/usr/bin/python3 -u
"""
Description: Appearance settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk

from settings.schema import FieldType
from settings.widgets.editors import create_editor


class AppearanceTab(Gtk.Box):
    """Appearance and styling settings tab"""

    def __init__(self, config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_focusable(True)
        self.connect('map', lambda _: self.grab_focus())

        self.config = config
        self.on_change = on_change

        header = Adw.PreferencesGroup()
        header.set_title('Appearance')
        header.set_description('Customize the look and feel of the bar')
        header.set_focusable(True)
        self.append(header)

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

        outputs_schema = {
            'type': FieldType.LIST,
            'item_type': FieldType.STRING,
            'default': [],
            'label': 'Outputs',
            'description': 'List of monitor outputs to display on',
            'choices': self._get_monitors(),
            'choices_label': 'Add monitor...',
            'unique': True,
            'sortable': False
        }
        self.outputs_editor = create_editor(
            'outputs', outputs_schema,
            config.get('outputs', []),
            self._on_field_change
        )
        self.append(self.outputs_editor)

    def _get_monitors(self):
        """Get names of currently connected monitors"""
        display = Gdk.Display.get_default()
        if not display:
            return []

        monitors = display.get_monitors()
        names = []
        for i in range(monitors.get_n_items()):
            monitor = monitors.get_item(i)
            name = None

            # Try to get the connector name (e.g., eDP-1, HDMI-A-1)
            try:
                name = monitor.get_connector()
            except (AttributeError, TypeError):
                pass

            if not name:
                try:
                    name = monitor.get_model()
                except (AttributeError, TypeError):
                    pass

            if not name:
                name = f"monitor_{i}"

            if name not in names:
                names.append(name)

        return sorted(names)

    def _on_field_change(self, key, value):
        """Handle field value changes"""
        if self.on_change:
            self.on_change(key, value, None)

    def refresh(self, config):
        """Update editors with new config values"""
        self.config = config
        self.style_editor.set_value(config.get('style', ''))
        self.outputs_editor.set_value(config.get('outputs', []))

    def get_values(self):
        """Get current values"""
        return {
            'style': self.style_editor.get_value(),
            'outputs': self.outputs_editor.get_value()
        }
