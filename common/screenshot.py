"""
Description: Widget screenshot capture utilities
Author: thnikk
"""
import os
from datetime import datetime
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gsk', '4.0')
gi.require_version('Graphene', '1.0')
from gi.repository import Gtk, Gsk, Graphene  # noqa
from common.state import state_manager
from common.helpers import print_debug

_capturing = False


def capture_widget_to_png(widget, filename):
    """
    Capture a GTK widget (including visible popovers) to a PNG file.
    Returns True on success.
    """
    try:
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        def find_popovers(parent):
            found = []
            if isinstance(parent, Gtk.MenuButton):
                pop = parent.get_popover()
                if pop and pop.get_visible():
                    found.append(pop)
            child = parent.get_first_child()
            while child:
                found.extend(find_popovers(child))
                child = child.get_next_sibling()
            return found

        popovers = find_popovers(widget)

        active_pop = state_manager.get('active_popover')
        if (active_pop and active_pop.get_visible()
                and active_pop not in popovers):
            res = active_pop.translate_coordinates(widget, 0, 0)
            if res:
                popovers.append(active_pop)

        min_x, min_y = 0.0, 0.0
        max_x, max_y = float(w), float(h)

        popover_data = []
        for pop in popovers:
            res = pop.translate_coordinates(widget, 0, 0)
            if res:
                px, py = res
                pw = pop.get_allocated_width()
                ph = pop.get_allocated_height()
                min_x = min(min_x, float(px))
                min_y = min(min_y, float(py))
                max_x = max(max_x, float(px + pw))
                max_y = max(max_y, float(py + ph))
                popover_data.append(
                    (pop, float(px), float(py), float(pw), float(ph)))

        final_width = int(max_x - min_x)
        final_height = int(max_y - min_y)

        if final_width <= 0 or final_height <= 0:
            return False

        print_debug(
            f"Capture dimensions: {final_width}x{final_height} "
            f"(offset: {min_x}, {min_y})")

        snapshot = Gtk.Snapshot()
        offset = Graphene.Point()
        offset.init(-min_x, -min_y)
        snapshot.translate(offset)

        paintable = Gtk.WidgetPaintable.new(widget)
        paintable.snapshot(snapshot, w, h)

        for pop, px, py, pw, ph in popover_data:
            snapshot.save()
            p_offset = Graphene.Point()
            p_offset.init(px, py)
            snapshot.translate(p_offset)
            pop_paintable = Gtk.WidgetPaintable.new(pop)
            pop_paintable.snapshot(snapshot, pw, ph)
            snapshot.restore()

        node = snapshot.to_node()
        if not node:
            return False

        renderer = Gsk.CairoRenderer()
        native = widget.get_native()
        if not native:
            return False

        surface = native.get_surface()
        renderer.realize(surface)

        viewport = Graphene.Rect()
        viewport.init(0, 0, final_width, final_height)
        texture = renderer.render_texture(node, viewport)
        if not texture:
            renderer.unrealize()
            return False

        success = texture.save_to_png(filename)
        renderer.unrealize()
        return success
    except Exception as e:
        print_debug(f"Screenshot error: {e}", color='red')
        return False


def take_screenshot(widget):
    """
    Capture a widget screenshot with a timestamped filename and
    send a desktop notification. Safe to use as a GLib timeout handler.
    """
    global _capturing
    if _capturing:
        return False
    _capturing = True

    try:
        from subprocess import run

        screenshot_dir = os.path.expanduser("~/Pictures/Screenshots")
        try:
            os.makedirs(screenshot_dir, exist_ok=True)
        except Exception:
            screenshot_dir = os.path.expanduser("~")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = os.path.join(
            screenshot_dir, f"pybar_{timestamp}.png")

        if capture_widget_to_png(widget, filename):
            print_debug(
                f"Screenshot saved to {filename}", color='green')
            try:
                run([
                    "notify-send", "-i", "camera-photo",
                    "Screenshot Captured", f"Saved to {filename}"
                ])
            except Exception:
                pass
    finally:
        _capturing = False
    return False
