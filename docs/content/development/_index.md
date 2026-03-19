---
title: "Development"
weight: 90
---

This page describes the process of writing a new module from scratch.

## File structure

Each module lives in its own file under the `modules/` directory. Create
`modules/mymodule.py` and register the class at the bottom with a
`module_map` dict:

```python
module_map = {
    'mymodule': MyModule
}
```

The key is the name users will use in their config to refer to the module.
Multiple keys can point to the same class if you want to support aliases.

## The class

Every module is a subclass of `BaseModule`, imported via the `common`
package. Set `DEFAULT_INTERVAL` to control how often `fetch_data` is
called (in seconds):

```python
import common as c

class MyModule(c.BaseModule):
    DEFAULT_INTERVAL = 5
```

The user can override the interval per-module in their config using the
`interval` key, so `DEFAULT_INTERVAL` is just the fallback.

## fetch_data

Override `fetch_data` to collect whatever data the module needs. It must
return a dict. The base class `update_ui` reads a standard set of keys
from that dict:

| Key | Type | Description |
|-----|------|-------------|
| `text` | `str` | Label shown on the bar |
| `icon` | `str` | Icon shown to the left of the label |
| `tooltip` | `str` | Tooltip shown on hover |
| `class` | `str` | CSS class added to the widget |

Returning `None` signals a transient error; the base class will fall back
to the last successful data and mark it stale. Returning an empty dict
`{}` also triggers stale-cache fallback unless `EMPTY_IS_ERROR = False`
is set on the class.

You can include any additional keys alongside the standard ones — they
are ignored by the default `update_ui` but are available in your own
override and in `build_popover`.

```python
def fetch_data(self):
    value = get_some_value()
    return {
        'text': f'{value}%',
        'tooltip': f'Current value: {value}',
        'raw_value': value,
    }
```


## SCHEMA

Define a `SCHEMA` class attribute to expose per-module settings in the
settings UI. Each key is a config field name, and each value is a dict
describing the field:

```python
SCHEMA = {
    'interval': {
        'type': 'integer',
        'default': 5,
        'label': 'Update Interval',
        'description': 'Seconds between updates',
        'min': 1,
        'max': 60,
    },
    'show_label': {
        'type': 'boolean',
        'default': True,
        'label': 'Show Label',
        'description': 'Display a text label next to the icon',
    },
}
```

The `type` and `default` keys are required. `label` and `description` are
displayed in the settings UI. The supported types and their extra keys are:

| Type | Extra keys |
|------|------------|
| `string` | — |
| `integer` | `min`, `max` |
| `float` | `min`, `max`, `step` |
| `boolean` | — |
| `choice` | `choices` (list of allowed values) |
| `color` | — |
| `file` | — |
| `list` | `item_type` (any type from this table) |

Read config values in `fetch_data` or elsewhere via `self.config.get`:

```python
show_label = self.config.get('show_label', True)
```

## create_widget and update_ui

The base class provides default implementations of both methods. For
simple modules that only need a label, icon, tooltip, and CSS class, you
do not need to override them.

To add a fixed icon to the bar widget, override `create_widget`, call
`super()`, then set the icon before returning:

```python
def create_widget(self, bar):
    m = super().create_widget(bar)
    m.set_icon('')
    return m
```

Override `update_ui` when you need to do anything beyond the defaults,
such as controlling widget visibility, updating a popover, or deriving
bar-level appearance from data:

```python
def update_ui(self, widget, data):
    if not data:
        return
    widget.set_label(data.get('text', ''))
    widget.set_visible(bool(data.get('text')))
```


## Icons

Module icons are rendered using Font Awesome 6 Free (Solid). The fonts are
bundled with pybar and registered at startup, so any solid-style icon from
that collection is available without any additional setup.

