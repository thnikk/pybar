#!/usr/bin/python3 -u
"""
Description: Appearance settings tab
Author: thnikk
"""
from settings.widgets.editors import create_editor
from settings.schema import FieldType, GLOBAL_SCHEMA
from gi.repository import Gtk, Adw, Gdk
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')


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

        # Bar Dimensions
        dimensions_group = Adw.PreferencesGroup()
        dimensions_group.set_title('Dimensions &amp; Typography')
        self.append(dimensions_group)

        for key in ['bar-height', 'font-size']:
            schema_field = GLOBAL_SCHEMA[key]
            value = config.get(key, schema_field['default'])

            row = Adw.ActionRow()
            row.set_title(schema_field.get('label', key))
            row.set_subtitle(schema_field.get('description', ''))

            editor = create_editor(
                key, schema_field, value, self._on_field_change,
                show_label=False
            )
            editor.set_valign(Gtk.Align.CENTER)
            row.add_suffix(editor)

            # Add reset button
            reset_btn = Gtk.Button.new_from_icon_name('edit-undo-symbolic')
            reset_btn.set_valign(Gtk.Align.CENTER)
            reset_btn.add_css_class('flat')
            reset_btn.set_tooltip_text('Reset to default')
            reset_btn.connect(
                'clicked', lambda _, k=key, e=editor, s=schema_field:
                e.set_value(s['default'])
            )
            row.add_suffix(reset_btn)

            dimensions_group.add(row)

            if key == 'bar-height':
                self.bar_height_editor = editor
            else:
                self.font_size_editor = editor

        style_schema = GLOBAL_SCHEMA['style']
        self.style_editor = create_editor(
            'style', style_schema,
            config.get('style', style_schema['default']),
            self._on_field_change
        )
        self.append(self.style_editor)

        outputs_schema = GLOBAL_SCHEMA['outputs']
        outputs_schema['choices'] = self._get_monitors()
        outputs_schema['choices_label'] = 'Add monitor...'

        self.outputs_editor = create_editor(
            'outputs', outputs_schema,
            config.get('outputs', outputs_schema['default']),
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
        self.bar_height_editor.set_value(
            config.get('bar-height', GLOBAL_SCHEMA['bar-height']['default']))
        self.font_size_editor.set_value(
            config.get('font-size', GLOBAL_SCHEMA['font-size']['default']))

    def get_values(self):
        """Get current values"""
        return {
            'style': self.style_editor.get_value(),
            'outputs': self.outputs_editor.get_value(),
            'bar-height': self.bar_height_editor.get_value(),
            'font-size': self.font_size_editor.get_value()
        }
