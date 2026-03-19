---
title: "Creating a Module"
weight: 1
---

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
