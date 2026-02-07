#!/usr/bin/python3 -u
"""
Description: Helper functions
Author: thnikk
"""
import inspect
import os
import json
import time
from datetime import datetime
import sys
import gi
import math
import cairo
import logging
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, Pango, GObject, GLib  # noqa


# Alignment mapping for GTK
align = {
    "fill": Gtk.Align.FILL, "start": Gtk.Align.START,
    "end": Gtk.Align.END, "center": Gtk.Align.CENTER
}
align_map = align


def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(
        sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def register_fonts(font_dir):
    """
    Register fonts with fontconfig for the application.
    For PyInstaller, copy fonts to permanent cache to avoid temp path issues.
    """
    import shutil
    from ctypes import CDLL, c_char_p, c_bool, c_void_p

    # If running from PyInstaller temp dir, copy fonts to cache
    if getattr(sys, 'frozen', False) and '_MEI' in font_dir:
        cache_fonts_dir = os.path.expanduser('~/.cache/pybar/fonts')
        try:
            # Create cache directory
            os.makedirs(cache_fonts_dir, exist_ok=True)

            # Copy all font files from temp to cache
            if os.path.exists(font_dir):
                for font_file in os.listdir(font_dir):
                    src = os.path.join(font_dir, font_file)
                    dst = os.path.join(cache_fonts_dir, font_file)
                    if os.path.isfile(src):
                        # Only copy if doesn't exist or is different
                        if not os.path.exists(dst) or \
                           os.path.getmtime(src) > os.path.getmtime(dst):
                            shutil.copy2(src, dst)

            # Use cache directory instead of temp
            font_dir = cache_fonts_dir
            print_debug(
                f"Copied fonts to permanent cache: {cache_fonts_dir}",
                color='green'
            )
        except Exception as e:
            print_debug(
                f"Failed to copy fonts to cache: {e}",
                color='red'
            )
            # Fall through to try original path anyway

    try:
        fontconfig = CDLL('libfontconfig.so.1')
        # FcConfigAppFontAddDir adds a directory to the application's font set
        # FcConfigAppFontAddDir(FcConfig *config, const FcChar8 *file)
        fontconfig.FcConfigAppFontAddDir.argtypes = [c_void_p, c_char_p]
        fontconfig.FcConfigAppFontAddDir.restype = c_bool

        success = fontconfig.FcConfigAppFontAddDir(
            None, font_dir.encode('utf-8'))
        print_debug(f"Registered fonts in {font_dir}: {success}")
    except Exception as e:
        print_debug(f"Font registration failed: {e}", color='red')


class Graph(Gtk.DrawingArea):
    """ Smooth history graph """

    def __init__(
            self, data, state=None, unit=None, min_config=None,
            max_config=None, height=120, width=300, smooth=True,
            time_markers=None, time_labels=None, hover_labels=None,
            colors=None, secondary_data=None):
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
        self.hover_index = -1
        self.set_draw_func(self.on_draw)

        # Add motion controller
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

        # Handle multi-series data
        series = self.data[0] if isinstance(self.data[0], list) else self.data
        num_points = len(series)

        idx = round((x / width) * (num_points - 1))
        idx = max(0, min(idx, num_points - 1))
        if idx != self.hover_index:
            self.hover_index = idx
            self.queue_draw()

    def on_leave(self, _controller):
        self.hover_index = -1
        self.queue_draw()

    def update_data(self, data, state):
        self.data = data
        self.state = state
        self.queue_draw()

    def _catmull_rom_point(self, p0, p1, p2, p3, t, alpha=0.5):
        """Calculate Catmull-Rom spline point at parameter t"""
        def tj(ti, pi, pj):
            xi, yi = pi
            xj, yj = pj
            return ((xj - xi)**2 + (yj - yi)**2)**0.5**alpha + ti

        t0, t1 = 0, tj(0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)

        # Handle edge cases where points are too close
        if abs(t2 - t1) < 1e-6:
            return p1
        if abs(t1 - t0) < 1e-6:
            t0 = t1 - 0.1  # Small offset to prevent division by zero
        if abs(t3 - t2) < 1e-6:
            t3 = t2 + 0.1  # Small offset to prevent division by zero

        # Normalize t to [t1, t2] range
        t_norm = t1 + t * (t2 - t1)

        # Calculate interpolation with safe division
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
        """Draw smooth Catmull-Rom spline through points"""
        if len(points) < 2:
            return

        if len(points) == 2:
            # Simple line for 2 points
            cr.move_to(points[0][0], points[0][1])
            cr.line_to(points[1][0], points[1][1])
            return

        # Create extended points with better ghost points for boundaries
        if len(points) >= 3:
            # Better ghost points: reflect first/last points
            p0 = (2 * points[0][0] - points[1][0],
                  2 * points[0][1] - points[1][1])
            p_last = (2 * points[-1][0] - points[-2][0],
                      2 * points[-1][1] - points[-2][1])

            extended_points = [
                p0,          # Ghost point at start (reflected)
                points[0],   # First actual point
                *points[1:-1],  # Middle points
                points[-1],  # Last actual point
                p_last       # Ghost point at end (reflected)
            ]
        else:
            # For exactly 2 points, create simple ghost points
            dx = points[1][0] - points[0][0]
            dy = points[1][1] - points[0][1]
            p0 = (points[0][0] - dx, points[0][1] - dy)
            p3 = (points[1][0] + dx, points[1][1] + dy)
            extended_points = [p0, points[0], points[1], p3]

        # Draw the spline
        first_segment = True
        for i in range(len(extended_points) - 3):
            p0, p1, p2, p3 = extended_points[i], extended_points[i +
                                                                 1], extended_points[i+2], extended_points[i+3]

            for j in range(n_points_per_segment):
                t = j / (n_points_per_segment -
                         1) if n_points_per_segment > 1 else 0
                point = self._catmull_rom_point(p0, p1, p2, p3, t, alpha=0.5)

                if first_segment and j == 0:
                    cr.move_to(point[0], point[1])
                    first_segment = False
                else:
                    cr.line_to(point[0], point[1])

    def on_draw(self, area, cr, width, height, *args):
        if not self.data:
            return

        # Handle both single series and multi-series
        is_multi = isinstance(self.data[0], list)
        series_list = self.data if is_multi else [self.data]
        if not series_list[0] or len(series_list[0]) < 2:
            return

        w = width
        h = height

        # Calculate global min/max across all series
        all_vals = []
        for s in series_list:
            all_vals.extend(s)

        min_val = self.min_config if self.min_config is not None else min(
            all_vals)
        max_val = self.max_config if self.max_config is not None else max(
            all_vals)
        range_val = max_val - min_val if max_val != min_val else 1

        def get_coords(i, series):
            x = (i / (len(series) - 1)) * w
            val = series[i]
            val = max(min(val, max_val), min_val)
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            return x, y

        # Draw grid lines with dynamic spacing
        grid_color = (0.56, 0.63, 0.75)
        cr.set_line_width(1)
        cr.set_source_rgba(grid_color[0], grid_color[1], grid_color[2], 0.1)

        # Calculate dynamic grid step
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
        for val in range(int(start_line), int(max_val) + 1, int(grid_step)):
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        # Draw each series
        for s_idx, series in enumerate(series_list):
            color = self.colors[s_idx % len(self.colors)]

            cr.new_path()
            if self.smooth:
                points = [get_coords(i, series) for i in range(len(series))]
                self._draw_catmull_rom_spline(
                    cr, points, n_points_per_segment=25)
            else:
                x0, y0 = get_coords(0, series)
                cr.move_to(x0, y0)
                for i in range(len(series) - 1):
                    x1, y1 = get_coords(i, series)
                    x2, y2 = get_coords(i + 1, series)
                    cr.curve_to(
                        x1 + (x2 - x1) / 2, y1, x1 + (x2 - x1) / 2, y2, x2, y2)

            cr.set_line_width(2)
            cr.set_source_rgb(*color)
            path = cr.copy_path()
            cr.stroke()

            # Fill the area
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

        # Draw secondary data (humidity)
        if self.secondary_data:
            s_series = self.secondary_data
            s_min, s_max = 0, 100
            s_range = 100

            def get_s_coords(i):
                x = (i / (len(s_series) - 1)) * w
                val = s_series[i]
                y = 10 + (h - 20) - ((val - s_min) / s_range) * (h - 20)
                return x, y

            s_color = self.colors[1] if len(
                self.colors) > 1 else (0.2, 0.5, 0.8)
            cr.new_path()
            if self.smooth:
                points = [get_s_coords(i) for i in range(len(s_series))]
                self._draw_catmull_rom_spline(
                    cr, points, n_points_per_segment=25)
            else:
                x0, y0 = get_s_coords(0)
                cr.move_to(x0, y0)
                for i in range(len(s_series) - 1):
                    x1, y1 = get_s_coords(i)
                    x2, y2 = get_s_coords(i + 1)
                    cr.line_to(x2, y2)

            cr.set_line_width(1)
            cr.set_source_rgba(s_color[0], s_color[1], s_color[2], 0.5)
            cr.stroke()

        # Draw time marker lines
        if self.time_markers and self.time_labels:
            cr.set_line_width(1)
            cr.set_source_rgba(0.5, 0.5, 0.5, 0.6)
            cr.set_dash([2, 2])

            num_points = len(series_list[0])
            for i, (marker_pos, label) in enumerate(
                    zip(self.time_markers, self.time_labels)):
                if 0 <= marker_pos <= num_points - 1:
                    x = (marker_pos / (num_points - 1)) * w
                    cr.move_to(x, 0)
                    cr.line_to(x, h)
                    cr.stroke()

                    cr.set_dash([])
                    cr.set_source_rgba(0.5, 0.5, 0.5, 0.8)
                    cr.select_font_face(
                        "Nunito", cairo.FONT_SLANT_NORMAL,
                        cairo.FONT_WEIGHT_NORMAL)
                    cr.set_font_size(9)
                    text_extents = cr.text_extents(label)
                    text_x = x - text_extents.width / 2
                    text_y = h / 2  # Show label in middle of graph
                    cr.move_to(text_x, text_y)
                    cr.show_text(label)
                    cr.set_dash([2, 2])
            cr.set_dash([])

        # Draw Legend (Min/Max values)
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
        if self.state:
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
            cr.arc(bg_x + bg_w - radius, bg_y + bg_h -
                   radius, radius, 0, math.pi / 2)
            cr.arc(bg_x + radius, bg_y + bg_h - radius,
                   radius, math.pi / 2, math.pi)
            cr.close_path()
            cr.fill()
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(tx, ty)
            cr.show_text(text)

        # Draw hover line and label
        if self.hover_index != -1:
            num_points = len(series_list[0])
            x = (self.hover_index / (num_points - 1)) * w
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
                total_h -= 4  # remove last spacing

                lx = x - max_w / 2
                ly = 45  # slightly lower to avoid legend
                lx = max(5, min(lx, w - max_w - 5))
                pad = 6

                cr.set_source_rgba(0, 0, 0, 0.8)
                cr.rectangle(
                    lx - pad, ly - total_h - pad,
                    max_w + pad * 2, total_h + pad * 2)
                cr.fill()

                cr.set_source_rgb(1, 1, 1)
                current_y = ly - total_h + line_extents[0].height
                for i, line in enumerate(lines):
                    cr.move_to(
                        lx + (max_w - line_extents[i].width) / 2, current_y)
                    cr.show_text(line)
                    if i < len(lines) - 1:
                        current_y += line_extents[i+1].height + 4


class PillBar(Gtk.DrawingArea):
    """ Custom drawing area for a stacked bar breakdown """
    def __init__(self, height=12, radius=6, wrap_width=None, hover_delay=0):
        super().__init__()
        self.set_content_height(height)
        self.radius = radius
        self.hover_delay = hover_delay
        self.segments = []  # List of {'percent': float, 'color': tuple}
        self.set_draw_func(self.on_draw)
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self.on_query_tooltip)

        # Immediate hover alternative
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
                        s['tooltip'], x, y, offset=y, delay=self.hover_delay)
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
        # Rounded clipping
        r = self.radius
        cr.new_sub_path()
        cr.arc(r, r, r, math.pi, 3 * math.pi / 2)
        cr.arc(width - r, r, r, 3 * math.pi / 2, 2 * math.pi)
        cr.arc(width - r, height - r, r, 0, math.pi / 2)
        cr.arc(r, height - r, r, math.pi / 2, math.pi)
        cr.close_path()
        cr.clip()

        # Background
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


