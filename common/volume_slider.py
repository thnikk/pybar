"""
Description: VolumeSliderRow widget for audio device volume control
Author: thnikk
"""
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class VolumeSliderRow(Gtk.Box):
    """
    Volume row with a progress bar background and drag/scroll input.

    Supports left-click drag to set volume, right-click to toggle mute,
    middle-click to set the device as default, and optional scroll-to-
    adjust (disabled by default since rows usually live in scroll boxes).
    """

    def __init__(
            self, title, subtitle, index, initial_volume,
            is_muted, set_volume_cb, set_mute_cb,
            is_default=False, set_default_cb=None,
            scroll_to_adjust=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.index = index
        self.set_volume_cb = set_volume_cb
        self.set_mute_cb = set_mute_cb
        self.set_default_cb = set_default_cb
        self.is_muted = bool(is_muted)
        self.scroll_to_adjust = scroll_to_adjust

        self.add_css_class("volume-row")
        self.set_hexpand(True)

        overlay = Gtk.Overlay()

        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_fraction(initial_volume / 100.0)
        self.progress_bar.add_css_class("volume-progress")
        overlay.set_child(self.progress_bar)

        content_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        content_box.add_css_class("volume-row-content")

        title_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title_box.set_hexpand(True)
        title_box.set_valign(Gtk.Align.CENTER)

        title_label = Gtk.Label()
        title_label.set_text(title)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_ellipsize(3)
        title_label.set_max_width_chars(30)
        title_label.add_css_class("title-label")
        title_box.append(title_label)

        if subtitle and subtitle != title:
            subtitle_label = Gtk.Label()
            subtitle_label.set_text(subtitle)
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.set_ellipsize(3)
            subtitle_label.set_max_width_chars(35)
            subtitle_label.add_css_class("subtitle-label")
            title_box.append(subtitle_label)

        content_box.append(title_box)

        self.default_icon = Gtk.Image.new_from_icon_name(
            "object-select-symbolic")
        self.default_icon.set_valign(Gtk.Align.CENTER)
        self.default_icon.add_css_class("default-icon")
        self.default_icon.set_visible(is_default)
        content_box.append(self.default_icon)

        overlay.add_overlay(content_box)
        self.append(overlay)

        self.adjustment = Gtk.Adjustment(
            value=initial_volume, lower=0, upper=100,
            step_increment=1, page_increment=10
        )
        self._vol_handler = self.adjustment.connect(
            "value-changed", self._on_volume_changed)

        sc = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)
        sc.connect("scroll", self._on_scroll)
        self.add_controller(sc)

        self.dragging = False
        drag = Gtk.GestureDrag.new()
        drag.set_button(1)
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self.add_controller(right_click)

        middle_click = Gtk.GestureClick.new()
        middle_click.set_button(2)
        middle_click.connect("pressed", self._on_middle_click)
        self.add_controller(middle_click)

        self._update_ui()

    def _update_volume_from_x(self, x):
        """Set volume from an x pixel coordinate."""
        width = self.get_width()
        if width > 0:
            volume = max(0, min(100, (x / width) * 100))
            self.adjustment.set_value(volume)

    def _on_drag_begin(self, gesture, start_x, start_y):
        self.dragging = True
        self._update_volume_from_x(start_x)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        ok, start_x, _start_y = gesture.get_start_point()
        if ok:
            self._update_volume_from_x(start_x + offset_x)

    def _on_drag_end(self, gesture, offset_x, offset_y):
        self.dragging = False

    def _on_right_click(self, gesture, n_press, x, y):
        self.toggle_mute()

    def _on_middle_click(self, gesture, n_press, x, y):
        if self.set_default_cb:
            self.set_default_cb(self.index)

    def _on_scroll(self, controller, dx, dy):
        if not self.scroll_to_adjust:
            return False
        self.adjust_volume(-dy * 2)
        return True

    def _on_volume_changed(self, adjustment):
        """Forward new volume (0.0–1.0) to the callback."""
        self.set_volume_cb(self.index, adjustment.get_value() / 100.0)
        self._update_ui()

    def _update_ui(self):
        """Refresh the progress bar and mute CSS state."""
        self.progress_bar.set_fraction(
            self.adjustment.get_value() / 100.0)
        if self.is_muted:
            self.progress_bar.add_css_class("muted")
        else:
            self.progress_bar.remove_css_class("muted")

    def set_volume_silent(self, value):
        """Set volume (0–100) without triggering the volume callback."""
        self.adjustment.handler_block(self._vol_handler)
        self.adjustment.set_value(max(0, min(100, value)))
        self.adjustment.handler_unblock(self._vol_handler)
        self._update_ui()

    def set_mute_silent(self, muted):
        """Set mute state without triggering the mute callback."""
        self.is_muted = bool(muted)
        self._update_ui()

    def adjust_volume(self, delta):
        """Adjust volume by delta, clamped to 0–100."""
        current = self.adjustment.get_value()
        self.adjustment.set_value(max(0, min(100, current + delta)))

    def toggle_mute(self):
        """Toggle mute and notify via callback."""
        self.is_muted = not self.is_muted
        self.set_mute_cb(self.index, self.is_muted)
        self._update_ui()

    def set_is_default(self, value):
        """Show or hide the default device indicator."""
        self.default_icon.set_visible(bool(value))
