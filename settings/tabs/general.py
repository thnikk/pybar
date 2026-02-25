#!/usr/bin/python3 -u
"""
Description: General settings tab
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GObject

from settings.schema import GLOBAL_SCHEMA, FieldType
from settings.widgets.editors import create_editor


class GeneralTab(Gtk.Box):
    """General bar settings tab"""

    def __init__(self, config, on_change):

        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.set_focusable(True)

        self.config = config
        self.on_change = on_change
        self.editors = {}

        # General Group
        self.general_group = Adw.PreferencesGroup()
        self.general_group.set_title('General Settings')
        self.general_group.set_description('Configure global bar behavior')
        self.append(self.general_group)

        # Floating Mode Group
        self.floating_group = Adw.PreferencesGroup()
        self.floating_group.set_title('Floating Mode')
        self.floating_group.set_description(
            'Configure floating bar appearance'
        )
        self.append(self.floating_group)

        # Popovers Group
        self.popovers_group = Adw.PreferencesGroup()
        self.popovers_group.set_title('Popovers')
        self.append(self.popovers_group)

        for key, schema_field in GLOBAL_SCHEMA.items():
            if key in ['style', 'outputs', 'bar-height', 'font-size']:
                continue

            value = config.get(key, schema_field.get('default'))
            
            if schema_field.get('type') == FieldType.CHOICE:
                row = Adw.ActionRow()
                row.set_title(schema_field.get('label', key))
                row.set_subtitle(schema_field.get('description', ''))
                
                choices = schema_field.get('choices', [])
                string_list = Gtk.StringList()
                for choice in choices:
                    string_list.append(str(choice))
                
                dropdown = Gtk.DropDown(model=string_list)
                dropdown.set_valign(Gtk.Align.CENTER)
                
                if value in choices:
                    dropdown.set_selected(choices.index(value))
                
                row.add_suffix(dropdown)
                row.set_activatable_widget(dropdown)

                # Add reset button
                reset_btn = Gtk.Button.new_from_icon_name('edit-undo-symbolic')
                reset_btn.set_valign(Gtk.Align.CENTER)
                reset_btn.add_css_class('flat')
                reset_btn.set_tooltip_text('Reset to default')
                
                def on_reset_clicked(_, k=key, d=dropdown, s=schema_field):
                    choices = s.get('choices', [])
                    default = s.get('default')
                    if default in choices:
                        d.set_selected(choices.index(default))

                reset_btn.connect('clicked', on_reset_clicked)
                row.add_suffix(reset_btn)
                
                class SimpleEditor:
                    def __init__(self, dropdown, choices, key, parent):
                        self.dropdown = dropdown
                        self.choices = choices
                        self.key = key
                        self.parent = parent
                        self.dropdown.connect('notify::selected', self._on_changed)
                    def _on_changed(self, *args):
                        idx = self.dropdown.get_selected()
                        if 0 <= idx < len(self.choices):
                            val = self.choices[idx]
                            if self.parent.on_change:
                                self.parent.on_change(self.key, val, None)
                    def get_value(self):
                        idx = self.dropdown.get_selected()
                        return self.choices[idx] if 0 <= idx < len(self.choices) else None
                    def set_value(self, val):
                        if val in self.choices:
                            self.dropdown.set_selected(self.choices.index(val))
                
                self.editors[key] = SimpleEditor(dropdown, choices, key, self)
            else:
                row = Adw.ActionRow()
                row.set_title(schema_field.get('label', key))
                row.set_subtitle(schema_field.get('description', ''))

                editor = create_editor(
                    key, schema_field, value, self._on_field_change,
                    show_label=False
                )
                self.editors[key] = editor
                
                # Use the actual control widget for alignment if possible
                editor.set_valign(Gtk.Align.CENTER)
                row.add_suffix(editor)

                # Add reset button
                reset_btn = Gtk.Button.new_from_icon_name('edit-undo-symbolic')
                reset_btn.set_valign(Gtk.Align.CENTER)
                reset_btn.add_css_class('flat')
                reset_btn.set_tooltip_text('Reset to default')
                reset_btn.connect(
                    'clicked', lambda _, k=key, e=editor, s=schema_field:
                    e.set_value(s.get('default'))
                )
                row.add_suffix(reset_btn)

                # If it's a toggle, make the row activatable
                if hasattr(editor, 'switch'):
                    row.set_activatable_widget(editor.switch)

            # Determine which group the setting belongs to
            if key in ['floating-mode', 'margin', 'corner-radius']:
                self.floating_group.add(row)
            elif 'popover' in key:
                self.popovers_group.add(row)
            else:
                self.general_group.add(row)

    def _on_combo_row_changed(self, row, pspec, key):
        """Handle ComboRow selection changes"""
        choices = GLOBAL_SCHEMA[key].get('choices', [])
        idx = row.get_selected()
        if 0 <= idx < len(choices):
            val = choices[idx]
            if self.on_change:
                self.on_change(key, val, None)

    def _on_field_change(self, key, value):
        """Handle field value changes"""
        if self.on_change:
            self.on_change(key, value, None)

    def refresh(self, config):
        """Update editors with new config values"""
        self.config = config
        for key, editor in self.editors.items():
            schema_field = GLOBAL_SCHEMA.get(key, {})
            value = config.get(key, schema_field.get('default'))
            editor.set_value(value)

    def get_values(self):
        """Get all current values"""
        return {
            key: editor.get_value() for key, editor in self.editors.items()
        }
