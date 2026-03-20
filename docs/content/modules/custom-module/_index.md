---
title: "Custom Module Scripts"
weight: 4
---

The `custom` module runs an external script on a configurable interval and
displays its output on the bar. This is the quickest way to add a module
without writing Python — the script can be in any language.

## Configuration

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `exec` | `file` | — | Path to the script (supports arguments) |
| `return-type` | `choice` | `json` | `json` or `text` |
| `interval` | `integer` | `60` | Seconds between executions |
| `on-click-middle` | `string` | — | Command to run on middle click |
| `on-click-right` | `string` | — | Command to run on right click |

## Text output

With `return-type` set to `text`, the module displays whatever the script
prints to stdout as-is:

```bash
#!/usr/bin/env bash
echo "hello"
```

## JSON output

With `return-type` set to `json` (the default), the script must print a
single JSON object. The top-level keys mirror the standard fields from
`fetch_data`:

| Key | Description |
|-----|-------------|
| `text` | Label shown on the bar |
| `icon` | Font Awesome icon character |
| `class` | CSS class added to the bar widget |

```bash
#!/usr/bin/env bash
echo '{"text": "hello", "icon": "\uf000", "class": "green"}'
```


## Popovers

A script can also define a popover by including a `widget` key in its JSON
output. The value is a schema that describes the popover's widget tree.
This only needs to be returned once — the module caches the schema and only
rebuilds the popover when it changes.

### Widget schema

The `widget` value is a dict with a `children` list. Each child describes
a widget using a `type` key and additional properties. Available types are:

| Type | Key properties |
|------|---------------|
| `box` / `hbox` / `vbox` | `orientation`, `spacing`, `children` |
| `label` | `text`, `id` |
| `button` | `label`, `id` |
| `separator` | `orientation` |
| `levelbar` | `min`, `max`, `value`, `id` |
| `pillbar` | `height`, `radius`, `segments`, `id` |
| `graph` | `data`, `height`, `width`, `min`, `max`, `id` |
| `slider` | `min`, `max`, `value`, `id` |
| `scroll` | `width`, `height`, `children` |
| `image` | `path`, `width`, `height` |

All types also accept `style`, `ha`, `va`, `he`, and `ve` for CSS classes
and alignment, mirroring the common widget helpers.

Assign an `id` to any widget that needs to be updated after the initial
build. Widgets without an `id` are static.

A minimal popover with a label:

```json
{
  "text": "42%",
  "widget": {
    "children": [
      {
        "type": "label",
        "text": "My Module",
        "style": "heading"
      },
      {
        "type": "label",
        "id": "value_label",
        "text": "42%"
      }
    ]
  }
}
```


### Updating widget values in place

Once the popover is built, individual widgets can be updated without
rebuilding the whole structure. Include a `widget_updates` key in the JSON
output alongside (or instead of) `widget`. Its value is a dict mapping
widget `id` strings to new values:

| Widget type | Accepted value |
|-------------|---------------|
| `label` | string |
| `button` | string (updates label text) |
| `levelbar` | number |
| `slider` | number |
| `pillbar` | list of segment dicts |
| `graph` | number (appended to history) or list (replaces history) |

```json
{
  "text": "43%",
  "widget_updates": {
    "value_label": "43%"
  }
}
```

For graphs, passing a single number appends it to an internal history
buffer (capped at 50 points). Passing a list replaces the history
entirely:

```json
{
  "text": "43%",
  "widget_updates": {
    "my_graph": 43
  }
}
```

## Environment variables

The following environment variables are set when the script runs:

| Variable | Value |
|----------|-------|
| `PYBAR_MODULE_NAME` | The module's name from the config |
| `PYBAR_MODULE_TYPE` | Always `custom` |

Click commands (`on-click-middle`, `on-click-right`) receive the same
variables when executed.

## Script requirements

- The script must be executable (`chmod +x`).
- It must exit with code `0`. Any other exit code is treated as an error
  and the module will fall back to its last cached data.
- Execution is terminated after 30 seconds if the script has not exited.
- stdout is captured; stderr is ignored.

## Example

A minimal Python script that reports CPU usage:

```python
#!/usr/bin/env python3
import json
import psutil

percent = round(psutil.cpu_percent(interval=0.5))
print(json.dumps({
    "text": f"{percent}%",
    "icon": "\uf2db",
    "widget": {
        "children": [
            {"type": "label", "text": "CPU", "style": "heading"},
            {"type": "label", "id": "value", "text": f"{percent}%"},
            {
                "type": "graph",
                "id": "graph",
                "data": [percent],
                "height": 120,
                "width": 300,
                "min": 0,
                "max": 100,
            }
        ]
    },
    "widget_updates": {
        "value": f"{percent}%",
        "graph": percent,
    }
}))
```
