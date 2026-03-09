#!/usr/bin/python3 -u
"""
Description: Icon module - displays an SVG on the bar with no module
             styling, sized to fit the bar height.
Author: thnikk
"""
import os
import common as c
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Rsvg', '2.0')
from gi.repository import Gtk, Rsvg  # noqa


# Default icon path relative to the resource root
_DEFAULT_ICON = 'assets/pybar-icon.svg'


class Icon(c.BaseModule):
    DEFAULT_INTERVAL = 0  # Static; no polling needed

    SCHEMA = {
        'path': {
            'type': 'file',
            'default': '',
            'label': 'Icon Path',
            'description': (
                'Path to a custom SVG icon. '
                'Defaults to assets/pybar-icon.svg.'
            )
        },
        'size': {
            'type': 'integer',
            'default': 0,
            'label': 'Icon Size',
            'description': (
                'Override icon height in pixels. '
                'Defaults to bar height.'
            ),
            'min': 0,
            'max': 200
        },
        'padding': {
            'type': 'integer',
            'default': 0,
            'label': 'Padding',
            'description': (
                'Space in pixels around the icon on all sides.'
            ),
            'min': 0,
            'max': 50
        }
    }

    def run_worker(self):
        """No background work needed for a static icon."""
        pass

    def _resolve_path(self):
        """Return the SVG path to use, falling back to the default."""
        custom = self.config.get('path', '')
        if custom:
            expanded = os.path.expanduser(custom)
            if os.path.isfile(expanded):
                return expanded
            c.print_debug(
                f"Icon path not found: {expanded}, using default",
                color='yellow'
            )
        return c.get_resource_path(_DEFAULT_ICON)

    def create_widget(self, bar):
        """Create a plain DrawingArea widget for the SVG."""
        config = c.state_manager.get('config') or {}
        bar_height = config.get('bar-height', 28)

        size = self.config.get('size', 0) or bar_height
        padding = self.config.get('padding', 0)
        # Shrink icon by padding on top/bottom; width gets padding on
        # left/right too, handled inside IconWidget
        icon_size = max(1, size - padding * 2)

        svg_path = self._resolve_path()
        return IconWidget(svg_path, icon_size, padding)


class IconWidget(Gtk.DrawingArea):
    """DrawingArea rendering an SVG at an exact logical size via librsvg.

    Cairo draw callbacks receive physical pixels on HiDPI but GTK's
    content-size reservation is in logical pixels, so the SVG is
    automatically crisp at any scale factor.
    """

    def __init__(self, svg_path, size, padding=0):
        super().__init__()
        self._size = size
        self._handle = None

        if not os.path.isfile(svg_path):
            c.print_debug(f"Icon file not found: {svg_path}", color='red')
            return

        try:
            self._handle = Rsvg.Handle.new_from_file(svg_path)
        except Exception as e:
            c.print_debug(f"Failed to load SVG: {e}", color='red')
            return

        # Height fits the icon; width adds horizontal padding on each side
        self.set_content_height(size)
        self.set_content_width(size + padding * 2)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._on_draw)

    def _on_draw(self, _area, cr, width, height, *_args):
        """Render the SVG centred and scaled to fit the draw area."""
        if not self._handle:
            return

        # Get intrinsic dimensions for correct aspect ratio
        has_dim, svg_w, svg_h = self._handle.get_intrinsic_size_in_pixels()
        if not has_dim or svg_w <= 0 or svg_h <= 0:
            svg_w = svg_h = float(self._size)

        scale = min(width / svg_w, height / svg_h)
        draw_w = svg_w * scale
        draw_h = svg_h * scale

        # Centre within the full allocated area (including side padding)
        cr.translate((width - draw_w) / 2, (height - draw_h) / 2)
        cr.scale(scale, scale)

        vp = Rsvg.Rectangle()
        vp.x, vp.y = 0.0, 0.0
        vp.width, vp.height = svg_w, svg_h

        try:
            self._handle.render_document(cr, vp)
        except Exception as e:
            c.print_debug(f"Failed to render SVG: {e}", color='red')


module_map = {
    'icon': Icon,
    'logo': Icon
}

alias_map = {
    'icon': Icon,
    'logo': Icon
}
