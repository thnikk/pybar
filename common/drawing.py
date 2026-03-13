"""
Description: Cairo drawing widgets (Graph, PillBar, scroll gradient boxes)
Author: thnikk
"""
import math
import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, Pango, PangoCairo, GLib  # noqa
from common.helpers import _suppress_overshoot, _parse_color
from common.widgets import HoverPopover


class Graph(Gtk.DrawingArea):
    """Smooth history graph with optional hover labels and icon overlays."""

    def __init__(
            self, data, state=None, unit=None, min_config=None,
            max_config=None, height=120, width=300, smooth=False,
            time_markers=None, time_labels=None, hover_labels=None,
            colors=None, secondary_data=None, icon_data=None,
            pin_first_to_edge=False, center_in_bins=False):
        super().__init__()
        self.set_content_height(height)
        self.set_content_width(width)
        self.set_hexpand(True)
        self.data = data
        self.secondary_data = secondary_data
        self.state = state
        self.unit = unit
        self.smooth = smooth
        self.min_config = min_config
        self.max_config = max_config
        self.time_markers = time_markers or []
        self.time_labels = time_labels or []
        self.hover_labels = hover_labels or []
        self.colors = colors or [(0.56, 0.63, 0.75), (0.2, 0.5, 0.8)]
        # Per-point icon strings; only drawn on icon change
        self.icon_data = icon_data or []
        # Pin point 0 to x=0; subsequent points centred in equal bins
        self.pin_first_to_edge = pin_first_to_edge
        # Centre every point in its own equal-width bin
        self.center_in_bins = center_in_bins
        self.hover_index = -1
        self.set_draw_func(self.on_draw)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self.on_motion)
        motion.connect("leave", self.on_leave)
        self.add_controller(motion)

    def on_motion(self, _controller, x, _y):
        if not self.data:
            return
        width = self.get_width()
        if width <= 0:
            return

        series = (
            self.data[0] if isinstance(self.data[0], list) else self.data)
        num_points = len(series)

        if self.center_in_bins and num_points > 0:
            idx = int(x * num_points / width)
        elif self.pin_first_to_edge and num_points > 1:
            threshold = 0.25 / (num_points - 1) * width
            if x < threshold:
                idx = 0
            else:
                idx = round(x * (num_points - 1) / width + 0.5)
        else:
            idx = round((x / width) * (num_points - 1))
        idx = max(0, min(idx, num_points - 1))
        if idx != self.hover_index:
            self.hover_index = idx
            self.queue_draw()

    def on_leave(self, _controller):
        self.hover_index = -1
        self.queue_draw()

    def update_data(self, data, state, icon_data=None):
        self.data = data
        self.state = state
        if icon_data is not None:
            self.icon_data = icon_data
        self.queue_draw()

    def _catmull_rom_point(self, p0, p1, p2, p3, t, alpha=0.5):
        """Calculate a Catmull-Rom spline point at parameter t."""
        def tj(ti, pi, pj):
            xi, yi = pi
            xj, yj = pj
            return ((xj - xi)**2 + (yj - yi)**2)**0.5**alpha + ti

        t0, t1 = 0, tj(0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)

        if abs(t2 - t1) < 1e-6:
            return p1
        if abs(t1 - t0) < 1e-6:
            t0 = t1 - 0.1
        if abs(t3 - t2) < 1e-6:
            t3 = t2 + 0.1

        t_norm = t1 + t * (t2 - t1)

        def safe_div(num, denom):
            return num / denom if abs(denom) > 1e-6 else 0

        A1 = [safe_div(t1 - t_norm, t1 - t0) * p0[i] +
              safe_div(t_norm - t0, t1 - t0) * p1[i] for i in (0, 1)]
        A2 = [safe_div(t2 - t_norm, t2 - t1) * p1[i] +
              safe_div(t_norm - t1, t2 - t1) * p2[i] for i in (0, 1)]
        A3 = [safe_div(t3 - t_norm, t3 - t2) * p2[i] +
              safe_div(t_norm - t2, t3 - t2) * p3[i] for i in (0, 1)]

        B1 = [safe_div(t2 - t_norm, t2 - t0) * A1[i] +
              safe_div(t_norm - t0, t2 - t0) * A2[i] for i in (0, 1)]
        B2 = [safe_div(t3 - t_norm, t3 - t1) * A2[i] +
              safe_div(t_norm - t1, t3 - t1) * A3[i] for i in (0, 1)]

        C = [safe_div(t2 - t_norm, t2 - t1) * B1[i] +
             safe_div(t_norm - t1, t2 - t1) * B2[i] for i in (0, 1)]

        return tuple(C)

    def _draw_catmull_rom_spline(self, cr, points, n_points_per_segment=30):
        """Draw a smooth Catmull-Rom spline through points."""
        if len(points) < 2:
            return

        if len(points) == 2:
            cr.move_to(points[0][0], points[0][1])
            cr.line_to(points[1][0], points[1][1])
            return

        if len(points) >= 3:
            p0 = (2 * points[0][0] - points[1][0],
                  2 * points[0][1] - points[1][1])
            p_last = (2 * points[-1][0] - points[-2][0],
                      2 * points[-1][1] - points[-2][1])
            extended_points = [
                p0, points[0], *points[1:-1], points[-1], p_last]
        else:
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
            p0 = (points[0][0] - dx, points[0][1] - dy)
            p3 = (points[1][0] + dx, points[1][1] + dy)
            extended_points = [p0, points[0], points[1], p3]

        first_segment = True
        for i in range(len(extended_points) - 3):
            p0, p1, p2, p3 = (
                extended_points[i], extended_points[i+1],
                extended_points[i+2], extended_points[i+3])
            for j in range(n_points_per_segment):
                t = (j / (n_points_per_segment - 1)
                     if n_points_per_segment > 1 else 0)
                point = self._catmull_rom_point(
                    p0, p1, p2, p3, t, alpha=0.5)
                if first_segment and j == 0:
                    cr.move_to(point[0], point[1])
                    first_segment = False
                else:
                    cr.line_to(point[0], point[1])

    def _point_x(self, i, n, w):
        """Convert a data index to an x coordinate."""
        if self.center_in_bins and n > 0:
            return (i + 0.5) / n * w
        if self.pin_first_to_edge and n > 1:
            return 0 if i == 0 else (i - 0.5) / (n - 1) * w
        return (i / (n - 1)) * w if n > 1 else w / 2

    def on_draw(self, area, cr, width, height, *args):
        if not self.data:
            return

        is_multi = isinstance(self.data[0], list)
        series_list = self.data if is_multi else [self.data]
        if not series_list[0] or len(series_list[0]) < 2:
            return

        w = width
        h = height

        all_vals = []
        for s in series_list:
            all_vals.extend(s)

        min_val = (self.min_config if self.min_config is not None
                   else min(all_vals))
        max_val = (self.max_config if self.max_config is not None
                   else max(all_vals))
        range_val = max_val - min_val if max_val != min_val else 1

        def get_coords(i, series):
            x = self._point_x(i, len(series), w)
            val = max(min(series[i], max_val), min_val)
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            return x, y

        # Grid lines
        grid_color = (0.56, 0.63, 0.75)
        cr.set_line_width(1)
        cr.set_source_rgba(grid_color[0], grid_color[1], grid_color[2], 0.1)

        target_lines = 5
        grid_step = 10
        if range_val > 0:
            mag = 10**math.floor(math.log10(range_val / target_lines))
            ratio = (range_val / target_lines) / mag
            if ratio < 1.5:
                multiplier = 1
            elif ratio < 3.5:
                multiplier = 2
            elif ratio < 7.5:
                multiplier = 5
            else:
                multiplier = 10
            grid_step = max(mag * multiplier, 1)

        start_line = math.ceil(min_val / grid_step) * grid_step
        for val in range(
                int(start_line), int(max_val) + 1, int(grid_step)):
            y = 10 + (h - 20) - (
                (val - min_val) / range_val) * (h - 20)
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        # Series lines and fills
        for s_idx, series in enumerate(series_list):
            color = self.colors[s_idx % len(self.colors)]
            _, first_y = get_coords(0, series)
            _, last_y = get_coords(len(series) - 1, series)

            cr.new_path()
            if self.smooth:
                points = (
                    [(0, first_y)]
                    + [get_coords(i, series) for i in range(len(series))]
                )
                self._draw_catmull_rom_spline(
                    cr, points, n_points_per_segment=25)
            else:
                cr.move_to(0, first_y)
                for i in range(len(series) - 1):
                    x1, y1 = get_coords(i, series)
                    x2, y2 = get_coords(i + 1, series)
                    cr.curve_to(
                        x1 + (x2 - x1) / 2, y1,
                        x1 + (x2 - x1) / 2, y2, x2, y2)

            cr.line_to(w, last_y)
            cr.set_line_width(2)
            cr.set_source_rgb(*color)
            path = cr.copy_path()
            cr.stroke()

            fill_opacity = 0.3 if len(series_list) == 1 else 0.15
            cr.append_path(path)
            cr.line_to(w, h)
            cr.line_to(0, h)
            cr.close_path()

            linpat = cairo.LinearGradient(0, 0, 0, h)
            linpat.add_color_stop_rgba(
                0, color[0], color[1], color[2], fill_opacity)
            linpat.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
            cr.set_source(linpat)
            cr.fill()

        # Secondary data (e.g. humidity) as centred pill bars
        if self.secondary_data:
            s_series = self.secondary_data
            n = len(s_series)
            s_color = (
                self.colors[1] if len(self.colors) > 1 else (0.2, 0.5, 0.8))

            bar_w = 6
            radius = bar_w / 2
            for i, val in enumerate(s_series):
                bx = self._point_x(i, n, w)
                graph_h = h - 20
                bar_h = max(bar_w, (val / 100) * graph_h)
                x0 = bx - bar_w / 2
                y0 = h / 2 - bar_h / 2
                cr.new_sub_path()
                cr.arc(x0 + radius, y0 + radius,
                       radius, math.pi, 3 * math.pi / 2)
                cr.arc(x0 + bar_w - radius, y0 + radius,
                       radius, 3 * math.pi / 2, 0)
                cr.arc(x0 + bar_w - radius, y0 + bar_h - radius,
                       radius, 0, math.pi / 2)
                cr.arc(x0 + radius, y0 + bar_h - radius,
                       radius, math.pi / 2, math.pi)
                cr.close_path()
            cr.set_source_rgba(
                s_color[0], s_color[1], s_color[2], 0.15)
            cr.fill()

        # Time marker lines and labels
        if self.time_markers and self.time_labels:
            cr.set_line_width(1)
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.6)
            cr.set_dash([2, 2])
            num_points = len(series_list[0])
            for marker_pos, lbl in zip(
                    self.time_markers, self.time_labels):
                if 0 <= marker_pos <= num_points - 1:
                    x = self._point_x(marker_pos, num_points, w)
                    cr.move_to(x, 0)
                    cr.line_to(x, h)
                    cr.stroke()
                    cr.set_dash([])
                    cr.set_source_rgba(0.5, 0.5, 0.5, 0.8)
                    cr.select_font_face(
                        "Nunito", cairo.FONT_SLANT_NORMAL,
                        cairo.FONT_WEIGHT_NORMAL)
                    cr.set_font_size(9)
                    text_extents = cr.text_extents(lbl)
                    cr.move_to(x - text_extents.width / 2, h / 2)
                    cr.show_text(lbl)
                    cr.set_dash([2, 2])
            cr.set_dash([])

        # Icon overlays drawn only at change points
        if self.icon_data:
            icon_font = Pango.FontDescription(
                "Nunito SemiBold, Font Awesome 6 Free Solid 16"
            )
            num_icon_pts = len(self.icon_data)
            prev = None
            for i, icon in enumerate(self.icon_data):
                if i == 0:
                    prev = icon
                    continue
                if icon == prev:
                    continue
                prev = icon
                ix = self._point_x(i, num_icon_pts, w)

                layout = PangoCairo.create_layout(cr)
                layout.set_font_description(icon_font)
                layout.set_text(icon)
                _, lext = layout.get_pixel_extents()

                tx = ix - (lext.x + lext.width / 2)
                gap = 10
                top_margin = 10
                _, curve_y = get_coords(i, series_list[0])
                ty_above = curve_y - gap - (lext.y + lext.height)
                ty = ty_above if ty_above >= top_margin else (
                    curve_y + gap - lext.y)

                cr.set_source_rgba(1, 1, 1, 0.75)
                cr.move_to(tx, ty)
                PangoCairo.show_layout(cr, layout)

        # Min/Max legend
        legend_color = (0.56, 0.63, 0.75)
        cr.set_source_rgba(
            legend_color[0], legend_color[1], legend_color[2], 0.5)
        cr.select_font_face("Nunito", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        cr.move_to(5, 15)
        cr.show_text(f"{max_val:.1f}")
        cr.move_to(5, h - 5)
        cr.show_text(f"{min_val:.1f}")

        # Current value overlay
        if self.state is not None:
            text = f"{self.state}{self.unit}"
            cr.set_font_size(24)
            extents = cr.text_extents(text)
            tx = w - extents.width - 15
            ty = h - 15
            padding = 10
            radius = 10
            bg_x = tx - padding
            bg_y = ty - extents.height - padding
            bg_w = extents.width + padding * 2
            bg_h = extents.height + padding * 2
            cr.set_source_rgba(0, 0, 0, 0.4)
            cr.new_sub_path()
            cr.arc(bg_x + radius, bg_y + radius,
                   radius, math.pi, 3 * math.pi / 2)
            cr.arc(bg_x + bg_w - radius, bg_y + radius,
                   radius, 3 * math.pi / 2, 2 * math.pi)
            cr.arc(bg_x + bg_w - radius, bg_y + bg_h - radius,
                   radius, 0, math.pi / 2)
            cr.arc(bg_x + radius, bg_y + bg_h - radius,
                   radius, math.pi / 2, math.pi)
            cr.close_path()
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(tx, ty)
            cr.show_text(text)

        # Hover indicator line and tooltip box
        if self.hover_index != -1:
            num_points = len(series_list[0])
            x = self._point_x(self.hover_index, num_points, w)
            hover_color = (0.56, 0.63, 0.75)
            cr.set_source_rgba(
                hover_color[0], hover_color[1], hover_color[2], 0.8)
            cr.set_line_width(1)
            cr.move_to(x, 0)
            cr.line_to(x, h)
            cr.stroke()

            if self.hover_index < len(self.hover_labels):
                label_text = str(self.hover_labels[self.hover_index])
                lines = label_text.split('\n')
                cr.set_font_size(11)

                max_w = 0
                total_h = 0
                line_extents = []
                for line in lines:
                    ext = cr.text_extents(line)
                    max_w = max(max_w, ext.width)
                    line_extents.append(ext)
                    total_h += ext.height + 4
                total_h -= 4

                lx = x - max_w / 2
                ly = 45
                lx = max(5, min(lx, w - max_w - 5))
                pad = 8
                radius = 6
                bx = lx - pad
                by = ly - total_h - pad
                bw = max_w + pad * 2
                bh = total_h + pad * 2

                cr.new_sub_path()
                cr.arc(bx + radius, by + radius,
                       radius, math.pi, 3 * math.pi / 2)
                cr.arc(bx + bw - radius, by + radius,
                       radius, 3 * math.pi / 2, 0)
                cr.arc(bx + bw - radius, by + bh - radius,
                       radius, 0, math.pi / 2)
                cr.arc(bx + radius, by + bh - radius,
                       radius, math.pi / 2, math.pi)
                cr.close_path()
                cr.set_source_rgba(0, 0, 0, 0.55)
                cr.fill()

                cr.set_source_rgb(1, 1, 1)
                current_y = ly - total_h + line_extents[0].height
                for i, line in enumerate(lines):
                    cr.move_to(
                        lx + (max_w - line_extents[i].width) / 2,
                        current_y)
                    cr.show_text(line)
                    if i < len(lines) - 1:
                        current_y += line_extents[i+1].height + 4


class PillBar(Gtk.DrawingArea):
    """Custom drawing area for a stacked bar breakdown."""

    def __init__(self, height=12, radius=6, wrap_width=None, hover_delay=0):
        super().__init__()
        self.set_content_height(height)
        self.radius = radius
        self.hover_delay = hover_delay
        self.segments = []
        self.set_draw_func(self.on_draw)
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)

        self.hover_popover = HoverPopover(self, wrap_width=wrap_width)
        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self.on_motion)
        motion.connect("leave", self.on_leave)
        self.add_controller(motion)

    def on_motion(self, controller, x, y):
        if not self.segments:
            return
        width = self.get_width()
        current_x = 0
        for s in self.segments:
            w = (s['percent'] / 100) * width
            if current_x <= x <= current_x + w:
                if s.get('tooltip'):
                    self.hover_popover.show_text(
                        s['tooltip'], x, y,
                        offset=y, delay=self.hover_delay)
                    return
            current_x += w
        self.hover_popover.popdown()

    def on_leave(self, controller):
        self.hover_popover.popdown()

    def update(self, segments):
        self.segments = segments or []
        self.queue_draw()

    def on_query_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        if not self.segments:
            return False
        width = self.get_width()
        current_x = 0
        for s in self.segments:
            w = (s['percent'] / 100) * width
            if current_x <= x <= current_x + w:
                if s.get('tooltip'):
                    tooltip.set_text(s['tooltip'])
                    return True
            current_x += w
        return False

    def on_draw(self, area, cr, width, height):
        cr.save()
        r = self.radius
        cr.new_sub_path()
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.arc(width - r, r, r, 3 * math.pi / 2, 2 * math.pi)
        cr.arc(width - r, height - r, r, 0, math.pi / 2)
        cr.arc(r, height - r, r, math.pi / 2, math.pi)
        cr.close_path()
        cr.clip()

        cr.set_source_rgba(0.5, 0.5, 0.5, 0.1)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        current_x = 0
        for s in self.segments:
            w = (s['percent'] / 100) * width
            if w < 0.5:
                current_x += w
                continue
            cr.set_source_rgb(*s['color'])
            cr.rectangle(current_x, 0, w, height)
            cr.fill()
            current_x += w
        cr.restore()


