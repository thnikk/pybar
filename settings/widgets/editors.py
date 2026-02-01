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
        default_value = schema_field.get('default')
        if default_value is None:
            default_value = 0
        self.adjustment = Gtk.Adjustment(
            value=value if value is not None else default_value,
            lower=min_val,
            upper=max_val,
            step_increment=1,
            page_increment=10
        )
        self.spin = Gtk.SpinButton(adjustment=self.adjustment)
        self.spin.set_numeric(True)
        self.spin.set_hexpand(True)
        self.spin.connect('value-changed', lambda _: self._emit_change())
        
        # Disable scroll events on the spin button
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect('scroll', lambda *args: True)
        self.spin.add_controller(scroll_controller)

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

        default_value = schema_field.get('default')
        if default_value is None:
            default_value = 0.0
        self.adjustment = Gtk.Adjustment(
            value=value if value is not None else default_value,
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
        
        # Disable scroll events on the spin button
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.connect('scroll', lambda *args: True)
        self.spin.add_controller(scroll_controller)
        
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

        self.dropdown.connect(
            'notify::selected', lambda *_: self._emit_change())
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


class DictEditor(FieldEditor):
    """Editor for dict fields with dynamic key-value pairs"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)
        self.rows = []
        self.key_type = schema_field.get('key_type', FieldType.STRING)
        self.value_type = schema_field.get('value_type', FieldType.STRING)

        # scroll = Gtk.ScrolledWindow()
        # scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # scroll.set_min_content_height(150)
        # scroll.set_vexpand(True)

        self.rows_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.append(self.rows_box)
        # scroll.set_child(self.rows_box)
        # self.append(scroll)

        add_btn = Gtk.Button(label='+ Add Entry')
        add_btn.get_style_context().add_class('flat')
        add_btn.connect('clicked', self._on_add_row)
        self.append(add_btn)

        if value and isinstance(value, dict):
            for k, v in value.items():
                self._add_row(k, v)

    def _add_row(self, key='', value=''):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        key_schema = {'type': self.key_type}
        row.key_editor = create_editor(
            f'{self.key}_key_{len(self.rows)}',
            key_schema,
            key,
            lambda k, v: self._emit_change()
        )
        if hasattr(row.key_editor, 'entry'):
            row.key_editor.entry.set_width_chars(15)
        elif hasattr(row.key_editor, 'spin'):
            row.key_editor.spin.set_width_chars(10)

        value_schema = {'type': self.value_type}
        row.value_editor = create_editor(
            f'{self.key}_value_{len(self.rows)}',
            value_schema,
            value,
            lambda k, v: self._emit_change()
        )
        row.value_editor.set_hexpand(True)

        delete_btn = Gtk.Button(label='-')
        delete_btn.get_style_context().add_class('flat')
        delete_btn.connect('clicked', lambda _: self._remove_row(row))

        row.append(row.key_editor)
        row.append(row.value_editor)
        row.append(delete_btn)

        self.rows_box.append(row)
        self.rows.append(row)

    def _remove_row(self, row):
        if row in self.rows:
            self.rows_box.remove(row)
            self.rows.remove(row)
            self._emit_change()

    def _on_add_row(self, _):
        self._add_row('', '')
        self._emit_change()

    def get_value(self):
        result = {}
        for row in self.rows:
            key = row.key_editor.get_value()
            if key is None or (isinstance(key, str) and not key.strip()):
                continue
            result[key] = row.value_editor.get_value()
        return result if result else None


class ListEditor(FieldEditor):
    """Editor for list fields with dynamic items"""

    def __init__(self, key, schema_field, value, on_change):
        super().__init__(key, schema_field, value, on_change)
        self.rows = []
        self.item_type = schema_field.get('item_type', FieldType.STRING)

        # scroll = Gtk.ScrolledWindow()
        # scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # scroll.set_min_content_height(150)
        # scroll.set_vexpand(True)

        self.rows_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.append(self.rows_box)
        # scroll.set_child(self.rows_box)
        # self.append(scroll)

        add_btn = Gtk.Button(label='+ Add Item')
        add_btn.get_style_context().add_class('flat')
        add_btn.connect('clicked', self._on_add_item)
        self.append(add_btn)

        if value and isinstance(value, list):
            for item in value:
                self._add_item(item)

    def _add_item(self, value=''):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        item_schema = {'type': self.item_type}
        row.item_editor = create_editor(
            f'{self.key}_item_{len(self.rows)}',
            item_schema,
            value,
            lambda k, v: self._emit_change()
        )
        row.item_editor.set_hexpand(True)

        up_btn = Gtk.Button(label='▲')
        up_btn.get_style_context().add_class('flat')
        up_btn.connect('clicked', lambda _: self._move_item_up(row))

        down_btn = Gtk.Button(label='▼')
        down_btn.get_style_context().add_class('flat')
        down_btn.connect('clicked', lambda _: self._move_item_down(row))

        delete_btn = Gtk.Button(label='-')
        delete_btn.get_style_context().add_class('flat')
        delete_btn.connect('clicked', lambda _: self._remove_item(row))

        row.append(row.item_editor)
        row.append(up_btn)
        row.append(down_btn)
        row.append(delete_btn)

        self.rows_box.append(row)
        self.rows.append(row)

    def _remove_item(self, row):
        if row in self.rows:
            self.rows_box.remove(row)
            self.rows.remove(row)
            self._emit_change()

    def _move_item_up(self, row):
        index = self.rows.index(row)
        if index > 0:
            prev_row = self.rows[index - 1]
            self.rows_box.remove(row)
            self.rows_box.insert_child_after(row, prev_row)
            self.rows.remove(row)
            self.rows.insert(index - 1, row)
            self._emit_change()

    def _move_item_down(self, row):
        index = self.rows.index(row)
        if index < len(self.rows) - 1:
            next_row = self.rows[index + 1]
            self.rows_box.remove(next_row)
            self.rows_box.insert_child_after(next_row, row)
            self.rows.remove(next_row)
            self.rows.insert(index, next_row)
            self._emit_change()

    def _on_add_item(self, _):
        self._add_item('')
        self._emit_change()

    def get_value(self):
        result = []
        for row in self.rows:
            value = row.item_editor.get_value()
            result.append(value)
        return result if result else None


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
        FieldType.DICT: DictEditor,
        FieldType.LIST: ListEditor,
    }

    editor_class = editors.get(field_type, StringEditor)
    return editor_class(key, schema_field, value, on_change)
