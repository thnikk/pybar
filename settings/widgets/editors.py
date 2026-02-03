#!/usr/bin/python3 -u
"""
Description: Field editor widgets for settings UI
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw  # noqa

from settings.schema import FieldType


class FieldEditor(Gtk.Box):
    """Base class for field editors"""

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.key = key
        self.schema_field = schema_field
        self.on_change = on_change
        if show_label:
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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)
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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)

        min_val = schema_field.get('min', -999999)
        max_val = schema_field.get('max', 999999)

        # Use a box with entry and spin buttons
        default_value = schema_field.get('default')
        if default_value is None:
            default_value = 0
        self.adjustment = Gtk.Adjustment(
            value=int(value) if value is not None else int(default_value),
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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)

        min_val = schema_field.get('min', -999999.0)
        max_val = schema_field.get('max', 999999.0)
        step = schema_field.get('step', 0.1)

        default_value = schema_field.get('default')
        if default_value is None:
            default_value = 0.0
        self.adjustment = Gtk.Adjustment(
            value=float(value) if value is not None else float(default_value),
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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)
        self.switch = Gtk.Switch()
        self.switch.set_active(bool(value) if value is not None else False)
        self.switch.set_halign(Gtk.Align.START)
        self.switch.connect('state-set', lambda _, state: self._emit_change())
        self.append(self.switch)

    def get_value(self):
        return self.switch.get_active()


class ChoiceEditor(FieldEditor):
    """Editor for choice/dropdown fields"""

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)

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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)

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

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label=True)
        self.rows = []
        self.key_type = schema_field.get('key_type', FieldType.STRING)
        self.value_type = schema_field.get('value_type', FieldType.STRING)
        self.nested_schema = schema_field.get('schema')
        self.has_nested = self.nested_schema is not None

        # scroll = Gtk.ScrolledWindow()
        # scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        # scroll.set_min_content_height(150)
        # scroll.set_vexpand(True)

        self.rows_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=5)
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
        if self.has_nested:
            self._add_nested_row(key, value)
        else:
            self._add_simple_row(key, value)

    def _add_nested_row(self, key='', value=''):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)

        key_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        key_schema = {'type': self.key_type}
        key_row.key_editor = create_editor(
            f'{self.key}_key_{len(self.rows)}',
            key_schema,
            key,
            lambda k, v: self._emit_change(),
            show_label=False
        )
        if hasattr(key_row.key_editor, 'entry'):
            key_row.key_editor.entry.set_width_chars(15)
        elif hasattr(key_row.key_editor, 'spin'):
            key_row.key_editor.spin.set_width_chars(10)

        delete_btn = Gtk.Button(label='-')
        delete_btn.get_style_context().add_class('flat')
        delete_btn.connect('clicked', lambda _: self._remove_row(container))

        key_row.append(key_row.key_editor)
        key_row.append(delete_btn)

        container.append(key_row)

        nested_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        nested_box.set_margin_start(10)
        nested_box.set_margin_top(10)
        nested_box.set_margin_bottom(10)
        nested_box.set_margin_end(10)
        nested_frame = Gtk.Frame()
        nested_frame.get_style_context().add_class('view')
        nested_frame.set_child(nested_box)

        container.nested_editors = []

        add_nested_btn = Gtk.Button(label='+ Add Entry')
        add_nested_btn.get_style_context().add_class('flat')
        add_nested_btn.connect(
            'clicked', lambda _, nb=nested_box, c=container:
            self._add_nested_entry(nb, '', '', c))
        nested_box.append(add_nested_btn)
        container.add_nested_btn = add_nested_btn

        if value and isinstance(value, dict):
            for nk, nv in value.items():
                self._add_nested_entry(nested_box, nk, nv, container)

        container.append(nested_frame)
        self.rows_box.append(container)
        self.rows.append(container)

    def _add_nested_entry(self, parent_box, key='', value='', container=None):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        key_schema = {'type': self.nested_schema.get('key_type', FieldType.STRING)}
        row.key_editor = create_editor(
            f'nested_key_{len(container.nested_editors)}',
            key_schema,
            key,
            lambda k, v: self._emit_change(),
            show_label=False
        )
        if hasattr(row.key_editor, 'entry'):
            row.key_editor.entry.set_width_chars(15)
        elif hasattr(row.key_editor, 'spin'):
            row.key_editor.spin.set_width_chars(10)

        nested_value_type = self.nested_schema.get('value_type', FieldType.STRING)
        value_schema = {'type': nested_value_type}
        row.value_editor = create_editor(
            f'nested_value_{len(container.nested_editors)}',
            value_schema,
            value,
            lambda k, v: self._emit_change(),
            show_label=False
        )
        row.value_editor.set_hexpand(True)

        delete_btn = Gtk.Button(label='-')
        delete_btn.get_style_context().add_class('flat')
        delete_btn.connect('clicked', lambda _: self._remove_nested_entry(row, parent_box))

        row.append(row.key_editor)
        row.append(row.value_editor)
        row.append(delete_btn)

        parent_box.prepend(row)
        container.nested_editors.append(row)

    def _remove_nested_entry(self, row, parent_box):
        if parent_box:
            parent_box.remove(row)
        if hasattr(parent_box, 'get_parent'):
            container = parent_box.get_parent()
            if hasattr(container, 'nested_editors') and row in container.nested_editors:
                container.nested_editors.remove(row)
        self._emit_change()

    def _add_simple_row(self, key='', value=''):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        key_schema = {'type': self.key_type}
        row.key_editor = create_editor(
            f'{self.key}_key_{len(self.rows)}',
            key_schema,
            key,
            lambda k, v: self._emit_change(),
            show_label=False
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
            lambda k, v: self._emit_change(),
            show_label=False
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
        if self.has_nested:
            result = {}
            for container in self.rows:
                key_row = container.get_first_child()
                key = key_row.key_editor.get_value()
                if key is None or (isinstance(key, str) and not key.strip()):
                    continue
                nested_value = {}
                if hasattr(container, 'nested_editors'):
                    for nested_row in container.nested_editors:
                        n_key = nested_row.key_editor.get_value()
                        if n_key is None or (isinstance(n_key, str) and not n_key.strip()):
                            continue
                        nested_value[n_key] = nested_row.value_editor.get_value()
                result[key] = nested_value if nested_value else {}
            return result if result else None
        else:
            result = {}
            for row in self.rows:
                key = row.key_editor.get_value()
                if key is None or (isinstance(key, str) and not key.strip()):
                    continue
                result[key] = row.value_editor.get_value()
            return result if result else None


class ListEditor(FieldEditor):
    """Editor for list fields with dynamic items"""

    def __init__(self, key, schema_field, value, on_change, show_label=True):
        super().__init__(key, schema_field, value, on_change, show_label)
        self.item_type = schema_field.get('item_type', FieldType.STRING)
        self.choices = schema_field.get('choices', [])
        self.unique = schema_field.get('unique', False)
        self.sortable = schema_field.get('sortable', True)

        self.values = list(value) if isinstance(value, list) else []

        self.list_box = Gtk.ListBox()
        self.list_box.add_css_class('boxed-list')
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.append(self.list_box)

        # Add Controls
        add_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_box.set_margin_top(6)

        if self.choices:
            label = schema_field.get('choices_label', 'Add...')
            strings = [label] + [str(c) for c in self.choices]
            self.dropdown = Gtk.DropDown.new_from_strings(strings)
            self.dropdown.connect('notify::selected', self._on_choice_selected)
            add_box.append(self.dropdown)

        self.entry = Gtk.Entry(placeholder_text="Enter value...")
        self.entry.set_hexpand(True)
        self.entry.connect('activate', lambda _: self._on_manual_add())
        add_box.append(self.entry)

        add_btn = Gtk.Button(icon_name="list-add-symbolic")
        add_btn.add_css_class("flat")
        add_btn.connect('clicked', lambda _: self._on_manual_add())
        add_box.append(add_btn)

        self.append(add_box)
        self._refresh_list()

    def _refresh_list(self):
        """Rebuild the list box rows"""
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)

        for i, val in enumerate(self.values):
            row = Adw.ActionRow()
            if self.item_type == FieldType.STRING:
                row.set_title(str(val))
            else:
                item_editor = create_editor(
                    f'{self.key}_item_{i}',
                    {'type': self.item_type},
                    val,
                    lambda k, v, idx=i: self._on_item_change(idx, v),
                    show_label=False
                )
                row.set_child(item_editor)

            suffix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

            if self.sortable:
                up_btn = Gtk.Button(icon_name="go-up-symbolic")
                up_btn.add_css_class("flat")
                up_btn.connect('clicked', lambda _, idx=i: self._move_item(idx, -1))
                suffix_box.append(up_btn)

                down_btn = Gtk.Button(icon_name="go-down-symbolic")
                down_btn.add_css_class("flat")
                down_btn.connect('clicked', lambda _, idx=i: self._move_item(idx, 1))
                suffix_box.append(down_btn)

            delete_btn = Gtk.Button(icon_name="list-remove-symbolic")
            delete_btn.add_css_class("flat")
            delete_btn.connect('clicked', lambda _, idx=i: self._remove_item(idx))
            suffix_box.append(delete_btn)

            row.add_suffix(suffix_box)
            self.list_box.append(row)

        self.list_box.set_visible(len(self.values) > 0)

    def _on_item_change(self, index, value):
        if 0 <= index < len(self.values):
            self.values[index] = value
            self._emit_change()

    def _on_choice_selected(self, dropdown, _):
        idx = dropdown.get_selected()
        if idx > 0:
            val = self.choices[idx - 1]
            if self._add_value(val):
                dropdown.set_selected(0)

    def _on_manual_add(self):
        val = self.entry.get_text().strip()
        if val:
            # Type conversion if needed
            if self.item_type == FieldType.INTEGER:
                try: val = int(val)
                except ValueError: return
            elif self.item_type == FieldType.FLOAT:
                try: val = float(val)
                except ValueError: return
                
            if self._add_value(val):
                self.entry.set_text("")

    def _add_value(self, val):
        if self.unique and val in self.values:
            return False
        self.values.append(val)
        self._refresh_list()
        self._emit_change()
        return True

    def _remove_item(self, index):
        if 0 <= index < len(self.values):
            self.values.pop(index)
            self._refresh_list()
            self._emit_change()

    def _move_item(self, index, delta):
        new_idx = index + delta
        if 0 <= new_idx < len(self.values):
            self.values[index], self.values[new_idx] = \
                self.values[new_idx], self.values[index]
            self._refresh_list()
            self._emit_change()

    def get_value(self):
        return self.values if self.values else None



def create_editor(key, schema_field, value, on_change, show_label=True):
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
    return editor_class(key, schema_field, value, on_change, show_label)