class StateManager:
    def __init__(self):
        self.data = {}
        self.subscribers = {}
        self._next_id = 0

    def _generate_id(self):
        """Generate unique subscription ID"""
        self._next_id += 1
        return self._next_id

    def update(self, name, new_data):
        self.data[name] = new_data
        if name in self.subscribers:
            # Make a copy to avoid issues if dict changes during iteration
            for sub_id, callback in list(self.subscribers[name].items()):
                try:
                    # Use idle_add with priority to ensure cleanup happens
                    GLib.idle_add(
                        callback, new_data,
                        priority=GLib.PRIORITY_DEFAULT_IDLE
                    )
                except Exception as e:
                    print_debug(
                        f"Callback failed for {name}: {e}", color='red'
                    )

    def subscribe(self, name, callback):
        """Subscribe to updates for a name, returns subscription ID"""
        sub_id = self._generate_id()
        if name not in self.subscribers:
            self.subscribers[name] = {}
        self.subscribers[name][sub_id] = callback
        if name in self.data:
            GLib.idle_add(callback, self.data[name])
        print_debug(f"Subscribe: {name} -> ID:{sub_id} (total: {len(self.subscribers[name])})")
        return sub_id

    def unsubscribe(self, sub_id):
        """Unsubscribe using the subscription ID returned by subscribe()"""
        for name, subs in list(self.subscribers.items()):
            if sub_id in subs:
                del subs[sub_id]
                print_debug(
                    f"Unsubscribe: {name} -> ID:{sub_id} "
                    f"(remaining: {len(subs)})"
                )
                if not subs:
                    del self.subscribers[name]
                return True
        return False

    def clear(self):
        """Clear all data and subscribers"""
        total_subs = sum(len(subs) for subs in self.subscribers.values())
        print_debug(
            f"Clearing StateManager: {len(self.data)} data items, "
            f"{total_subs} subscriptions"
        )
        # Log details before clearing
        for name, subs in self.subscribers.items():
            if len(subs) > 1:
                print_debug(
                    f"  WARNING: {name} has {len(subs)} subscriptions "
                    f"(expected 1)",
                    color='yellow'
                )
        self.data.clear()
        self.subscribers.clear()

    def get(self, name):
        return self.data.get(name)

    def debug_info(self):
        """Return debug information about subscriptions"""
        info = {}
        for name, subs in self.subscribers.items():
            info[name] = len(subs)
        return info


