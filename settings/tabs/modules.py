#!/usr/bin/python3 -u
"""
Description: Modules settings tab with libadwaita styling
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, GObject, Graphene, Adw

from settings.widgets.editors import create_editor
from settings.schema import get_module_schema
import module as mod


class ModuleChip(Gtk.Box):
    """A draggable chip representing a module using Adwaita styling"""

    def __init__(self, name, on_select, on_remove, section, config=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.name = name
        self.section = section
        self.on_select = on_select
        self.on_remove = on_remove

        self.add_css_class('module-chip')
        # self.set_margin_top(4)
        # self.set_margin_bottom(4)
        # self.set_margin_start(4)
        # self.set_margin_end(4)

        module_config = (
            config.get('modules', {}).get(name, {}) if config else {}
        )
        module_type = module_config.get('type', name)

        if module_type != name:
            self.set_tooltip_text(f"Type: {module_type}")

        label = Gtk.Label(label=name)
        label.add_css_class('caption')
        self.append(label)

        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('window-close-symbolic')
        remove_btn.add_css_class('flat')
        remove_btn.add_css_class('circular')
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.connect('clicked', self._on_remove_clicked)
        self.append(remove_btn)

        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect('released', self._on_clicked)
        self.add_controller(click)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect('prepare', self._on_drag_prepare)
        drag_source.connect('drag-begin', self._on_drag_begin)
        drag_source.connect('drag-end', self._on_drag_end)
        self.add_controller(drag_source)

    def _on_clicked(self, gesture, n_press, x, y):
        if self.on_select:
            self.on_select(self.name)

    def _on_remove_clicked(self, btn):
        if self.on_remove:
            self.on_remove(self)

    def _on_drag_prepare(self, source, x, y):
        data = f"{self.section.section_name}:{self.name}"
        return Gdk.ContentProvider.new_for_value(data)

    def _on_drag_begin(self, source, drag):
        icon = Gtk.DragIcon.get_for_drag(drag)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        label = Gtk.Label(label=self.name)
        box.append(label)
        box.add_css_class('card')
        icon.set_child(box)
        self.set_opacity(0.3)

    def _on_drag_end(self, source, drag, delete_data):
        self.set_opacity(1.0)


class DropIndicator(Gtk.Box):
    """Visual indicator showing where a module will be dropped"""

    def __init__(self):
        super().__init__()
        self.set_size_request(3, -1)
        self.add_css_class('drop-indicator')


class SectionRow(Gtk.Box):
    """Box for a bar section with drag-drop support"""

    def __init__(
        self, section_name, modules, on_select, on_change,
        all_sections, config=None
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.section_name = section_name
        self.on_select = on_select
        self.on_change = on_change
        self.all_sections = all_sections
        self.config = config
        self._drop_index = -1
        self._drop_indicator = None

        self.set_margin_top(6)
        self.set_margin_bottom(6)

        display_name = section_name.replace('modules-', '').title()
        
        label = Gtk.Label(label=display_name)
        label.set_halign(Gtk.Align.START)
        label.add_css_class('heading')
        self.append(label)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.NEVER)
        scroll.set_hexpand(True)
        scroll.set_min_content_height(48)
        scroll.add_css_class('section-scroll')

        frame = Gtk.Frame()
        frame.add_css_class('section-frame')
        frame.set_hexpand(True)

        self.chips_box = Gtk.FlowBox()
        self.chips_box.set_valign(Gtk.Align.START)
        self.chips_box.set_halign(Gtk.Align.FILL)
        self.chips_box.set_homogeneous(False)
        self.chips_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.chips_box.set_max_children_per_line(100)
        self.chips_box.set_column_spacing(4)
        self.chips_box.set_row_spacing(4)
        self.chips_box.set_margin_top(4)
        self.chips_box.set_margin_bottom(4)
        self.chips_box.set_margin_start(4)
        self.chips_box.set_margin_end(4)

        self.placeholder = Gtk.Label(label='Drop modules here')
        self.placeholder.add_css_class('dim-label')
        self.placeholder.set_valign(Gtk.Align.CENTER)
        self.placeholder.set_margin_start(8)
        self.placeholder.set_margin_end(8)

        overlay = Gtk.Overlay()
        overlay.set_child(self.chips_box)
        overlay.add_overlay(self.placeholder)

        frame.set_child(overlay)
        scroll.set_child(frame)
        self.append(scroll)

        for name in modules:
            self._add_chip(name)

        self._update_placeholder()

        drop_target = Gtk.DropTarget.new(
            GObject.TYPE_STRING, Gdk.DragAction.MOVE
        )
        drop_target.connect('drop', self._on_drop)
        drop_target.connect('enter', self._on_enter)
        drop_target.connect('motion', self._on_motion)
        drop_target.connect('leave', self._on_leave)
        scroll.add_controller(drop_target)

        self._frame = frame
        self._overlay = overlay
        self._scroll = scroll

    def _add_chip(self, name, position=-1):
        chip = ModuleChip(
            name, self.on_select, self._on_remove, self, self.config
        )
        if position < 0 or position >= len(self._get_chips()):
            self.chips_box.append(chip)
        else:
            self.chips_box.insert(chip, position)
        self._update_placeholder()

    def _on_remove(self, chip):
        self.chips_box.remove(chip)
        self._emit_change()
        self._update_placeholder()

    def _update_placeholder(self):
        has_chips = len(self._get_chips()) > 0
        self.placeholder.set_visible(not has_chips)

    def _get_chips(self, exclude_indicator=False):
        """Get all module chips"""
        chips = []
        child = self.chips_box.get_first_child()
        while child:
            if isinstance(child, Gtk.FlowBoxChild):
                chip_child = child.get_child()
                if isinstance(chip_child, ModuleChip):
                    chips.append(chip_child)
                elif exclude_indicator and isinstance(
                    chip_child, DropIndicator
                ):
                    pass
            child = child.get_next_sibling()
        return chips

    def _get_drop_index(self, x, y):
        """Calculate drop index based on x, y coordinates"""
        chips = self._get_chips(exclude_indicator=True)
        if not chips:
            return 0

        # First, find which row the cursor is on
        cursor_row_chips = []
        row_tolerance = 10  # pixels
        
        for i, chip in enumerate(chips):
            child = chip.get_parent()
            if not child:
                continue
            
            success, bounds = child.compute_bounds(self.chips_box)
            if not success:
                continue
            
            chip_y = bounds.get_y()
            chip_height = bounds.get_height()
            
            # Check if cursor y is within this chip's row
            if chip_y - row_tolerance <= y <= chip_y + chip_height + row_tolerance:
                cursor_row_chips.append((i, chip, bounds))
        
        # If no chips in cursor row, find closest row
        if not cursor_row_chips:
            min_row_distance = float('inf')
            target_y = None
            
            for chip in chips:
                child = chip.get_parent()
                if not child:
                    continue
                
                success, bounds = child.compute_bounds(self.chips_box)
                if not success:
                    continue
                
                chip_y = bounds.get_y()
                chip_height = bounds.get_height()
                chip_center_y = chip_y + chip_height / 2
                
                row_distance = abs(y - chip_center_y)
                if row_distance < min_row_distance:
                    min_row_distance = row_distance
                    target_y = chip_y
            
            # Get all chips at the target y position
            for i, chip in enumerate(chips):
                child = chip.get_parent()
                if not child:
                    continue
                
                success, bounds = child.compute_bounds(self.chips_box)
                if not success:
                    continue
                
                if abs(bounds.get_y() - target_y) < row_tolerance:
                    cursor_row_chips.append((i, chip, bounds))
        
        if not cursor_row_chips:
            return len(chips)
        
        # Now find the best position within the row
        min_distance = float('inf')
        best_index = cursor_row_chips[-1][0] + 1  # Default to end of row
        
        for i, chip, bounds in cursor_row_chips:
            chip_center_x = bounds.get_x() + bounds.get_width() / 2
            distance = abs(x - chip_center_x)
            
            if distance < min_distance:
                min_distance = distance
                if x < chip_center_x:
                    best_index = i
                else:
                    best_index = i + 1
        
        return best_index

    def _auto_scroll(self, x):
        """Auto-scroll when dragging near edges"""
        adj = self._scroll.get_hadjustment()
        scroll_width = self._scroll.get_width()
        edge_size = 40
        scroll_speed = 8

        if x < edge_size:
            adj.set_value(adj.get_value() - scroll_speed)
        elif x > scroll_width - edge_size:
            adj.set_value(adj.get_value() + scroll_speed)

    def _on_enter(self, target, x, y):
        self._frame.add_css_class('drop-target')
        return Gdk.DragAction.MOVE

    def _on_motion(self, target, x, y):
        self._auto_scroll(x)
        new_index = self._get_drop_index(x, y)
        if new_index != self._drop_index:
            self._drop_index = new_index
            self._update_drop_indicator()
        return Gdk.DragAction.MOVE

    def _on_leave(self, target):
        self._frame.remove_css_class('drop-target')
        self._remove_drop_indicator()
        self._drop_index = -1

    def _update_drop_indicator(self):
        """Show drop indicator at current drop position"""
        chips = self._get_chips()

        if not chips:
            if self._drop_indicator:
                self._drop_indicator.set_visible(False)
            return

        # Create drop indicator as overlay if it doesn't exist
        if not self._drop_indicator:
            self._drop_indicator = Gtk.Box()
            self._drop_indicator.add_css_class('drop-indicator-overlay')
            self._drop_indicator.set_size_request(4, -1)
            self._drop_indicator.set_halign(Gtk.Align.START)
            self._drop_indicator.set_valign(Gtk.Align.START)
            self._overlay.add_overlay(self._drop_indicator)
        
        self._drop_indicator.set_visible(True)
        
        # Calculate position based on drop index
        if self._drop_index >= len(chips):
            target_chip = chips[-1]
            after_chip = True
        else:
            target_chip = chips[self._drop_index]
            after_chip = False
        
        target_child = target_chip.get_parent()
        if not target_child:
            return
        
        # Get position of target chip relative to overlay
        success, bounds = target_child.compute_bounds(self._overlay)
        if not success:
            return
        
        if after_chip:
            x = bounds.get_x() + bounds.get_width() + 2
        else:
            x = bounds.get_x() - 5
        
        y = bounds.get_y()
        height = bounds.get_height()
        
        self._drop_indicator.set_size_request(4, int(height))
        self._drop_indicator.set_margin_start(int(x))
        self._drop_indicator.set_margin_top(int(y))

    def _remove_drop_indicator(self):
        """Remove the drop indicator"""
        if self._drop_indicator:
            self._drop_indicator.set_visible(False)

    def _on_drop(self, target, value, x, y):
        drop_index = self._drop_index
        self._frame.remove_css_class('drop-target')
        self._remove_drop_indicator()
        self._drop_index = -1

        parts = value.split(':', 1)
        if len(parts) != 2:
            module_name = value
            source_section = None
        else:
            source_section, module_name = parts

        if source_section == 'available':
            source_section = None

        current_index = -1
        if source_section == self.section_name:
            chips = self._get_chips()
            for i, chip in enumerate(chips):
                if chip.name == module_name:
                    current_index = i
                    break

        if source_section and source_section != self.section_name:
            if source_section in self.all_sections:
                self.all_sections[source_section].remove_module_by_name(
                    module_name
                )
        elif source_section == self.section_name and current_index >= 0:
            self.remove_module_by_name(module_name, emit=False)
            if current_index < drop_index:
                drop_index -= 1

        for chip in self._get_chips():
            if chip.name == module_name:
                return False

        if drop_index < 0:
            drop_index = len(self._get_chips())
        self._add_chip(module_name, drop_index)
        self._emit_change()
        return True

    def remove_module_by_name(self, module_name, emit=True):
        for chip in self._get_chips():
            if chip.name == module_name:
                self.chips_box.remove(chip)
                if emit:
                    self._emit_change()
                self._update_placeholder()
                return True
        return False

    def refresh(self, modules, config=None):
        """Clear and re-add module chips"""
        if config:
            self.config = config
        while child := self.chips_box.get_first_child():
            self.chips_box.remove(child)
        for name in modules:
            self._add_chip(name)
        self._update_placeholder()

    def get_modules(self):
        return [chip.name for chip in self._get_chips()]

    def _emit_change(self):
        if self.on_change:
            self.on_change()


class AvailableModulesGroup(Adw.PreferencesGroup):
    """Adwaita preference group for available modules"""

    def __init__(self, on_add, sections, config=None):
        super().__init__()
        self.set_title('Add Module')
        self.set_description(
            'Select a module type and drag it to a section or click the + '
            'button'
        )
        self.on_add = on_add
        self.sections = sections
        self.config = config

        mod.discover_modules()
        all_modules = sorted(mod._module_map.keys())

        # Create a horizontal box for the dropdown and button
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        controls_box.set_spacing(8)
        controls_box.set_halign(Gtk.Align.START)
        controls_box.set_margin_top(8)
        controls_box.set_margin_bottom(8)
        controls_box.set_margin_start(8)
        controls_box.set_margin_end(8)

        # Create a box with dotted border to indicate draggability
        drag_indicator = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        drag_indicator.add_css_class('drag-indicator')
        drag_indicator.set_hexpand(False)

        # Create dropdown
        dropdown = Gtk.DropDown()
        string_list = Gtk.StringList()
        for name in all_modules:
            string_list.append(name)
        dropdown.set_model(string_list)
        dropdown.set_size_request(200, -1)

        drag_source = Gtk.DragSource()
        drag_source.set_actions(Gdk.DragAction.MOVE)
        drag_source.connect(
            'prepare', lambda s, x, y: self._drag_prepare(dropdown)
        )
        drag_source.connect(
            'drag-begin', lambda s, d: self._drag_begin(d, dropdown)
        )
        dropdown.add_controller(drag_source)

        drag_indicator.append(dropdown)
        controls_box.append(drag_indicator)

        # Create add button
        add_btn = Gtk.Button()
        add_btn.set_icon_name('list-add-symbolic')
        add_btn.set_tooltip_text('Add module')
        add_btn.connect('clicked', lambda b: self._on_add_clicked_btn(dropdown))
        controls_box.append(add_btn)

        self.add(controls_box)

    def _drag_prepare(self, combo_row):
        selected = combo_row.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return None
        model = combo_row.get_model()
        name = model.get_string(selected)
        return Gdk.ContentProvider.new_for_value(f"available:{name}")

    def _drag_begin(self, drag, combo_row):
        selected = combo_row.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return
        model = combo_row.get_model()
        name = model.get_string(selected)

        icon = Gtk.DragIcon.get_for_drag(drag)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class('module-chip')
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(4)
        box.set_margin_end(4)
        label = Gtk.Label(label=name)
        label.add_css_class('caption')
        box.append(label)
        icon.set_child(box)

    def _on_add_clicked_btn(self, combo_row):
        selected = combo_row.get_selected()
        if selected == Gtk.INVALID_LIST_POSITION:
            return
        model = combo_row.get_model()
        module_type = model.get_string(selected)
        self._on_add_clicked(module_type)

    def _on_add_clicked(self, module_type):
        dialog = Adw.MessageDialog.new(None)
        dialog.set_heading(f"Add {module_type}")
        dialog.set_body("Choose a section and name for the module")

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("left", "Add to Left")
        dialog.add_response("center", "Add to Center")
        dialog.add_response("right", "Add to Right")

        dialog.set_default_response("center")
        dialog.set_close_response("cancel")

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)

        name_row = Adw.EntryRow()
        name_row.set_title("Instance Name")
        name_row.set_text(module_type)
        content_box.append(name_row)

        error_label = Gtk.Label()
        error_label.add_css_class('error')
        error_label.set_visible(False)
        content_box.append(error_label)

        dialog.set_extra_child(content_box)

        def on_response(dlg, response):
            if response == "cancel":
                return

            section_map = {
                "left": "modules-left",
                "center": "modules-center",
                "right": "modules-right"
            }
            section_name = section_map.get(response)
            if not section_name:
                return

            instance_name = name_row.get_text().strip()

            if not instance_name:
                error_label.set_label("Name cannot be empty")
                error_label.set_visible(True)
                name_row.add_css_class('error')
                return

            if not self._is_name_globally_unique(instance_name):
                error_label.set_label(f"'{instance_name}' already exists")
                error_label.set_visible(True)
                name_row.add_css_class('error')
                return

            if section_name in self.sections:
                section = self.sections[section_name]

                if instance_name != module_type and self.config is not None:
                    modules_config = self.config.setdefault('modules', {})
                    modules_config[instance_name] = {'type': module_type}

                section._add_chip(instance_name)
                section._emit_change()

        dialog.connect('response', on_response)
        dialog.present()

    def _is_name_globally_unique(self, name):
        """Check if name is unique across all sections"""
        for section in self.sections.values():
            if name in section.get_modules():
                return False
        return True


class ModuleSettingsGroup(Adw.PreferencesGroup):
    """Adwaita preference group for module settings"""

    def __init__(self):
        super().__init__()
        self.set_title('Module Settings')
        self.set_description('Select a module to configure')
        self.selected_module = None
        self.config = None
        self.on_change = None
        self.sections = None
        self._current_rows = []

        # Vertical box for settings with spacing
        self._content_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=20
        )
        self.add(self._content_box)

        # Initial placeholder
        placeholder_row = Adw.ActionRow()
        placeholder_label = Gtk.Label(
            label='Click a module to configure its settings'
        )
        placeholder_label.set_opacity(0.5)
        placeholder_label.set_vexpand(True)
        placeholder_label.set_valign(Gtk.Align.CENTER)
        placeholder_label.set_margin_top(24)
        placeholder_label.set_margin_bottom(24)
        placeholder_row.set_child(placeholder_label)
        self._content_box.append(placeholder_row)
        self._current_rows.append(placeholder_row)

    def show_module_settings(
        self, module_name, config, on_change, sections
    ):
        """Show settings for a specific module"""
        self.selected_module = module_name
        self.config = config
        self.on_change = on_change
        self.sections = sections

        # Remove all previously added rows
        for row in self._current_rows:
            self._content_box.remove(row)
        self._current_rows.clear()

        module_config = config.get('modules', {}).get(module_name, {})
        module_type = module_config.get('type', module_name)

        mod.discover_modules()
        module_class = mod._module_map.get(module_type)

        if not module_class:
            # Re-add placeholder for no settings
            placeholder_row = Adw.ActionRow()
            placeholder_label = Gtk.Label(
                label=f'No settings available for {module_name}'
            )
            placeholder_label.set_opacity(0.5)
            placeholder_label.set_vexpand(True)
            placeholder_label.set_valign(Gtk.Align.CENTER)
            placeholder_label.set_margin_top(24)
            placeholder_label.set_margin_bottom(24)
            placeholder_row.set_child(placeholder_label)
            self._content_box.append(placeholder_row)
            self._current_rows.append(placeholder_row)
            return

        schema = get_module_schema(module_class)

        header_text = (
            f"{module_name} ({module_type})"
            if module_type != module_name else module_name.title()
        )

        name_row = Adw.EntryRow()
        name_row.set_title("Instance Name")
        name_row.set_text(module_name)
        name_row.add_suffix(
            self._create_apply_button(module_name, module_type, name_row)
        )
        name_row.connect(
            'changed', lambda r: self._on_name_changed(r, module_name)
        )
        self._content_box.append(name_row)
        self._current_rows.append(name_row)
        self._name_row = name_row
        self._name_apply_btn = name_row.get_last_child()

        if schema:
            for key, schema_field in schema.items():
                value = module_config.get(key, schema_field.get('default'))
                editor = create_editor(
                    key, schema_field, value,
                    lambda k, v, m=module_name: self._on_module_field_change(
                        m, k, v
                    )
                )
                self._content_box.append(editor)
                self._current_rows.append(editor)
        else:
            info_row = Adw.ActionRow()
            info_row.set_title("No configurable options")
            info_row.set_subtitle(f"Module type: {module_type}")
            self._content_box.append(info_row)
            self._current_rows.append(info_row)

    def _create_apply_button(self, module_name, module_type, entry_row):
        """Create apply button for name changes"""
        btn = Gtk.Button(label="Apply")
        btn.add_css_class('suggested-action')
        btn.set_sensitive(False)
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect(
            'clicked',
            lambda b: self._apply_rename(module_name, module_type, entry_row)
        )
        return btn

    def _on_name_changed(self, entry_row, old_name):
        """Handle name entry changes"""
        new_name = entry_row.get_text().strip()

        if new_name == old_name:
            self._name_apply_btn.set_sensitive(False)
            entry_row.remove_css_class('error')
            return

        if not new_name:
            entry_row.add_css_class('error')
            self._name_apply_btn.set_sensitive(False)
            return

        if not self._is_name_unique(new_name, exclude=old_name):
            entry_row.add_css_class('error')
            self._name_apply_btn.set_sensitive(False)
            return

        entry_row.remove_css_class('error')
        self._name_apply_btn.set_sensitive(True)

    def _apply_rename(self, old_name, module_type, entry_row):
        """Apply module rename"""
        new_name = entry_row.get_text().strip()

        if new_name == old_name:
            return

        if not new_name or not self._is_name_unique(
            new_name, exclude=old_name
        ):
            return

        source_section = None
        source_chip = None
        for section in self.sections.values():
            for chip in section._get_chips():
                if chip.name == old_name:
                    source_section = section
                    source_chip = chip
                    break
            if source_section:
                break

        if not source_section or not source_chip:
            return

        source_chip.name = new_name
        label = source_chip.get_first_child()
        if isinstance(label, Gtk.Label):
            label.set_label(new_name)
        if module_type != new_name:
            source_chip.set_tooltip_text(f"Type: {module_type}")
        else:
            source_chip.set_tooltip_text(None)

        modules_config = self.config.setdefault('modules', {})
        old_config = modules_config.pop(old_name, {})

        if module_type != new_name:
            old_config['type'] = module_type
        elif 'type' in old_config and old_config['type'] == new_name:
            del old_config['type']

        modules_config[new_name] = old_config

        self.selected_module = new_name

        if self.on_change:
            layout = {
                section_name: section.get_modules()
                for section_name, section in self.sections.items()
            }
            self.on_change('__layout__', layout, None)

        self.show_module_settings(new_name, self.config, self.on_change, self.sections)

    def _is_name_unique(self, name, exclude=None):
        """Check if name is unique across all sections"""
        if not self.sections:
            return True
        for section in self.sections.values():
            for module_name in section.get_modules():
                if module_name == name and module_name != exclude:
                    return False
        return True

    def _on_module_field_change(self, module_name, key, value):
        if self.on_change:
            self.on_change(key, value, module_name)

    def reset(self):
        """Revert to initial placeholder"""
        self.selected_module = None
        for row in self._current_rows:
            self._content_box.remove(row)
        self._current_rows.clear()

        placeholder_row = Adw.ActionRow()
        placeholder_label = Gtk.Label(
            label='Click a module to configure its settings'
        )
        placeholder_label.set_opacity(0.5)
        placeholder_label.set_vexpand(True)
        placeholder_label.set_valign(Gtk.Align.CENTER)
        placeholder_label.set_margin_top(24)
        placeholder_label.set_margin_bottom(24)
        placeholder_row.set_child(placeholder_label)
        self._content_box.append(placeholder_row)
        self._current_rows.append(placeholder_row)


class ModulesTab(Gtk.Box):
    """Modules configuration using split view layout"""

    def __init__(self, config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_focusable(True)
        self.config = config
        self.on_change = on_change
        self.sections = {}

        # Left side: Layout and available modules
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_box.set_spacing(12)

        left_scroll = Gtk.ScrolledWindow()
        left_scroll.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        left_scroll.set_vexpand(True)

        left_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_content.set_margin_top(24)
        left_content.set_margin_bottom(24)
        left_content.set_margin_start(24)
        left_content.set_margin_end(24)
        left_content.set_spacing(18)

        layout_group = Adw.PreferencesGroup()
        layout_group.set_title('Bar Layout')
        layout_group.set_description(
            'Drag modules between sections or click to configure'
        )

        for section_name in [
            'modules-left', 'modules-center', 'modules-right'
        ]:
            modules = config.get(section_name, [])
            section = SectionRow(
                section_name, modules, self._on_module_select,
                self._on_layout_change, self.sections, config
            )
            self.sections[section_name] = section
            layout_group.add(section)

        left_content.append(layout_group)

        available = AvailableModulesGroup(
            self._on_add_module, self.sections, config
        )
        left_content.append(available)

        left_scroll.set_child(left_content)

        # Right side: Module settings
        right_scroll = Gtk.ScrolledWindow()
        right_scroll.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        right_scroll.set_vexpand(True)

        right_content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_content.set_margin_top(24)
        right_content.set_margin_bottom(24)
        right_content.set_margin_start(24)
        right_content.set_margin_end(24)

        # right_content.set_margin_start(12)
        right_content.set_size_request(400, -1)

        self.settings_group = ModuleSettingsGroup()
        right_content.append(self.settings_group)
        right_scroll.set_child(right_content)

        # Use OverlaySplitView for sidebar styling
        split_view = Adw.OverlaySplitView()
        split_view.set_sidebar(right_scroll)
        split_view.set_sidebar_position(Gtk.PackType.END)
        split_view.set_content(left_scroll)
        split_view.set_sidebar_width_fraction(0.5)
        split_view.set_show_sidebar(True)

        self.append(split_view)

    def _on_module_select(self, module_name):
        self.settings_group.show_module_settings(
            module_name, self.config, self.on_change, self.sections
        )

    def _on_module_field_change(self, module_name, key, value):
        if self.on_change:
            self.on_change(key, value, module_name)

    def _on_layout_change(self):
        if self.on_change:
            self.on_change('__layout__', self.get_layout(), None)

    def _on_add_module(self, module_name):
        center = self.sections.get('modules-center')
        if center:
            center._add_chip(module_name)
            center._emit_change()

    def refresh(self, config):
        """Update all sections and reset settings view"""
        self.config = config
        for section_name, section in self.sections.items():
            modules = config.get(section_name, [])
            section.refresh(modules, config)
        self.settings_group.reset()

    def get_layout(self):
        return {
            section_name: section.get_modules()
            for section_name, section in self.sections.items()
        }