To find an icon, search the
[Font Awesome 6 free solid icon set](https://fontawesome.com/v6/search?s=solid&ic=free-collection).
Click on an icon and copy its unicode value (shown as e.g. `f000`). In
source, write it as a Python unicode escape:

```python
m.set_icon('\uf000')
```

Alternatively, paste the character directly into the source file if your
editor supports it. Both forms are equivalent at runtime.

Icons passed to `set_icon` are set on the bar widget. Icons returned in
the `icon` key of `fetch_data` go through the same rendering path via the
base class `update_ui`.

## Popovers

Modules can display a popover when clicked. The popover is built lazily
on the first update and then kept alive, with individual widgets inside
it updated in place on subsequent updates.

### Building the popover

Build the popover's content in a `build_popover` method. Store references
to any widgets that will need updating in `widget.popover_widgets`, a dict
keyed by name. Call `widget.set_widget` to attach the content:

```python
def build_popover(self, widget, data):
    widget.popover_widgets = {}
    box = c.box('v', spacing=10, style='widget')

    val_label = c.label(data.get('text', ''), ha='end', he=True)
    box.append(val_label)
    widget.popover_widgets['val_label'] = val_label

    return box
```

### Lazy first-build and in-place updates

Build the popover once on first use, then update its contents in place on
every subsequent call. Rebuilding the entire popover on each update is
expensive and causes visible flicker. The standard pattern is:

```python
def update_ui(self, widget, data):
    if not data:
        return
    widget.set_label(data.get('text', ''))

    if not widget.get_popover():
        widget.set_widget(self.build_popover(widget, data))

    if hasattr(widget, 'popover_widgets'):
        pw = widget.popover_widgets
        pw['val_label'].set_text(data.get('text', ''))
```

### Skipping updates when the popover is not visible

If the popover is not currently open, you can skip updating its internals
entirely. Store a snapshot of the last data used to populate the popover
and compare it on the next call. Only rebuild or refresh when the data
has actually changed:

```python
def update_ui(self, widget, data):
    if not data:
        return
    widget.set_label(data.get('text', ''))

    compare_data = data.copy()
    compare_data.pop('timestamp', None)

    if (widget.get_popover() and
            getattr(widget, 'last_popover_data', None) == compare_data):
        return

    widget.last_popover_data = compare_data
    widget.set_widget(self.build_popover(widget, data))
```

For modules whose popover content changes frequently (like a graph or
per-core CPU bars), skip the comparison and always update in-place, but
still guard against updating while the popover is not visible:

```python
if not widget.get_active():
    return

if hasattr(widget, 'popover_widgets'):
    pw = widget.popover_widgets
    pw['val_label'].set_text(data.get('text', ''))
```

### When a full rebuild is necessary

In-place updates only work when the structure of the popover stays the
same between calls. If the data changes in a way that requires a different
number of rows or a different layout — for example, the list of connected
network devices changes — a full rebuild is unavoidable. In that case,
compare the structural aspect of the data and only rebuild when it
actually differs:

```python
def update_ui(self, widget, data):
    if not data:
        return

    new_keys = set(data.get('items', {}).keys())
    old_keys = set(getattr(widget, '_last_keys', set()))

    if not widget.get_popover() or new_keys != old_keys:
        widget._last_keys = new_keys
        widget.set_widget(self.build_popover(widget, data))
        return

    # Structure unchanged — update in place
    if hasattr(widget, 'popover_widgets'):
        for key in new_keys:
            widget.popover_widgets[key].set_text(str(data['items'][key]))
```


## Common widgets

All of the following are available via the `common` package (`import common as c`).

### Layout helpers

`c.box(orientation, spacing=0, style=None)` creates a `Gtk.Box`. Pass
`'h'` or `'v'` for orientation:

```python
row = c.box('h', spacing=10)
col = c.box('v', spacing=5, style='widget')
```

`c.sep(orientation, style=None)` creates a `Gtk.Separator`:

```python
row.append(c.sep('v'))   # vertical rule between siblings
col.append(c.sep('h'))   # horizontal rule
```

`c.label(text, style=None, ha=None, va=None, he=False, wrap=None, length=None)`
creates a `Gtk.Label`. `ha`/`va` accept `'start'`, `'end'`, `'center'`,
or `'fill'`. `he=True` makes the label expand horizontally (useful for
pushing other widgets to the right). `wrap` sets a max character width
for word-wrapping. `length` enables truncation with a hover tooltip for
the full text:

```python
# Expands to fill remaining space
title = c.label('CPU', style='heading', ha='start', he=True)

# Truncated at 20 chars with hover tooltip showing full text
cmd = c.label(long_string, length=20)
```

`c.level(min=0, max=100, value=0, style=None)` creates a `Gtk.LevelBar`:

```python
bar = c.level(min=0, max=100, value=round(percent))
bar.set_hexpand(True)
```

`c.scroll(width=0, height=0, style=None)` creates a basic
`Gtk.ScrolledWindow`. For most popover use cases the gradient scroll
boxes below are preferred.

### Graph

`c.Graph` is a Cairo drawing area that renders a scrolling line graph.
Import it directly or access it as `c.Graph`.

```python
graph = c.Graph(
    data=[[0]],       # list of series; each series is a list of values
    state=42,         # current value shown as an overlay label
    unit='%',         # appended to the state label
    height=180,       # widget height in pixels
    width=300,        # widget width in pixels
    smooth=False,     # Catmull-Rom smoothing (slower, better for few pts)
    min_config=0,     # fixed y-axis minimum (None = auto)
    max_config=100,   # fixed y-axis maximum (None = auto)
    colors=[(0.3, 0.6, 0.9)],  # one RGB tuple per series
)
```

Pass multiple series to overlay them on the same graph:

```python
graph = c.Graph(
    data=[history_core0, history_core1, history_core2],
    colors=self.get_colors(3),
    ...
)
```

Call `update_data` in `update_ui` to push new values without rebuilding
the widget:

```python
pw['graph'].update_data(
    [data['history']],   # same shape as the constructor's data
    round(data['total']) # new state value
)
```

Optional constructor parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `secondary_data` | `None` | A second data series drawn as vertical pill bars |
| `hover_labels` | `[]` | Per-point strings shown in a tooltip on hover |
| `time_markers` | `[]` | Data-point indices where a vertical dashed line is drawn |
| `time_labels` | `[]` | Labels for each time marker |
| `icon_data` | `[]` | Per-point icon strings; a FA icon is drawn at each change |
| `pin_first_to_edge` | `False` | Pin the first data point to x=0 |
| `center_in_bins` | `False` | Centre each point in an equal-width bin |

### PillBar

`c.PillBar` is a Cairo drawing area that renders a segmented, rounded
bar suitable for showing a percentage breakdown (e.g. memory by process).

```python
bar = c.PillBar(
    height=12,       # bar height in pixels
    radius=6,        # corner radius
    wrap_width=None, # max chars for hover tooltip wrapping
    hover_delay=0,   # ms delay before hover tooltip appears
)
```

Call `update` to set the segments. Each segment is a dict with
`percent`, `color`, and an optional `tooltip`:

```python
bar.update([
    {'percent': 40.0, 'color': (0.95, 0.74, 0.69), 'tooltip': 'firefox'},
    {'percent': 20.0, 'color': (0.56, 0.63, 0.75), 'tooltip': 'python3'},
    {'percent': 10.0, 'color': (1.0, 1.0, 1.0),   'tooltip': 'Other'},
])
```

`percent` values are relative to the full bar width (i.e. they should
add up to at most 100). Segments that would be less than 0.5 px wide
are skipped. Hovering over a segment shows its `tooltip` in a small
popover.

### VScrollGradientBox / HScrollGradientBox

These wrap a child widget in a `Gtk.ScrolledWindow` and overlay
edge-fade gradients to signal scrollable content. They also animate a
brief flash when the user tries to scroll past the end.

`c.VScrollGradientBox` scrolls vertically:

```python
vsgb = c.VScrollGradientBox(
    child,          # any Gtk widget
    height=250,     # fixed viewport height in pixels (0 = unconstrained)
    max_height=None,# soft maximum; widget expands up to this height
    width=400,      # fixed viewport width in pixels (0 = unconstrained)
    gradient_size=None,  # fade band size in pixels (default: 30)
)
c.add_style(vsgb, 'box')
```

`c.HScrollGradientBox` scrolls horizontally:

```python
hsgb = c.HScrollGradientBox(
    child,
    height=0,
    max_width=None,
    gradient_size=None,
)
```

Both classes expose `._scroll` (the inner `Gtk.ScrolledWindow`) if you
need to swap the child after construction:

```python
vsgb._scroll.set_child(new_content)
```

## Minimal skeleton


Putting it all together, the smallest viable module looks like this:

```python
import common as c


class MyModule(c.BaseModule):
    DEFAULT_INTERVAL = 5

    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 5,
            'label': 'Update Interval',
            'description': 'Seconds between updates',
            'min': 1,
            'max': 60,
        },
    }

    def fetch_data(self):
        value = get_some_value()
        return {
            'text': f'{value}',
            'tooltip': f'Value: {value}',
            'raw_value': value,
        }

    def build_popover(self, widget, data):
        widget.popover_widgets = {}
        box = c.box('v', spacing=10, style='widget')

        val_label = c.label(data.get('text', ''))
        box.append(val_label)
        widget.popover_widgets['val_label'] = val_label

        return box

    def create_widget(self, bar):
        m = super().create_widget(bar)
        m.set_icon('')
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))

        if not widget.get_popover():
            widget.set_widget(self.build_popover(widget, data))

        if hasattr(widget, 'popover_widgets'):
            pw = widget.popover_widgets
            pw['val_label'].set_text(data.get('text', ''))


module_map = {
    'mymodule': MyModule,
}
```