state_manager = StateManager()


class BaseModule:
    def __init__(self, name, config):
        self.name = name
        self.config = config
        module_default = getattr(self.__class__, 'DEFAULT_INTERVAL', None)
        self.interval = config.get('interval', module_default or 60)
        self.cache_path = os.path.expanduser(f"~/.cache/pybar/{name}.json")
        self.last_data = None
        self.is_hass = name.startswith('hass') or \
            config.get('type', '').startswith('hass')
        self.empty_is_error = getattr(
            self.__class__, 'EMPTY_IS_ERROR', True
        )

    def cleanup(self):
        """Override in subclass if cleanup is needed"""
        pass

    def fetch_data(self):
        """Override this to fetch data for the module"""
        return {}

    def run_worker(self):
        """Standard worker loop with caching"""
        import module
        stop_event = module._worker_stop_flags.get(self.name)
        first_run = True
        while True:
            data = None
            if first_run and not self.is_hass and \
                    os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, 'r') as f:
                        cached = json.load(f)
                    if cached:
                        self.last_data = cached
                        stale_init = cached.copy()
                        if 'timestamp' in cached:
                            cache_age = time.time() - cached['timestamp']
                            if cache_age > self.interval * 2:
                                stale_init['stale'] = True
                        stale_init['timestamp'] = datetime.now().timestamp()
                        state_manager.update(self.name, stale_init)
                        print_debug(
                            f"Loaded {self.name} from cache", color='green')
                except Exception as e:
                    print_debug(
                        f"Failed to load cache for {self.name}: {e}",
                        color='red')

            start_time = time.time()
            try:
                new_data = self.fetch_data()
                if new_data is not None:
                    if new_data == {} and self.last_data and self.empty_is_error:
                        data = self.last_data.copy()
                        if 'timestamp' in self.last_data:
                            cache_age = time.time() - self.last_data['timestamp']
                            if cache_age > self.interval * 2:
                                data['stale'] = True
                        else:
                            data['stale'] = True
                        print_debug(
                            f"{self.name} returned empty, using stale cache",
                            color='yellow')
                    else:
                        data = new_data
                        self.last_data = data
                        if not self.is_hass:
                            try:
                                os.makedirs(
                                    os.path.dirname(self.cache_path),
                                    exist_ok=True)
                                with open(self.cache_path, 'w') as f:
                                    json.dump(data, f)
                            except Exception as e:
                                print_debug(
                                    f"Failed to save cache for {self.name}: {e}",
                                    color='red')
                else:
                    if self.last_data:
                        data = self.last_data.copy()
                        data['stale'] = True
            except Exception as e:
                print_debug(f"Worker {self.name} failed: {e}", color='red')
                if self.last_data:
                    data = self.last_data.copy()
                    data['stale'] = True

            execution_time = time.time() - start_time

            if data is not None:
                if isinstance(data, dict):
                    data['timestamp'] = datetime.now().timestamp()
                state_manager.update(self.name, data)

            first_run = False
            if self.interval <= 0:
                break

            sleep_time = max(0, self.interval - execution_time)
            if stop_event:
                if stop_event.wait(timeout=sleep_time):
                    break
            else:
                time.sleep(sleep_time)

    def create_widget(self, bar):
        """Create the GTK widget for the bar"""
        import weakref
        
        m = Module()
        m.set_position(bar.position)
        
        # Use weak reference to widget to break circular reference
        widget_ref = weakref.ref(m)
        
        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)
        
        sub_id = state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        m._update_callback = update_callback
        return m

    def update_ui(self, widget, data):
        """Update the UI with new data"""
        if not data:
            return
        if 'text' in data:
            widget.set_label(data['text'])
            widget.set_visible(bool(data['text']))
        if 'icon' in data:
            widget.set_icon(data['icon'])
        if 'tooltip' in data:
            widget.set_tooltip_text(str(data['tooltip']))

        widget.reset_style()
        if 'class' in data:
            add_style(widget, data['class'])
        if data.get('stale'):
            add_style(widget, 'stale')