class _ScrollGradientBase(Gtk.Overlay):
    """Shared base for horizontal and vertical scroll gradient overlays."""

    GRADIENT_SIZE = 30
    BG = (0.169, 0.188, 0.231)   # #2b303b as floats
    FLASH = (0.3, 0.36, 0.47)    # Light default flash colour

    def __init__(
            self, child, gradient_size=None,
            bg_color=None, flash_color=None):
        super().__init__()
        self._gradient_size = (
            gradient_size if gradient_size is not None
            else self.GRADIENT_SIZE
        )
        self._bg_color = _parse_color(bg_color) if bg_color else self.BG
        self._flash_color = (
            _parse_color(flash_color) if flash_color else self.FLASH
        )
        self._flash_opacity = 0.0
        self._flash_dir = 0
        self._anim_id = None
        self.set_overflow(Gtk.Overflow.HIDDEN)

        self._scroll = self._make_scroll()
        self._scroll.set_child(child)
        self.set_child(self._scroll)

        self._canvas = Gtk.DrawingArea()
        self._canvas.set_can_target(False)
        self._canvas.set_draw_func(self._draw)
        self.add_overlay(self._canvas)

        adj = self._get_adjustment()
        adj.connect("value-changed", lambda *_: self._canvas.queue_draw())
        adj.connect("changed", lambda *_: self._canvas.queue_draw())

        self._scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES)
        self._scroll_controller.connect("scroll", self._on_scroll_event)
        self._scroll.add_controller(self._scroll_controller)

    def _on_scroll_event(self, _controller, dx, dy):
        delta = dy if hasattr(self, '_sw_height') else dx
        if delta == 0:
            return False

        adj = self._get_adjustment()
        val = adj.get_value()
        max_val = adj.get_upper() - adj.get_page_size()

        if max_val <= 0:
            return False

        if delta < 0 and val <= 0:
            self._start_flash(-1)
        elif delta > 0 and val >= max_val - 0.1:
            self._start_flash(1)
        return False

    def _make_scroll(self):
        raise NotImplementedError

    def _get_adjustment(self):
        raise NotImplementedError

    def scroll_by(self, delta):
        """Scroll by delta pixels, flashing at boundaries."""
        adj = self._get_adjustment()
        val = adj.get_value()
        upper = adj.get_upper()
        page = adj.get_page_size()
        max_val = upper - page
        if max_val <= 0:
            return
        new_val = val + delta
        if new_val < 0 and val <= 0:
            self._start_flash(-1)
        elif new_val > max_val and val >= max_val - 1:
            self._start_flash(1)
        adj.set_value(max(0.0, min(new_val, max_val)))

    def _start_flash(self, direction):
        """Animate a brief edge-flash to signal an overscroll attempt."""
        if self._anim_id:
            GLib.source_remove(self._anim_id)
        self._flash_opacity = 0.7
        self._flash_dir = direction

        def _fade():
            self._flash_opacity -= 0.05
            if self._flash_opacity <= 0.0:
                self._flash_opacity = 0.0
                self._anim_id = None
                self._canvas.queue_draw()
                return False
            self._canvas.queue_draw()
            return True

        self._anim_id = GLib.timeout_add(16, _fade)

    def _rounded_rect(self, cr, x, y, w, h, r):
        """Trace a rounded rectangle path."""
        cr.new_sub_path()
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.arc(x + w - r, y + r, r, 3 * math.pi / 2, 2 * math.pi)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.close_path()

    def _draw(self, _area, cr, width, height, *_args):
        raise NotImplementedError


