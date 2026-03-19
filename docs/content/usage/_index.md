---
title: "Usage"
weight: 1
---

Pybar should primarily be launched with:

```bash
    pybar -r
```

The `-r` or `--replace` argument will replace the existing instance of the program. This mimics using `swaybar_command` in sway when running the bar through `exec_always` (or regular `exec` on hyprland), where the bar is restarted whenever your config is reloaded.