class Module(Gtk.MenuButton):
    """ Template module """

    def __init__(self, icon=True, text=True):
        super().__init__()
        self.set_direction(Gtk.ArrowType.UP)
        self._cleaned_up = False

        self.get_style_context().add_class('module')
        self.set_cursor_from_name("pointer")
        self.added_styles = []
        self._subscriptions = []  # Track state manager subscriptions

        self.con = Gtk.Overlay()
        self.con.get_style_context().add_class('module-overlay')
        self.indicator = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.indicator.get_style_context().add_class('indicator')
        self.indicator_added_styles = []

        self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.box.set_vexpand(False)
        self.box.set_halign(Gtk.Align.CENTER)
        self.box.set_margin_top(4)
        self.box.set_margin_bottom(4)

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

        # Connect destroy signal for automatic cleanup
        self.connect("destroy", self._on_destroy)

    def _cleanup_popover(self):
        """Cleanup current popover if it exists"""
        popover = self.get_popover()
        if popover:
            # Ensure popover is not visible
            if hasattr(popover, 'popdown'):
                popover.popdown()

            # First set to None to release MenuButton reference
            self.set_popover(None)

            # Then destroy to ensure GTK resources are freed
            if hasattr(popover, 'destroy'):
                popover.destroy()
            elif hasattr(popover, 'unparent'):
                popover.unparent()

    def cleanup(self):
        """Clean up subscriptions and resources when destroyed"""

        # Ensure cleanup runs only once
        if getattr(self, '_cleaned_up', False):
            print_debug(
                f"Module {id(self)} cleanup called twice!",
                color='yellow'
            )
            return
        self._cleaned_up = True

        print_debug(f"Cleaning up Module {id(self)} with "
                    f"{len(self._subscriptions)} subscriptions")

        # Disconnect the destroy signal handler first
        try:
            GObject.signal_handlers_destroy(self)
        except Exception:
            pass

        # Unsubscribe from state manager
        for sub_id in self._subscriptions:
            state_manager.unsubscribe(sub_id)
        self._subscriptions.clear()

        # Clear any widget lists
        if hasattr(self, 'popover_widgets'):
            self.popover_widgets.clear()

        if hasattr(self, 'bar_gpu_levels'):
            self.bar_gpu_levels.clear()

        # Clean up the popover widget FIRST
        self._cleanup_popover()

        # Clear box contents and break references
        if self.box:
            child = self.box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.box.remove(child)
                # Disconnect all signals from child
                try:
                    GObject.signal_handlers_destroy(child)
                except Exception:
                    pass
                child = next_child

        # Break references to internal widgets
        self.icon = None
        self.text = None
        self.box = None
        self.con = None
        self.indicator = None
        
        # Clear callback reference to break closure
        if hasattr(self, '_update_callback'):
            self._update_callback = None

    def _on_destroy(self, widget):
        """Called when widget is destroyed"""
        self.cleanup()

    def set_label(self, text):
        """ Set text and toggle visibility """
        if self.text:
            self.text.set_text(str(text))
            self.text.set_visible(bool(text))
            self._update_layout()
        return self

    def get_text(self):
        """ Get current text """
        return self.text.get_text() if self.text else ""

    def set_icon(self, icon):
        """ Set icon and toggle visibility """
        if self.icon:
            self.icon.set_text(str(icon))
            self.icon.set_visible(bool(icon))
            self._update_layout()
        return self

    def get_active(self):
        """ Check if the popover is visible """
        popover = self.get_popover()
        if popover:
            return popover.get_visible()
        return False

    def _update_layout(self):
        """ Update spacing/margins based on what is visible """
        # Check if widget has been cleaned up
        if self.box is None:
            return

        # Count visible children in the main box
        count = 0
        child = self.box.get_first_child()
        while child:
            if child.get_visible():
                count += 1
            child = child.get_next_sibling()

        # Set spacing if more than one child is visible
        self.box.set_spacing(5 if count > 1 else 0)

    def _update_spacing(self):
        """ Alias for compatibility """
        self._update_layout()

    def reset_style(self):
        """ Reset module style back to default """
        for style in self.added_styles:
            self.get_style_context().remove_class(style)
        self.added_styles = []
        for style in self.indicator_added_styles:
            self.indicator.get_style_context().remove_class(style)
        self.indicator_added_styles = []
        self.indicator.set_visible(False)

    def add_style(self, style_class):
        """ Set style """
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
        """ Remove style """
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
        """ Add style to indicator and show it """
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
        """ Remove style from indicator and hide if empty """
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
        """ Set widget """
        # Clean up existing popover first
        self._cleanup_popover()

        widget = Widget()
        widget.box.append(box)
        widget.draw()
        self.set_popover(widget)

    def set_position(self, position):
        """ Set popover direction """
        directions = {
            "top": Gtk.ArrowType.DOWN,
            "left": Gtk.ArrowType.RIGHT,
            "bottom": Gtk.ArrowType.UP,
            "right": Gtk.ArrowType.LEFT,
        }
        self.set_direction(directions.get(position, Gtk.ArrowType.UP))
        return self


