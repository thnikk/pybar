"""
Description: GTK helper functions and widget factories
Author: thnikk
"""

import inspect
import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango, GLib  # noqa

# Alignment mapping for GTK
align = {
    "fill": Gtk.Align.FILL,
    "start": Gtk.Align.START,
    "end": Gtk.Align.END,
    "center": Gtk.Align.CENTER,
}
align_map = align


def print_debug(msg, name=None, color=None) -> None:
    """Print debug message using logging."""
    if not name:
        # Fast path: check if any debug logging is enabled at all
        # to avoid the very expensive inspect.stack() call
        if not logging.root.isEnabledFor(logging.DEBUG):
            return
        frame = inspect.stack()[1]
        name = frame[0].f_code.co_filename.split("/")[-1].split(".")[0]
    logger = logging.getLogger(name)
    logger.debug(msg)


def add_style(widget, style):
    """Add style class(es) to a widget."""
    if hasattr(widget, "add_style"):
        widget.add_style(style)
        return
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().add_class(item)
    else:
        widget.get_style_context().add_class(style)


def del_style(widget, style):
    """Remove style class(es) from a widget."""
    if hasattr(widget, "del_style"):
        widget.del_style(style)
        return
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().remove_class(item)
    else:
        widget.get_style_context().remove_class(style)


def box(orientation, spacing=0, style=None):
    """Create a Gtk.Box."""
    obox = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL
        if orientation == "v"
        else Gtk.Orientation.HORIZONTAL,
        spacing=spacing,
    )
    if style:
        obox.get_style_context().add_class(style)
    return obox


def sep(orientation, style=None):
    """Create a Gtk.Separator."""
    separator = Gtk.Separator(
        orientation=Gtk.Orientation.VERTICAL
        if orientation == "v"
        else Gtk.Orientation.HORIZONTAL
    )
    if style:
        separator.get_style_context().add_class(style)
    return separator


def level(min=0, max=100, value=0, style=None):
    """Create a Gtk.LevelBar."""
    widget = Gtk.LevelBar.new_for_interval(min, max)
    widget.set_value(value)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def image(file_path=None, style=None, width=None, height=None):
    """Create a Gtk.Picture widget."""
    if file_path:
        widget = Gtk.Picture.new_for_filename(file_path)
    else:
        widget = Gtk.Picture.new()
    if style:
        widget.get_style_context().add_class(style)
    if width:
        widget.set_content_width(width)
    if height:
        widget.set_content_height(height)
    return widget


def scroll(width=0, height=0, style=None, vexpand=False, hexpand=True):
    """Create a Gtk.ScrolledWindow."""
    window = Gtk.ScrolledWindow(hexpand=hexpand, vexpand=vexpand)
    window.set_overflow(Gtk.Overflow.HIDDEN)
    window.set_min_content_width(width)
    window.set_min_content_height(height)
    if height > 0:
        window.set_max_content_height(height)
    if width > 0:
        window.set_max_content_width(width)
    window.set_propagate_natural_width(True)
    window.set_propagate_natural_height(True)
    window.set_policy(
        Gtk.PolicyType.AUTOMATIC if width else Gtk.PolicyType.NEVER,
        Gtk.PolicyType.AUTOMATIC if height else Gtk.PolicyType.NEVER,
    )
    if style:
        window.get_style_context().add_class(style)
    return window


# Shared provider for suppressing ScrolledWindow overshoot highlights.
# A single instance is reused across all windows; it never needs to be
# removed because it carries no per-widget state.
_overshoot_provider = None


def _suppress_overshoot(scrolled_window):
    """Remove the built-in overshoot highlight from a ScrolledWindow."""
    global _overshoot_provider
    if _overshoot_provider is None:
        _overshoot_provider = Gtk.CssProvider()
        _overshoot_provider.load_from_data(
            b"overshoot { background: none; box-shadow: none; }"
        )
    scrolled_window.get_style_context().add_provider(
        _overshoot_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )


def _parse_color(color):
    """
    Convert a color to an (r, g, b) float tuple.
    Accepts: float tuple, byte tuple (0-255), or hex string.
    """
    if isinstance(color, str):
        h = color.lstrip("#")
        return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    if any(v > 1.0 for v in color):
        return tuple(v / 255.0 for v in color)
    return tuple(color)