class HScrollGradientBox(_ScrollGradientBase):
    """
    Horizontal ScrolledWindow with edge-fade gradients and
    overscroll flash effect.
    """

    def __init__(
            self, child, max_width=None, height=0,
            gradient_size=None, bg_color=None, flash_color=None):
        self._max_width = max_width
        self._sw_height = height
        super().__init__(
            child, gradient_size=gradient_size,
            bg_color=bg_color, flash_color=flash_color)

    def _make_scroll(self):
        sw = Gtk.ScrolledWindow(hexpand=True)
        sw.set_overflow(Gtk.Overflow.HIDDEN)
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sw.set_propagate_natural_width(True)
        sw.set_kinetic_scrolling(False)
        _suppress_overshoot(sw)
        if self._sw_height > 0:
            sw.set_min_content_height(self._sw_height)
            sw.set_max_content_height(self._sw_height)
        if self._max_width is not None:
            sw.set_min_content_width(self._max_width)
            sw.set_max_content_width(self._max_width)
        return sw

    def _get_adjustment(self):
        return self._scroll.get_hadjustment()

    def _draw(self, _area, cr, width, height, *_args):
        adj = self._get_adjustment()
        val = adj.get_value()
        upper = adj.get_upper()
        page = adj.get_page_size()
        gs = self._gradient_size
        fade_px = 40.0
        r, g, b = self._bg_color
        fr, fg, fb = self._flash_color
        radius = 10

        left_op = min(val / fade_px, 1.0)
        right_op = min((upper - page - val) / fade_px, 1.0)

        cr.save()
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.clip()

        if left_op > 0:
            pat = cairo.LinearGradient(0, 0, gs, 0)
            pat.add_color_stop_rgba(0, r, g, b, left_op)
            pat.add_color_stop_rgba(1, r, g, b, 0.0)
            cr.rectangle(0, 0, gs, height)
            cr.set_source(pat)
            cr.fill()
        if right_op > 0:
            pat = cairo.LinearGradient(width - gs, 0, width, 0)
            pat.add_color_stop_rgba(0, r, g, b, 0.0)
            pat.add_color_stop_rgba(1, r, g, b, right_op)
            cr.rectangle(width - gs, 0, gs, height)
            cr.set_source(pat)
            cr.fill()

        if self._flash_opacity > 0:
            if self._flash_dir == -1:
                pat = cairo.LinearGradient(0, 0, gs, 0)
                pat.add_color_stop_rgba(
                    0, fr, fg, fb, self._flash_opacity)
                pat.add_color_stop_rgba(1, fr, fg, fb, 0.0)
                cr.rectangle(0, 0, gs, height)
                cr.set_source(pat)
                cr.fill()
            elif self._flash_dir == 1:
                pat = cairo.LinearGradient(width - gs, 0, width, 0)
                pat.add_color_stop_rgba(0, fr, fg, fb, 0.0)
                pat.add_color_stop_rgba(
                    1, fr, fg, fb, self._flash_opacity)
                cr.rectangle(width - gs, 0, gs, height)
                cr.set_source(pat)
                cr.fill()

        cr.restore()


