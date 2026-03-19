---
title: "Popovers"
weight: 2
---

Modules can display a popover when clicked. The popover is built lazily
on the first update and then kept alive, with individual widgets inside
it updated in place on subsequent updates.

## Building the popover

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

## Lazy first-build and in-place updates

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

## Skipping updates when the popover is not visible

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

## When a full rebuild is necessary

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
