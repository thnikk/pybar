#!/usr/bin/python3 -u
"""
Description: Field editor widgets for settings UI
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

from settings.schema import FieldType


class FieldEditor(Gtk.Box):
    """Base class for field editors"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.key = key
        self.schema_field = schema_field
        self.on_change = on_change
        self._build_label()

    def _build_label(self):
        """Build the label and description"""
        label_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label = Gtk.Label(label=self.schema_field.get('label', self.key))
        label.set_halign(Gtk.Align.START)
        label_box.append(label)
        self.append(label_box)

        description = self.schema_field.get('description')
        if description:
            desc_label = Gtk.Label(label=description)
            desc_label.set_halign(Gtk.Align.START)
            desc_label.set_opacity(0.7)
            desc_label.set_wrap(True)
            desc_label.set_max_width_chars(40)
            self.append(desc_label)

    def get_value(self):
        """Override to return current value"""
        raise NotImplementedError

    def _emit_change(self):
        """Call the change callback"""
        if self.on_change:
            self.on_change(self.key, self.get_value())


class StringEditor(FieldEditor):
    """Editor for string fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)
        self.entry = Gtk.Entry()
        self.entry.set_text(str(value) if value is not None else '')
        self.entry.set_hexpand(True)
        self.entry.connect('changed', lambda _: self._emit_change())
        self.append(self.entry)

    def get_value(self):
        text = self.entry.get_text()
        return text if text else None


class IntegerEditor(FieldEditor):
    """Editor for integer fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)

        min_val = schema_field.get('min', -999999)
        max_val = schema_field.get('max', 999999)

        # Use a box with entry and spin buttons
        self.adjustment = Gtk.Adjustment(
            value=value if value is not None else schema_field.get('default', 0),
            lower=min_val,
            upper=max_val,
            step_increment=1,
            page_increment=10
        )
        self.spin = Gtk.SpinButton(adjustment=self.adjustment)
        self.spin.set_numeric(True)
        self.spin.set_hexpand(True)
        self.spin.connect('value-changed', lambda _: self._emit_change())

        # Add a "clear" option for nullable fields
        if schema_field.get('default') is None:
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            self.nullable = True
            self.clear_btn = Gtk.Button(label='Clear')
            self.clear_btn.connect('clicked', self._on_clear)
            box.append(self.spin)
            box.append(self.clear_btn)
            self.append(box)
            self._is_null = value is None
            if self._is_null:
                self.spin.set_sensitive(False)
        else:
            self.nullable = False
            self._is_null = False
            self.append(self.spin)

    def _on_clear(self, _):
        self._is_null = not self._is_null
        self.spin.set_sensitive(not self._is_null)
        self.clear_btn.set_label('Set' if self._is_null else 'Clear')
        self._emit_change()

    def get_value(self):
        if hasattr(self, 'nullable') and self.nullable and self._is_null:
            return None
        return int(self.spin.get_value())


class FloatEditor(FieldEditor):
    """Editor for float fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)

        min_val = schema_field.get('min', -999999.0)
        max_val = schema_field.get('max', 999999.0)
        step = schema_field.get('step', 0.1)

        self.adjustment = Gtk.Adjustment(
            value=value if value is not None else schema_field.get('default', 0),
            lower=min_val,
            upper=max_val,
            step_increment=step,
            page_increment=step * 10
        )
        self.spin = Gtk.SpinButton(adjustment=self.adjustment)
        self.spin.set_digits(2)
        self.spin.set_numeric(True)
        self.spin.set_hexpand(True)
        self.spin.connect('value-changed', lambda _: self._emit_change())
        self.append(self.spin)

    def get_value(self):
        return float(self.spin.get_value())


class BooleanEditor(FieldEditor):
    """Editor for boolean fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)
        self.switch = Gtk.Switch()
        self.switch.set_active(bool(value) if value is not None else False)
        self.switch.set_halign(Gtk.Align.START)
        self.switch.connect('state-set', lambda _, state: self._emit_change())
        self.append(self.switch)

    def get_value(self):
        return self.switch.get_active()


class ChoiceEditor(FieldEditor):
    """Editor for choice/dropdown fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)

        choices = schema_field.get('choices', [])
        self.choices = choices

        # Create string list for dropdown
        string_list = Gtk.StringList()
        for choice in choices:
            string_list.append(str(choice))

        self.dropdown = Gtk.DropDown(model=string_list)
        self.dropdown.set_hexpand(True)

        # Set initial selection
        if value in choices:
            self.dropdown.set_selected(choices.index(value))
        elif choices:
            self.dropdown.set_selected(0)

        self.dropdown.connect('notify::selected', lambda *_: self._emit_change())
        self.append(self.dropdown)

    def get_value(self):
        idx = self.dropdown.get_selected()
        if 0 <= idx < len(self.choices):
            return self.choices[idx]
        return None


class FileEditor(FieldEditor):
    """Editor for file path fields"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.entry = Gtk.Entry()
        self.entry.set_text(str(value) if value else '')
        self.entry.set_hexpand(True)
        self.entry.connect('changed', lambda _: self._emit_change())

        browse_btn = Gtk.Button(label='Browse...')
        browse_btn.connect('clicked', self._on_browse)

        box.append(self.entry)
        box.append(browse_btn)
        self.append(box)

    def _on_browse(self, _):
        dialog = Gtk.FileChooserNative(
            title='Select File',
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.connect('response', self._on_file_response)
        dialog.show()

    def _on_file_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            file = dialog.get_file()
            if file:
                self.entry.set_text(file.get_path())
        dialog.destroy()

    def get_value(self):
        text = self.entry.get_text()
        return text if text else None


def create_editor(key, schema_field, value, on_change):
    """Factory function to create appropriate editor for field type"""
    field_type = schema_field.get('type', FieldType.STRING)

    editors = {
        FieldType.STRING: StringEditor,
        FieldType.INTEGER: IntegerEditor,
        FieldType.FLOAT: FloatEditor,
        FieldType.BOOLEAN: BooleanEditor,
        FieldType.CHOICE: ChoiceEditor,
        FieldType.FILE: FileEditor,
    }

    editor_class = editors.get(field_type, StringEditor)
    return editor_class(key, schema_field, value, on_change)