def handle_popover_edge(popover):
    """ Check if a popover is close to the screen edge and flatten corners """
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

    # Find the bar position (top/bottom)
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

    # Threshold: only flatten if the module itself is near the edge
    # The radius is 20px, so 25px is a safe threshold
    threshold = 25
    module_center_x = x + parent.get_width() / 2

    if module_center_x < threshold:
        popover.add_css_class("edge-left")
    elif module_center_x > width - threshold:
        popover.add_css_class("edge-right")


class Widget(Gtk.Popover):
    """ Template widget"""

    def __init__(self):
        super().__init__()
        self.set_position(Gtk.PositionType.TOP)

        # Check config for autohide behavior

        config = state_manager.get('config') or {}
        autohide = config.get('popover-autohide', True)
        self.set_autohide(autohide)

        self.box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.connect("map", self._on_map)
        self.connect("unmap", self._on_unmap)
        self._destroyed = False

    def destroy(self):
        """Ensure proper cleanup of widget resources"""
        if self._destroyed:
            return
        self._destroyed = True

        # Popdown first to ensure it's not visible
        self.popdown()

        # Disconnect all signals first to break reference cycles
        try:
            GObject.signal_handlers_destroy(self)
        except Exception:
            pass

        # Clear box contents recursively
        if self.box:
            child = self.box.get_first_child()
            while child:
                next_child = child.get_next_sibling()
                self.box.remove(child)
                # Disconnect child signals
                try:
                    GObject.signal_handlers_destroy(child)
                except Exception:
                    pass
                # Recursively destroy child widgets
                if hasattr(child, 'unparent'):
                    child.unparent()
                child = next_child

        # Break reference to box
        self.box = None

        # Unparent to release GTK resources
        self.unparent()

    def _on_map(self, _):
        """ Check if we are close to the screen edge and flatten corners """
        handle_popover_edge(self)

        config = state_manager.get('config') or {}
        if config.get('popover-exclusive', False):
            active = state_manager.get('active_popover')
            if active and active != self:
                active.popdown()
            state_manager.update('active_popover', self)

    def _on_unmap(self, _):
        """ Clear active popover if it's us """
        if state_manager.get('active_popover') == self:
            state_manager.update('active_popover', None)

    def heading(self, string):
        self.box.append(label(string))

    def draw(self):
        self.box.set_visible(True)
        self.set_child(self.box)


