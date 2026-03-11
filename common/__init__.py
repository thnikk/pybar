"""
Description: common package — re-exports all public names so that
             callers using 'import common' and 'common.X' continue
             to work unchanged after the package split.
Author: thnikk
"""
# GTK/GLib namespaces re-exported for callers using c.Pango, c.GObject, etc.
import gi  # noqa
gi.require_version('Gtk', '4.0')
gi.require_version('Pango', '1.0')
from gi.repository import Pango, GObject  # noqa

# Utilities and constants
from common.helpers import (  # noqa
    align, align_map,
    print_debug,
    add_style, del_style,
    box, sep, level, image, scroll,
    _suppress_overshoot, _parse_color,
)

# State management
from common.state import StateManager, state_manager  # noqa

# GTK widget classes and factories
from common.widgets import (  # noqa
    handle_popover_edge,
    HoverPopover,
    set_hover_popover,
    TruncatedLabel,
    label,
    button,
    icon_button,
    slider,
    Widget,
    Module,
)

# Cairo drawing widgets
from common.drawing import (  # noqa
    Graph,
    PillBar,
    HScrollGradientBox,
    VScrollGradientBox,
)

# Volume slider widget
from common.volume_slider import VolumeSliderRow  # noqa

# Screenshot utilities
from common.screenshot import capture_widget_to_png, take_screenshot  # noqa

# Font/resource helpers
from common.fonts import get_resource_path, register_fonts  # noqa

# BaseModule (imported last to avoid circular imports with module.py)
from common.base_module import BaseModule  # noqa
