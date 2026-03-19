"""
Description: GTK widget classes (Module, Widget, HoverPopover, etc.)
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, Gdk, Pango, GObject, GLib  # noqa
from common.state import state_manager
from common.helpers import print_debug, add_style, align


def apply_zone_snap(popover):
    """
    Override popover pointing rect to pin it to the screen zone
    matching the section its parent module lives in.

    Left section  → popover left edge aligns with screen left edge.
    Center section → popover is centered on the screen.
    Right section  → popover right edge aligns with screen right edge.

    The rect x is expressed in the parent widget's local coordinate
    space; we translate screen positions back through the hierarchy.
    """
    parent = popover.get_parent()
    if not parent:
        return

    section = getattr(parent, 'section', None)
    if not section:
        return

    toplevel = parent.get_native()
    if not toplevel:
        return

    win_width = toplevel.get_width()
    # Translate the module's origin into window coordinates.
    point = parent.translate_coordinates(toplevel, 0, 0)
    if not point:
        return
    mod_x, _ = point
    mod_w = parent.get_width()

    rect = Gdk.Rectangle()
    rect.width = parent.get_width()
    rect.height = parent.get_height()
    # y=0 anchors to the top of the module button in local space,
    # matching GTK's default popover origin and avoiding overlap.
    rect.y = 0

    if section == 'left':
        # Pin popover left edge to screen left: rect.x in local space
        # equals the negative of the module's screen x offset so that
        # the popover's own left edge lands at screen x=0.
        rect.x = -mod_x
    elif section == 'right':
        # Pin popover right edge to screen right: shift rect.x so the
        # popover's right edge lands at win_width.
        rect.x = win_width - mod_x - mod_w
    else:
        # Center: place rect at the screen's horizontal midpoint.
        rect.x = int(win_width / 2 - mod_x - mod_w / 2)

    popover.set_pointing_to(rect)


def handle_popover_edge(popover):
    """Check if a popover is near the screen edge and flatten corners."""
    parent = popover.get_parent()
    if not parent:
        return

    toplevel = parent.get_native()
    if not toplevel:
        return

    width = toplevel.get_width()
    point = parent.translate_coordinates(toplevel, 0, 0)
    if not point:
        return

    x, _ = point

    bar_pos = "bottom"
    if hasattr(parent, "get_direction"):
        direction = parent.get_direction()
        if direction == Gtk.ArrowType.DOWN:
            bar_pos = "top"

    popover.remove_css_class("edge-left")
    popover.remove_css_class("edge-right")
    popover.remove_css_class("pos-top")
    popover.remove_css_class("pos-bottom")
    popover.add_css_class(f"pos-{bar_pos}")

    threshold = 25
    module_center_x = x + parent.get_width() / 2

    if module_center_x < threshold:
        popover.add_css_class("edge-left")
    elif module_center_x > width - threshold:
        popover.add_css_class("edge-right")


class HoverPopover(Gtk.Popover):
    """Lightweight immediate tooltip alternative."""

    def __init__(self, parent, wrap_width=None):
        super().__init__()
        self.set_parent(parent)
        self.set_autohide(False)
        self.set_position(Gtk.PositionType.TOP)
        self.get_style_context().add_class('hover-popover')
        self.label = Gtk.Label()
        if wrap_width:
            self.label.set_wrap(True)
            self.label.set_max_width_chars(wrap_width)
            self.label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_child(self.label)
        self.set_has_arrow(False)
        self._timeout_id = None
        self._pending_text = None
        self._invalid = False
        parent.connect("destroy", self._on_parent_destroy)

    def _on_parent_destroy(self, _widget):
        """Invalidate and cancel pending timeout on parent destruction."""
        self._invalid = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def popdown(self):
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        self._pending_text = None
        if not self._invalid:
            super().popdown()

    def show_text(self, text, x, y, offset=0, delay=0):
        if self._invalid or not text:
            self.popdown()
            return

        if self.get_visible() and self.label.get_text() == text:
            # Update position only if already showing the same text
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(
                x), int(y - offset), 1, 1
            self.set_pointing_to(rect)
            return

        if self._pending_text == text:
            self._pending_coords = (x, y, offset)
            return

        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self._pending_text = text
        self._pending_coords = (x, y, offset)

        def do_show():
            if self._invalid:
                self._timeout_id = None
                return False
            px, py, poff = self._pending_coords
            self.label.set_text(self._pending_text)
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(
                px), int(py - poff), 1, 1
            self.set_pointing_to(rect)
            self.popup()
            self._timeout_id = None
            self._pending_text = None
            return False

        if delay <= 0 or self.get_visible():
            do_show()
        else:
            self._timeout_id = GLib.timeout_add(delay, do_show)


def set_hover_popover(widget, text_provider, delay=500, wrap_width=None):
    """
    Attach a HoverPopover to a widget.
    text_provider can be a string or callable returning a string.
    Should only be called once per widget during creation.
    """
    if hasattr(widget, '_hover_popover'):
        old_popover = widget._hover_popover
        if old_popover:
            old_popover.popdown()
            if hasattr(old_popover, 'unparent'):
                old_popover.unparent()

    popover = HoverPopover(widget, wrap_width=wrap_width)
    widget._hover_popover = popover

    motion = Gtk.EventControllerMotion.new()

    def on_motion(controller, x, y):
        text = text_provider() if callable(text_provider) else text_provider
        if text:
            popover.show_text(text, x, y, offset=y, delay=delay)
        else:
            popover.popdown()

    def on_leave(controller):
        popover.popdown()

    motion.connect("motion", on_motion)
    motion.connect("leave", on_leave)
    widget.add_controller(motion)
    widget.set_has_tooltip(False)
    return popover


class TruncatedLabel(Gtk.Label):
    """Label that shows a HoverPopover when its text is truncated."""

    def __init__(self, max_length=None, **kwargs):
        initial_text = kwargs.pop('label', '')
        super().__init__(**kwargs)
        self._max_length = max_length
        self._full_text = ""
        self._hover_popover = None
        self._popover_initialized = False

        motion = Gtk.EventControllerMotion.new()
        motion.connect("enter", self._on_enter)
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        self.set_has_tooltip(False)

        self.set_text(initial_text)

    def _ensure_popover(self):
        """Lazy-initialize HoverPopover once the widget is rooted."""
        if not self._popover_initialized and self.get_root():
            self._hover_popover = HoverPopover(self, wrap_width=40)
            self._popover_initialized = True

    def _on_enter(self, controller, x, y):
        self._ensure_popover()

    def _on_motion(self, controller, x, y):
        if self._hover_popover and self._full_text:
            self._hover_popover.show_text(
                self._full_text, x, y, offset=y, delay=500
            )
        elif self._hover_popover:
            self._hover_popover.popdown()

    def _on_leave(self, controller):
        if self._hover_popover:
            self._hover_popover.popdown()

    def set_text(self, text):
        text = str(text)
        super().set_text(text)
        # Store full text only when truncation will occur
        if self._max_length and len(text) > self._max_length:
            self._full_text = text
        else:
            self._full_text = ""


def label(
        input_text, style=None, va=None, ha=None,
        he=False, wrap=None, length=None):
    """Create a Gtk.Label (or TruncatedLabel when length is given)."""
    if isinstance(length, int):
        text = TruncatedLabel(max_length=length, label=str(input_text))
        text.set_max_width_chars(length)
        text.set_width_chars(1)
        text.set_ellipsize(Pango.EllipsizeMode.END)
    else:
        text = Gtk.Label(label=str(input_text))
    if style:
        text.get_style_context().add_class(style)
    if va in align:
        text.set_valign(align[va])
    if ha in align:
        text.set_halign(align[ha])
    text.set_hexpand(bool(he))
    if isinstance(wrap, int):
        text.set_wrap(True)
        text.set_max_width_chars(wrap)
    return text


def button(label=None, style=None, ha=None, length=None):
    """Create a Gtk.Button."""
    widget = Gtk.Button.new()
    widget.set_cursor_from_name("pointer")
    if label:
        widget.set_label(label)
    if style:
        widget.get_style_context().add_class(style)
    if ha in align:
        widget.set_halign(align[ha])
    if length and label:
        child = widget.get_child()
        if isinstance(child, Gtk.Label):
            child.set_max_width_chars(length)
            child.set_ellipsize(Pango.EllipsizeMode.END)

            def _hover_text(w=widget, lim=length):
                t = w.get_label()
                return t if t and len(t) > lim else None

            set_hover_popover(widget, _hover_text)
    return widget


def icon_button(icon, text, spacing=10):
    """Create a button with an icon and text label side by side."""
    from common.helpers import box as make_box
    btn = Gtk.Button()
    btn_box = make_box('h', spacing)
    btn_box.append(label(icon, ha='start', he=True))
    btn_box.append(label(text))
    btn.set_child(btn_box)
    return btn


def slider(value, min=0, max=100, style=None, scrollable=True):
    """Create a Gtk.Scale (horizontal slider)."""
    widget = Gtk.Scale.new_with_range(
        Gtk.Orientation.HORIZONTAL, min, max, 1)
    widget.set_value(value)
    widget.set_draw_value(False)
    if style:
        widget.get_style_context().add_class(style)

    # Disable the built-in long-press gesture (broken with mouse input)
    for controller in widget.observe_controllers():
        if isinstance(controller, Gtk.GestureLongPress):
            controller.set_propagation_phase(Gtk.PropagationPhase.NONE)

    if not scrollable:
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_scroll(controller, dx, dy):
            parent = widget.get_parent()
            while parent and not isinstance(parent, Gtk.ScrolledWindow):
                parent = parent.get_parent()
            if parent:
                adj = parent.get_vadjustment()
                if adj:
                    adj.set_value(adj.get_value() + (dy * 30))
            return True

        scroll_controller.connect("scroll", on_scroll)
        widget.add_controller(scroll_controller)

    return widget


class Widget(Gtk.Popover):
    """Template popover widget."""

    def __init__(self):
        super().__init__()
        self.set_position(Gtk.PositionType.TOP)

        config = state_manager.get('config') or {}
        autohide = config.get('popover-autohide', True)
        self.set_autohide(autohide)

        if not config.get('popover-arrow', False):
            self.set_has_arrow(False)
            margin = 5
            self.set_margin_bottom(margin)
            self.set_margin_top(margin)

        self.box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self._destroyed = False

        self._workspace_subscription = None
        self._opened_on_workspace = None

    def destroy(self):
        """Clean up widget resources."""
        if self._destroyed:
            return
        self._destroyed = True

        self.popdown()

        if self._workspace_subscription:
            state_manager.unsubscribe(self._workspace_subscription)
            self._workspace_subscription = None

        try:
            GObject.signal_handlers_destroy(self)
        except Exception:
            pass

        if self.box:
            child = self.box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.box.remove(child)
                try:
                    GObject.signal_handlers_destroy(child)
                except Exception:
                    pass
                if hasattr(child, 'unparent'):
                    child.unparent()
                child = next_child

        self.box = None
        self.unparent()

    def _on_map(self, _):
        """Handle edge CSS and exclusive-popover logic on show."""
        config = state_manager.get('config') or {}
        if config.get('popover-arrow', False):
            handle_popover_edge(self)
        # Zone-snap overrides the pointing rect before the popover
        # renders so it appears in the correct screen region.
        if config.get('popover-zone-snap', False):
            apply_zone_snap(self)

        parent = self.get_parent()
        if parent:
            parent.add_css_class('popover-open')

        if config.get('popover-exclusive', False):
            active = state_manager.get('active_popover')
            if active and active != self:
                active.popdown()
        state_manager.update('active_popover', self)

        if config.get('popover-hide-on-workspace-change', True):
            workspace_data = state_manager.get('workspaces')
            if workspace_data:
                self._opened_on_workspace = workspace_data.get('focused')

            if not self._workspace_subscription:
                self._workspace_subscription = state_manager.subscribe(
                    'workspaces', self._on_workspace_change
                )

    def _on_unmap(self, _):
        """Clear active popover state and workspace subscription on hide."""
        if state_manager.get('active_popover') == self:
            state_manager.update('active_popover', None)

        parent = self.get_parent()
        if parent:
            parent.remove_css_class('popover-open')

        if self._workspace_subscription:
            state_manager.unsubscribe(self._workspace_subscription)
            self._workspace_subscription = None
        self._opened_on_workspace = None

    def _on_workspace_change(self, data):
        """Hide popover if its workspace is no longer visible."""
        if not data or self._destroyed:
            return
        visible_workspaces = data.get('visible', [])
        if (self._opened_on_workspace is not None and
                self._opened_on_workspace not in visible_workspaces):
            GLib.idle_add(self.popdown)

    def heading(self, string):
        self.box.append(label(string))

    def draw(self):
        self.box.set_visible(True)
        self.set_child(self.box)


class Module(Gtk.MenuButton):
    """Template bar module widget."""

    def __init__(self, icon=True, text=True):
        super().__init__()
        self.set_direction(Gtk.ArrowType.UP)
        self._cleaned_up = False

        self.get_style_context().add_class('module')
        self.set_cursor_from_name("pointer")
        self.added_styles = []
        self._subscriptions = []

        self.con = Gtk.Overlay()
        self.con.get_style_context().add_class('module-overlay')
        self.indicator = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.indicator.get_style_context().add_class('indicator')
        self.indicator_added_styles = []

        self.box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.set_vexpand(False)
        self.box.set_halign(Gtk.Align.CENTER)

        self.con.set_child(self.box)
        self.indicator.set_valign(Gtk.Align.END)
        self.con.add_overlay(self.indicator)
        self.indicator.set_visible(False)
        self.set_child(self.con)

        self.icon = None
        self.text = None

        if icon:
            self.icon = Gtk.Label()
            self.icon.set_visible(False)
            self.icon.set_valign(Gtk.Align.CENTER)
            self.box.append(self.icon)
        if text:
            self.text = Gtk.Label()
            self.text.set_visible(False)
            self.text.set_valign(Gtk.Align.CENTER)
            self.text.set_margin_start(0)
            self.box.append(self.text)

        self.connect("destroy", self._on_destroy)

    def _cleanup_popover(self):
        """Clean up the current popover if it exists."""
        popover = self.get_popover()
        if popover:
            if hasattr(popover, 'popdown'):
                popover.popdown()
            self.set_popover(None)
            if hasattr(popover, 'destroy'):
                popover.destroy()
            elif hasattr(popover, 'unparent'):
                popover.unparent()

    def cleanup(self):
        """Unsubscribe and release all resources."""
        if getattr(self, '_cleaned_up', False):
            print_debug(
                f"Module {id(self)} cleanup called twice!", color='yellow')
            return
        self._cleaned_up = True

        print_debug(f"Cleaning up Module {id(self)} with "
                    f"{len(self._subscriptions)} subscriptions")

        try:
            GObject.signal_handlers_destroy(self)
        except Exception:
            pass

        for sub_id in self._subscriptions:
            state_manager.unsubscribe(sub_id)
        self._subscriptions.clear()

        if hasattr(self, 'popover_widgets'):
            self.popover_widgets.clear()

        if hasattr(self, 'bar_gpu_levels'):
            self.bar_gpu_levels.clear()

        self._cleanup_popover()

        if self.box:
            child = self.box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.box.remove(child)
                try:
                    GObject.signal_handlers_destroy(child)
                except Exception:
                    pass
                child = next_child

        self.icon = None
        self.text = None
        self.box = None
        self.con = None
        self.indicator = None

        if hasattr(self, '_update_callback'):
            self._update_callback = None

    def _on_destroy(self, widget):
        """Called when the widget is destroyed by GTK."""
        self.cleanup()

    def _is_valid(self):
        """Return True if the widget has not been cleaned up."""
        return not self._cleaned_up and self.box is not None

    def set_label(self, text):
        """Set text and toggle visibility."""
        if not self._is_valid():
            return self
        if self.text:
            self.text.set_text(str(text))
            self.text.set_visible(bool(text))
            self._update_layout()
        return self

    def get_text(self):
        """Return current text label value."""
        return self.text.get_text() if self.text else ""

    def set_icon(self, icon):
        """Set icon and toggle visibility."""
        if not self._is_valid():
            return self
        if self.icon:
            self.icon.set_text(str(icon))
            self.icon.set_visible(bool(icon))
            self._update_layout()
        return self

    def get_active(self):
        """Return True if the popover is visible."""
        popover = self.get_popover()
        if popover:
            return popover.get_visible()
        return False

    def _update_layout(self):
        """Update spacing based on visible child count."""
        if self.box is None:
            return
        count = 0
        child = self.box.get_first_child()
        while child:
            if child.get_visible():
                count += 1
            child = child.get_next_sibling()
        self.box.set_spacing(5 if count > 1 else 0)

    def _update_spacing(self):
        """Alias for compatibility."""
        self._update_layout()

    def reset_style(self):
        """Reset module style to default."""
        if not self._is_valid():
            return
        for style in self.added_styles:
            self.get_style_context().remove_class(style)
        self.added_styles = []
        for style in self.indicator_added_styles:
            self.indicator.get_style_context().remove_class(style)
        self.indicator_added_styles = []
        self.indicator.set_visible(False)

    def add_style(self, style_class):
        """Add a style class to the module."""
        if not self._is_valid():
            return self
        if isinstance(style_class, str):
            if style_class not in self.added_styles:
                self.get_style_context().add_class(style_class)
                self.added_styles.append(style_class)
        elif isinstance(style_class, list):
            for item in style_class:
                if item not in self.added_styles:
                    self.get_style_context().add_class(item)
                    self.added_styles.append(item)
        return self

    def del_style(self, style_class):
        """Remove a style class from the module."""
        if not self._is_valid():
            return self
        if isinstance(style_class, str):
            if style_class in self.added_styles:
                self.get_style_context().remove_class(style_class)
                self.added_styles.remove(style_class)
        elif isinstance(style_class, list):
            for item in style_class:
                if item in self.added_styles:
                    self.get_style_context().remove_class(item)
                    self.added_styles.remove(item)
        return self

    def add_indicator_style(self, style_class):
        """Add a style class to the indicator and show it."""
        if not self._is_valid():
            return self
        was_empty = not self.indicator_added_styles
        if isinstance(style_class, str):
            if style_class not in self.indicator_added_styles:
                self.indicator.get_style_context().add_class(style_class)
                self.indicator_added_styles.append(style_class)
        elif isinstance(style_class, list):
            for item in style_class:
                if item not in self.indicator_added_styles:
                    self.indicator.get_style_context().add_class(item)
                    self.indicator_added_styles.append(item)
        if was_empty:
            self.box.set_vexpand(True)
        self.indicator.set_visible(True)
        return self

    def del_indicator_style(self, style_class):
        """Remove a style class from the indicator; hide it if empty."""
        if not self._is_valid():
            return self
        if isinstance(style_class, str):
            if style_class in self.indicator_added_styles:
                self.indicator.get_style_context().add_class(style_class)
                self.indicator_added_styles.remove(style_class)
        elif isinstance(style_class, list):
            for item in style_class:
                if item in self.indicator_added_styles:
                    self.indicator.get_style_context().add_class(item)
                    self.indicator_added_styles.remove(item)
        if not self.indicator_added_styles:
            self.box.set_vexpand(False)
            self.indicator.set_visible(False)
        return self

    def set_widget(self, box):
        """Set the popover child widget."""
        if not self._is_valid():
            return
        self._cleanup_popover()
        widget = Widget()
        widget.box.append(box)
        widget.draw()
        self.set_popover(widget)

    def set_position(self, position):
        """Set the popover arrow direction based on bar position."""
        directions = {
            "top": Gtk.ArrowType.DOWN,
            "left": Gtk.ArrowType.RIGHT,
            "bottom": Gtk.ArrowType.UP,
            "right": Gtk.ArrowType.LEFT,
        }
        self.set_direction(directions.get(position, Gtk.ArrowType.UP))
        return self