class VScrollGradientBox(_ScrollGradientBase):
    """
    Vertical ScrolledWindow with edge-fade gradients and
    overscroll flash effect.
    """

    def __init__(
            self, child, height=0, max_height=None, width=0,
            gradient_size=None, bg_color=None, flash_color=None):
        self._sw_height = height
        self._max_height = max_height
        self._sw_width = width
        super().__init__(
            child, gradient_size=gradient_size,
            bg_color=bg_color, flash_color=flash_color)

    def _make_scroll(self):
        sw = Gtk.ScrolledWindow(hexpand=True)
        sw.set_overflow(Gtk.Overflow.HIDDEN)
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_propagate_natural_height(True)
        sw.set_kinetic_scrolling(False)
        _suppress_overshoot(sw)
        if self._sw_width > 0:
            sw.set_min_content_width(self._sw_width)
            sw.set_max_content_width(self._sw_width)
            sw.set_propagate_natural_width(False)
            self.set_size_request(self._sw_width, -1)
        if self._sw_height > 0:
            sw.set_min_content_height(self._sw_height)
            sw.set_max_content_height(self._sw_height)
        if self._max_height is not None:
            sw.set_vexpand(True)
            sw.set_max_content_height(self._max_height)
        return sw

    def _get_adjustment(self):
        return self._scroll.get_vadjustment()

    def _draw(self, _area, cr, width, height, *_args):
        adj = self._get_adjustment()
        val = adj.get_value()
        upper = adj.get_upper()
        page = adj.get_page_size()
        gs = self._gradient_size
        fade_px = 40.0
        r, g, b = self._bg_color
        fr, fg, fb = self._flash_color
        radius = 10

        top_op = min(val / fade_px, 1.0)
        bottom_op = min((upper - page - val) / fade_px, 1.0)

        cr.save()
        self._rounded_rect(cr, 0, 0, width, height, radius)
        cr.clip()

        if top_op > 0:
            pat = cairo.LinearGradient(0, 0, 0, gs)
            pat.add_color_stop_rgba(0, r, g, b, top_op)
            pat.add_color_stop_rgba(1, r, g, b, 0.0)
            cr.rectangle(0, 0, width, gs)
            cr.set_source(pat)
            cr.fill()
        if bottom_op > 0:
            pat = cairo.LinearGradient(0, height - gs, 0, height)
            pat.add_color_stop_rgba(0, r, g, b, 0.0)
            pat.add_color_stop_rgba(1, r, g, b, bottom_op)
            cr.rectangle(0, height - gs, width, gs)
            cr.set_source(pat)
            cr.fill()

        if self._flash_opacity > 0:
            if self._flash_dir == -1:
                pat = cairo.LinearGradient(0, 0, 0, gs)
                pat.add_color_stop_rgba(
                    0, fr, fg, fb, self._flash_opacity)
                pat.add_color_stop_rgba(1, fr, fg, fb, 0.0)
                cr.rectangle(0, 0, width, gs)
                cr.set_source(pat)
                cr.fill()
            elif self._flash_dir == 1:
                pat = cairo.LinearGradient(0, height - gs, 0, height)
                pat.add_color_stop_rgba(0, fr, fg, fb, 0.0)
                pat.add_color_stop_rgba(
                    1, fr, fg, fb, self._flash_opacity)
                cr.rectangle(0, height - gs, width, gs)
                cr.set_source(pat)
                cr.fill()

        cr.restore()