class HoverPopover(Gtk.Popover):
    """ Lightweight immediate tooltip alternative """
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

    def popdown(self):
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
        self._pending_text = None
        super().popdown()

    def show_text(self, text, x, y, offset=0, delay=0):
        if not text:
            self.popdown()
            return

        if self.get_visible() and self.label.get_text() == text:
            # Update position immediately if already showing same text
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(x), int(y - offset), 1, 1
            self.set_pointing_to(rect)
            return

        if self._pending_text == text:
            # Already waiting to show this exact text, just update coords
            self._pending_coords = (x, y, offset)
            return

        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self._pending_text = text
        self._pending_coords = (x, y, offset)

        def do_show():
            px, py, poff = self._pending_coords
            self.label.set_text(self._pending_text)
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(px), int(py - poff), 1, 1
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
    text_provider can be a string or a callable that returns a string.
    """
    popover = HoverPopover(widget, wrap_width=wrap_width)
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


def print_debug(msg, name=None, color=None) -> None:
    """ Print debug message using logging """
    if not name:
        frame = inspect.stack()[1]
        name = frame[0].f_code.co_filename.split('/')[-1].split('.')[0]
    logger = logging.getLogger(name)
    logger.debug(msg)


def box(orientation, spacing=0, style=None):
    """ Create box """
    obox = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL if orientation == 'v'
        else Gtk.Orientation.HORIZONTAL,
        spacing=spacing
    )
    if style:
        obox.get_style_context().add_class(style)
    return obox


def add_style(widget, style):
    """ Add style to widget """
    if hasattr(widget, 'add_style'):
        widget.add_style(style)
        return
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().add_class(item)
    else:
        widget.get_style_context().add_class(style)


def del_style(widget, style):
    """ Remove style from widget """
    if hasattr(widget, 'del_style'):
        widget.del_style(style)
        return
    if isinstance(style, list):
        for item in style:
            widget.get_style_context().remove_class(item)
    else:
        widget.get_style_context().remove_class(style)


def button(label=None, style=None, ha=None, length=None):
    """ Button """
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
            if len(label) > length:
                widget.set_tooltip_text(label)
    return widget


def icon_button(icon, text, spacing=10):
    button = Gtk.Button()
    button_box = box('h', spacing)
    button_box.append(label(icon, ha='start', he=True))
    button_box.append(label(text))
    button.set_child(button_box)
    return button


def sep(orientation, style=None):
    """ Separator """
    separator = Gtk.Separator(
        orientation=Gtk.Orientation.VERTICAL
        if orientation == 'v' else Gtk.Orientation.HORIZONTAL
    )
    if style:
        separator.get_style_context().add_class(style)
    return separator


def label(
        input_text, style=None, va=None, ha=None,
        he=False, wrap=None, length=None):
    """ Create label """
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
    if isinstance(length, int):
        text.set_max_width_chars(length)
        text.set_ellipsize(Pango.EllipsizeMode.END)
        if len(str(input_text)) > length:
            text.set_tooltip_text(str(input_text))
    return text


def slider(value, min=0, max=100, style=None, scrollable=True):
    """ Create a slider """
    widget = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min, max, 1)
    widget.set_value(value)
    widget.set_draw_value(False)
    if style:
        widget.get_style_context().add_class(style)

    if not scrollable:
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)
        scroll_controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_scroll(controller, dx, dy):
            # Find the parent ScrolledWindow
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


def level(min=0, max=100, value=0, style=None):
    """ Create level bar """
    widget = Gtk.LevelBar.new_for_interval(min, max)
    widget.set_value(value)
    if style:
        widget.get_style_context().add_class(style)
    return widget


def image(file_path=None, style=None, width=None, height=None):
    """ Create image widget """
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
    """ Create scrollable window """
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
        Gtk.PolicyType.AUTOMATIC if height else Gtk.PolicyType.NEVER
    )
    if style:
        window.get_style_context().add_class(style)
    return window
