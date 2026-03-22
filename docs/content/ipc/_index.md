---
title: "IPC"
weight: 100
---

Pybar uses a unix socket located at `~/.cache/pybar/pybar.sock` to enable some inter-process communication.

## Toggling widgets
You can toggle the visibility of a widget using the `toggle` action:

``` bash
    echo '{"action":"toggle","widget":"mpris","monitor":"DP-5"}' | \
    nc -U ~/.cache/pybar/pybar.sock
```

## Reloading modules
You can reload data for a module using the `reload` action:

``` bash
    echo '{"action":"reload","module":"updates"}' | \
    nc -U ~/.cache/pybar/pybar.sock
```

## Debug commands

The following commands are only available when pybar is started with the `--debug` flag (`pybar --debug`).

### Object count

Takes a snapshot of all live Python objects grouped by type, useful for spotting memory leaks. Call it twice with a gap between to compare growth:

```bash
    # First snapshot (baseline)
    echo '{"action":"objcount","top":40}' | \
    nc -U ~/.cache/pybar/pybar.sock

    # Second snapshot after some time
    echo '{"action":"objcount","top":40}' | \
    nc -U ~/.cache/pybar/pybar.sock
```

The `top` field controls how many types are returned (default: 30).

### Tracemalloc

Tracks Python memory allocations. The first call starts tracing and records a baseline; the second call diffs against it and returns the top allocation sites by size, showing only what grew between the two snapshots:

```bash
    # Start tracing and record baseline
    echo '{"action":"tracemalloc"}' | \
    nc -U ~/.cache/pybar/pybar.sock

    # Diff snapshot after 5+ minutes
    echo '{"action":"tracemalloc","top":40}' | \
    nc -U ~/.cache/pybar/pybar.sock
```

The `top` field controls how many allocation sites are returned (default: 30).

The helper script `pybar-memsnap` (found in `scripts/` in the repo) automates this workflow — it records a baseline, waits 5 minutes, then prints the diff:

```bash
    # Object count diff (default)
    python3 scripts/pybar-memsnap

    # Tracemalloc allocation diff
    python3 scripts/pybar-memsnap --mode tracemalloc

    # Shorter 60s window for either mode
    python3 scripts/pybar-memsnap --quick
```

### Widget instance counter

When running with `--debug`, pybar logs the number of live `Widget` (popover) instances, total state subscribers, and state keys to the log file every 30 seconds:

```
    Widget instances: 42  total subs: 87  workspaces subs: 3  state keys: 18
```

This can be monitored with:

```bash
    tail -f ~/.cache/pybar/pybar.log | grep 'Widget instances'
```
