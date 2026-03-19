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
