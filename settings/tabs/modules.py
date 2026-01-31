#!/usr/bin/python3 -u
"""
Description: Modules settings tab with horizontal bar preview layout
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GObject, Graphene  # noqa

from settings.widgets.editors import create_editor
from settings.schema import get_module_schema
import module as mod


class ModuleChip(Gtk.Box):
    """A draggable chip representing a module"""

    def __init__(self, name, on_select, on_remove, section, config=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.name = name
        self.section = section
        self.on_select = on_select
        self.on_remove = on_remove

        self.get_style_context().add_class('module-chip')
        self.set_margin_top(2)
        self.set_margin_bottom(2)
        self.set_margin_start(2)
        self.set_margin_end(2)

        # Determine module type from config
        module_config = config.get('modules', {}).get(name, {}) if config else {}
        module_type = module_config.get('type', name)

        # Set tooltip if name differs from type
        if module_type != name:
            self.set_tooltip_text(f"Type: {module_type}")

        label = Gtk.Label(label=name)
        self.append(label)

        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('window-close-symbolic')
        remove_btn.get_style_context().add_class('flat')
        remove_btn.get_style_context().add_class('circular')
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.connect('clicked', self._on_remove_clicked)
        self.append(remove_btn)

        # Use GestureClick for selection (not a Button)
        click = Gtk.GestureClick()
        click.set_button(1)  # Left click
        click.connect('released', self._on_clicked)
        self.add_controller(click)

        # Setup drag source
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
        box.get_style_context().add_class('card')
        icon.set_child(box)
        self.set_opacity(0.3)

    def _on_drag_end(self, source, drag, delete_data):
        self.set_opacity(1.0)


class DropIndicator(Gtk.Box):
    """Visual indicator showing where a module will be dropped"""

    def __init__(self):
        super().__init__()
        self.set_size_request(3, -1)
        self.get_style_context().add_class('drop-indicator')


class SectionBox(Gtk.Box):
    """A horizontal row for a bar section (left/center/right)"""

    def __init__(self, section_name, modules, on_select, on_change,
                 all_sections, config=None):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.section_name = section_name
        self.on_select = on_select
        self.on_change = on_change
        self.all_sections = all_sections
        self.config = config  # Store config for tooltip lookup
        self._drop_index = -1
        self._drop_indicator = None

        display_name = section_name.replace('modules-', '').title()

        # Label on the left
        header = Gtk.Label(label=display_name)
        header.set_width_chars(6)
        header.set_xalign(0)
        header.get_style_context().add_class('dim-label')
        self.append(header)

        # Scrolled window for horizontal scrolling
        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        self.scroll.set_hexpand(True)
        self.scroll.set_min_content_height(36)
        self.scroll.get_style_context().add_class('section-scroll')

        # Convert vertical scroll to horizontal
        scroll_controller = Gtk.EventControllerScroll()
        scroll_controller.set_flags(
            Gtk.EventControllerScrollFlags.VERTICAL |
            Gtk.EventControllerScrollFlags.HORIZONTAL)
        scroll_controller.connect('scroll', self._on_scroll)
        self.scroll.add_controller(scroll_controller)

        # Frame inside scroll for styling
        frame = Gtk.Frame()
        frame.get_style_context().add_class('section-frame')

        # Horizontal box for chips
        self.chips_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.chips_box.set_spacing(4)
        self.chips_box.set_halign(Gtk.Align.START)
        self.chips_box.set_valign(Gtk.Align.CENTER)
        self.chips_box.set_margin_top(6)
        self.chips_box.set_margin_bottom(6)
        self.chips_box.set_margin_start(8)
        self.chips_box.set_margin_end(8)

        # Placeholder for empty sections
        self.placeholder = Gtk.Label(label='Drop modules here')
        self.placeholder.get_style_context().add_class('dim-label')
        self.placeholder.set_margin_start(8)
        self.placeholder.set_margin_end(8)

        inner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        inner.set_valign(Gtk.Align.CENTER)
        inner.append(self.chips_box)
        inner.append(self.placeholder)

        frame.set_child(inner)
        self.scroll.set_child(frame)
        self.append(self.scroll)

        # Add initial modules
        for name in modules:
            self._add_chip(name)

        self._update_placeholder()

        # Setup drop target on scroll area
        drop_target = Gtk.DropTarget.new(
            GObject.TYPE_STRING, Gdk.DragAction.MOVE)
        drop_target.connect('drop', self._on_drop)
        drop_target.connect('enter', self._on_enter)
        drop_target.connect('motion', self._on_motion)
        drop_target.connect('leave', self._on_leave)
        self.scroll.add_controller(drop_target)

        self._frame = frame
        self._inner = inner

    def _on_scroll(self, controller, dx, dy):
        """Convert vertical scroll to horizontal"""
        adj = self.scroll.get_hadjustment()
        # Use dy (vertical) to scroll horizontally
        adj.set_value(adj.get_value() + dy * 30)
        return True  # Stop propagation

    def _add_chip(self, name, position=-1):
        chip = ModuleChip(
            name, self.on_select, self._on_remove, self, self.config)
        if position < 0 or position >= len(self._get_chips()):
            self.chips_box.append(chip)
        else:
            # Insert at position by reordering
            chips = self._get_chips()
            # Remove all chips
            for c in chips:
                self.chips_box.remove(c)
            # Re-add with new chip at position
            chips.insert(position, chip)
            for c in chips:
                self.chips_box.append(c)
        self._update_placeholder()

    def _on_remove(self, chip):
        self.chips_box.remove(chip)
        self._emit_change()
        self._update_placeholder()

    def _update_placeholder(self):
        has_chips = len(self._get_chips()) > 0
        self.placeholder.set_visible(not has_chips)
        self.chips_box.set_visible(has_chips)

    def _get_chips(self):
        """Get all module chips"""
        chips = []
        child = self.chips_box.get_first_child()
        while child:
            if isinstance(child, ModuleChip):
                chips.append(child)
            child = child.get_next_sibling()
        return chips

    def _get_drop_index(self, x):
        """Calculate drop index based on x coordinate"""
        chips = self._get_chips()
        if not chips:
            return 0

        # For each chip, get its position relative to scroll widget
        # and find where x falls
        for i, chip in enumerate(chips):
            # Get chip's origin point (0,0) in chip coordinates
            point = Graphene.Point()
            point.x = 0
            point.y = 0

            # Translate chip origin to scroll widget coordinates
            success, translated = chip.compute_point(self.scroll, point)
            if not success:
                continue

            chip_left = translated.x
            chip_width = chip.get_width()
            chip_center = chip_left + chip_width / 2

            # If cursor is left of this chip's center, insert before it
            if x < chip_center:
                return i

        # Cursor is past all chips, insert at end
        return len(chips)

    def _auto_scroll(self, x):
        """Auto-scroll when dragging near edges"""
        adj = self.scroll.get_hadjustment()
        scroll_width = self.scroll.get_width()
        edge_size = 40  # pixels from edge to trigger scroll
        scroll_speed = 8

        if x < edge_size:
            # Scroll left
            adj.set_value(adj.get_value() - scroll_speed)
        elif x > scroll_width - edge_size:
            # Scroll right
            adj.set_value(adj.get_value() + scroll_speed)

    def _on_enter(self, target, x, y):
        self._frame.get_style_context().add_class('drop-target')
        return Gdk.DragAction.MOVE

    def _on_motion(self, target, x, y):
        # Auto-scroll when near edges
        self._auto_scroll(x)

        new_index = self._get_drop_index(x)
        if new_index != self._drop_index:
            self._drop_index = new_index
            self._update_drop_indicator()
        return Gdk.DragAction.MOVE

    def _on_leave(self, target):
        self._frame.get_style_context().remove_class('drop-target')
        self._remove_drop_indicator()
        self._drop_index = -1

    def _update_drop_indicator(self):
        """Show drop indicator at current drop position"""
        self._remove_drop_indicator()

        chips = self._get_chips()

        # Create indicator
        self._drop_indicator = DropIndicator()

        if not chips:
            # Empty section - just show indicator
            self.chips_box.set_visible(True)
            self.placeholder.set_visible(False)
            self.chips_box.append(self._drop_indicator)
        elif self._drop_index >= len(chips):
            # Insert at end
            self.chips_box.append(self._drop_indicator)
        else:
            # Insert at position - need to reorder
            all_children = []
            child = self.chips_box.get_first_child()
            while child:
                all_children.append(child)
                child = child.get_next_sibling()

            # Remove all
            for c in all_children:
                self.chips_box.remove(c)

            # Re-add with indicator at position
            chip_index = 0
            for c in all_children:
                if chip_index == self._drop_index:
                    self.chips_box.append(self._drop_indicator)
                self.chips_box.append(c)
                chip_index += 1

    def _remove_drop_indicator(self):
        """Remove the drop indicator"""
        if self._drop_indicator:
            parent = self._drop_indicator.get_parent()
            if parent:
                parent.remove(self._drop_indicator)
            self._drop_indicator = None
        self._update_placeholder()

    def _on_drop(self, target, value, x, y):
        drop_index = self._drop_index
        self._frame.get_style_context().remove_class('drop-target')
        self._remove_drop_indicator()
        self._drop_index = -1

        parts = value.split(':', 1)
        if len(parts) != 2:
            module_name = value
            source_section = None
        else:
            source_section, module_name = parts

        # Handle "available:" prefix
        if source_section == 'available':
            source_section = None

        # Get current index if same section (for reorder)
        current_index = -1
        if source_section == self.section_name:
            chips = self._get_chips()
            for i, chip in enumerate(chips):
                if chip.name == module_name:
                    current_index = i
                    break

        # Remove from source section
        if source_section and source_section != self.section_name:
            if source_section in self.all_sections:
                self.all_sections[source_section].remove_module_by_name(
                    module_name)
        elif source_section == self.section_name and current_index >= 0:
            self.remove_module_by_name(module_name, emit=False)
            # Adjust drop index if we removed from before it
            if current_index < drop_index:
                drop_index -= 1

        # Check for duplicates
        for chip in self._get_chips():
            if chip.name == module_name:
                return False

        # Add at position
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

    def get_modules(self):
        return [chip.name for chip in self._get_chips()]

    def _emit_change(self):
        if self.on_change:
            self.on_change()


class AvailableModulesExpander(Gtk.Box):
    """Expandable panel showing available modules"""

    def __init__(self, on_add, sections, config=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.on_add = on_add
        self.sections = sections
        self.config = config

        # Expander with flowbox of available modules
        expander = Gtk.Expander(label='Add Module')
        expander.set_expanded(False)

        # Discover all available modules
        mod.discover_modules()
        all_modules = sorted(mod._module_map.keys())

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        content.set_margin_top(8)

        # FlowBox for module buttons
        flowbox = Gtk.FlowBox()
        flowbox.set_valign(Gtk.Align.START)
        flowbox.set_homogeneous(False)
        flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        flowbox.set_max_children_per_line(8)
        flowbox.set_min_children_per_line(3)

        for name in all_modules:
            btn = Gtk.Button(label=name)
            btn.get_style_context().add_class('module-add-btn')
            btn.connect('clicked', lambda b, n=name: self._on_add_clicked(n))

            # Setup drag source
            drag_source = Gtk.DragSource()
            drag_source.set_actions(Gdk.DragAction.MOVE)
            drag_source.connect(
                'prepare', lambda s, x, y, n=name: self._drag_prepare(n))
            drag_source.connect(
                'drag-begin', lambda s, d, n=name: self._drag_begin(d, n))
            btn.add_controller(drag_source)

            flowbox.append(btn)

        content.append(flowbox)
        expander.set_child(content)
        self.append(expander)

    def _drag_prepare(self, name):
        return Gdk.ContentProvider.new_for_value(f"available:{name}")

    def _drag_begin(self, drag, name):
        icon = Gtk.DragIcon.get_for_drag(drag)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(10)
        box.set_margin_end(10)
        label = Gtk.Label(label=name)
        box.append(label)
        box.get_style_context().add_class('card')
        icon.set_child(box)

    def _on_add_clicked(self, module_type):
        # Show a popup to select section and enter name
        popover = Gtk.Popover()
        popover.set_autohide(True)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        # Type label
        type_label = Gtk.Label(label=f"Type: {module_type}")
        type_label.set_halign(Gtk.Align.START)
        type_label.get_style_context().add_class('dim-label')
        box.append(type_label)

        # Name entry
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name_lbl = Gtk.Label(label="Name:")
        name_box.append(name_lbl)

        name_entry = Gtk.Entry()
        name_entry.set_text(module_type)
        name_entry.set_hexpand(True)
        name_entry.set_width_chars(20)
        name_box.append(name_entry)
        box.append(name_box)

        # Error label
        error_label = Gtk.Label()
        error_label.get_style_context().add_class('error')
        error_label.set_halign(Gtk.Align.START)
        error_label.set_visible(False)
        box.append(error_label)

        # Section buttons
        section_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        section_box.set_margin_top(5)

        for section_name in ['modules-left', 'modules-center', 'modules-right']:
            display = section_name.replace('modules-', '').title()
            btn = Gtk.Button(label=f'Add to {display}')
            btn.get_style_context().add_class('flat')
            btn.connect(
                'clicked',
                lambda b, s=section_name, t=module_type, e=name_entry,
                       err=error_label, p=popover:
                    self._do_add_with_name(s, t, e, err, p))
            section_box.append(btn)

        box.append(section_box)
        popover.set_child(box)

        # Find the button that was clicked
        child = self.get_first_child()  # expander
        if child:
            popover.set_parent(child)
            popover.popup()

    def _is_name_globally_unique(self, name):
        """Check if name is unique across all sections"""
        for section in self.sections.values():
            if name in section.get_modules():
                return False
        return True

    def _do_add_with_name(self, section_name, module_type, name_entry,
                          error_label, popover):
        instance_name = name_entry.get_text().strip()

        # Validate not empty
        if not instance_name:
            error_label.set_label("Name cannot be empty")
            error_label.set_visible(True)
            name_entry.add_css_class('error')
            return

        # Validate unique
        if not self._is_name_globally_unique(instance_name):
            error_label.set_label(f"'{instance_name}' already exists")
            error_label.set_visible(True)
            name_entry.add_css_class('error')
            return

        popover.popdown()

        if section_name in self.sections:
            section = self.sections[section_name]

            # If name differs from type, create config entry with type field
            if instance_name != module_type and self.config is not None:
                modules_config = self.config.setdefault('modules', {})
                modules_config[instance_name] = {'type': module_type}

            section._add_chip(instance_name)
            section._emit_change()


class ModulesTab(Gtk.Box):
    """Modules configuration tab with vertical section rows"""

    def __init__(self, config, on_change):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)

        self.config = config
        self.on_change = on_change
        self.selected_module = None
        self.sections = {}

        # Bar layout header
        preview_header = Gtk.Label(label='Bar Layout')
        preview_header.set_halign(Gtk.Align.START)
        preview_header.get_style_context().add_class('heading')
        self.append(preview_header)

        hint = Gtk.Label(
            label='Drag modules between sections or click to configure')
        hint.set_halign(Gtk.Align.START)
        hint.get_style_context().add_class('dim-label')
        self.append(hint)

        # Vertical sections (3 rows: left, center, right)
        sections_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        for section_name in ['modules-left', 'modules-center', 'modules-right']:
            modules = config.get(section_name, [])
            section = SectionBox(
                section_name, modules, self._on_module_select,
                self._on_layout_change, self.sections, config)
            self.sections[section_name] = section
            sections_box.append(section)

        self.append(sections_box)

        # Available modules expander
        available = AvailableModulesExpander(
            self._on_add_module, self.sections, config)
        self.append(available)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(5)
        sep.set_margin_bottom(5)
        self.append(sep)

        # Module settings section
        settings_header = Gtk.Label(label='Module Settings')
        settings_header.set_halign(Gtk.Align.START)
        settings_header.get_style_context().add_class('heading')
        self.append(settings_header)

        # Settings scroll area
        settings_scroll = Gtk.ScrolledWindow()
        settings_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        settings_scroll.set_vexpand(True)
        settings_scroll.set_min_content_height(150)

        self.settings_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10)

        self.settings_placeholder = Gtk.Label(
            label='Click a module above to configure its settings')
        self.settings_placeholder.set_opacity(0.5)
        self.settings_placeholder.set_vexpand(True)
        self.settings_placeholder.set_valign(Gtk.Align.CENTER)
        self.settings_box.append(self.settings_placeholder)

        self.settings_content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.settings_content.set_visible(False)
        self.settings_box.append(self.settings_content)

        settings_scroll.set_child(self.settings_box)
        self.append(settings_scroll)

    def _on_module_select(self, module_name):
        self.selected_module = module_name
        self._show_module_settings(module_name)

    def _show_module_settings(self, module_name):
        # Clear previous content
        child = self.settings_content.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.settings_content.remove(child)
            child = next_child

        # Get current module config and determine type
        module_config = self.config.get('modules', {}).get(module_name, {})
        module_type = module_config.get('type', module_name)

        # Get module class and schema using type (not name)
        mod.discover_modules()
        module_class = mod._module_map.get(module_type)

        if not module_class:
            self.settings_placeholder.set_label(
                f'No settings available for {module_name}')
            self.settings_placeholder.set_visible(True)
            self.settings_content.set_visible(False)
            return

        schema = get_module_schema(module_class)
        if not schema:
            self.settings_placeholder.set_label(
                f'No configurable options for {module_name}')
            self.settings_placeholder.set_visible(True)
            self.settings_content.set_visible(False)
            return

        # Module name header - show type in parens if different from name
        if module_type != module_name:
            header_text = f"{module_name} ({module_type})"
        else:
            header_text = module_name.title()
        name_label = Gtk.Label(label=header_text)
        name_label.set_halign(Gtk.Align.START)
        name_label.get_style_context().add_class('title')
        self.settings_content.append(name_label)

        # Instance name editor
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        name_box.set_margin_bottom(5)

        instance_label = Gtk.Label(label='Instance Name:')
        instance_label.set_halign(Gtk.Align.START)
        name_box.append(instance_label)

        self._name_entry = Gtk.Entry()
        self._name_entry.set_text(module_name)
        self._name_entry.set_hexpand(True)
        self._name_entry.connect('changed', self._on_name_entry_changed)
        self._name_entry.connect(
            'activate',
            lambda e: self._apply_rename(module_name, module_type))
        name_box.append(self._name_entry)

        self._name_apply_btn = Gtk.Button(label='Apply')
        self._name_apply_btn.set_sensitive(False)
        self._name_apply_btn.connect(
            'clicked',
            lambda b: self._apply_rename(module_name, module_type))
        name_box.append(self._name_apply_btn)

        self.settings_content.append(name_box)

        # Error label for name validation
        self._name_error = Gtk.Label()
        self._name_error.set_halign(Gtk.Align.START)
        self._name_error.get_style_context().add_class('error')
        self._name_error.set_visible(False)
        self.settings_content.append(self._name_error)

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(5)
        sep.set_margin_bottom(5)
        self.settings_content.append(sep)

        # Settings grid
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(15)

        row = 0
        for key, schema_field in schema.items():
            value = module_config.get(key, schema_field.get('default'))
            editor = create_editor(
                key, schema_field, value,
                lambda k, v, m=module_name: self._on_module_field_change(m, k, v)
            )
            grid.attach(editor, 0, row, 1, 1)
            row += 1

        self.settings_content.append(grid)
        self.settings_placeholder.set_visible(False)
        self.settings_content.set_visible(True)

    def _on_name_entry_changed(self, entry):
        """Validate name as user types"""
        new_name = entry.get_text().strip()
        old_name = self.selected_module

        # Check if name changed
        if new_name == old_name:
            self._name_apply_btn.set_sensitive(False)
            self._name_error.set_visible(False)
            entry.remove_css_class('error')
            return

        # Validate: not empty
        if not new_name:
            self._name_error.set_label('Name cannot be empty')
            self._name_error.set_visible(True)
            self._name_apply_btn.set_sensitive(False)
            entry.add_css_class('error')
            return

        # Validate: globally unique
        if not self._is_name_unique(new_name, exclude=old_name):
            self._name_error.set_label(f"'{new_name}' already exists")
            self._name_error.set_visible(True)
            self._name_apply_btn.set_sensitive(False)
            entry.add_css_class('error')
            return

        # Valid
        self._name_error.set_visible(False)
        self._name_apply_btn.set_sensitive(True)
        entry.remove_css_class('error')

    def _apply_rename(self, old_name, module_type):
        """Apply the module rename"""
        new_name = self._name_entry.get_text().strip()

        if new_name == old_name:
            return

        if not new_name or not self._is_name_unique(new_name, exclude=old_name):
            return

        # Find which section contains this module
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

        # Update chip
        source_chip.name = new_name
        # Update chip's label
        label = source_chip.get_first_child()
        if isinstance(label, Gtk.Label):
            label.set_label(new_name)
        # Update tooltip
        if module_type != new_name:
            source_chip.set_tooltip_text(f"Type: {module_type}")
        else:
            source_chip.set_tooltip_text(None)

        # Update config
        modules_config = self.config.setdefault('modules', {})
        old_config = modules_config.pop(old_name, {})

        # Ensure type is preserved when name differs
        if module_type != new_name:
            old_config['type'] = module_type
        elif 'type' in old_config and old_config['type'] == new_name:
            # Clean up redundant type field
            del old_config['type']

        modules_config[new_name] = old_config

        # Update selected module
        self.selected_module = new_name

        # Emit layout change (this updates the section arrays)
        self._on_layout_change()

        # Refresh settings panel with new name
        self._show_module_settings(new_name)

    def _is_name_unique(self, name, exclude=None):
        """Check if name is unique across all sections.

        Args:
            name: The name to check
            exclude: Optional name to exclude (for rename validation)
        """
        for section in self.sections.values():
            for module_name in section.get_modules():
                if module_name == name and module_name != exclude:
                    return False
        return True

    def _on_module_field_change(self, module_name, key, value):
        if self.on_change:
            self.on_change(key, value, module_name)

    def _on_layout_change(self):
        if self.on_change:
            self.on_change('__layout__', self.get_layout(), None)

    def _on_add_module(self, module_name):
        # Add to center by default
        center = self.sections.get('modules-center')
        if center:
            center._add_chip(module_name)
            center._emit_change()

    def get_layout(self):
        return {
            section_name: section.get_modules()
            for section_name, section in self.sections.items()
        }
