<p align="center">
    <img width="300" src="assets/pybar_logo_light.svg#gh-light-mode-only" alt="Pybar">
    <img width="300" src="assets/pybar_logo_dark.svg#gh-dark-mode-only" alt="Pybar">
</p>

<p align="center">
    A statusbar for Sway with clickable widgets.
</p>

![Screenshot](assets/screenshot.png)

### Modules with widgets
- Weather
- Updates
- Hoyoverse
- Git
- XDrip+
- Calendar
- Volume
- Backlight
- Battery
- Network
- Power
- Sales
- Generic waybar module for waybar-formatted modules

### Goals
There are still some things missing, including:
- [ ] Implement system tray
- [ ] Allow differently configured bars for different monitors.
- [x] Configurable bar position
    - Only top and bottom allowed
    - [ ] Draw widgets in the correct orientation when on top
- [ ] Dynamically redraw widgets

### Installation
As pybar is still under very active development, I haven't looked into packaging yet. For now, you can:

Clone the repo in a safe place

```
$ mkdir ~/Git
$ cd ~/Git
$ git clone https://github.com/thnikk/pybar
```

Create a launcher called `pybar` and put it somewhere in your PATH
```
#!/usr/bin/env sh

# Kill previous instances
pkill -f "python.*pybar"

# Run new bar and log to file
python -u ~/Git/pybar/main.py > ~/.cache/pybar.log 2>&1
```

To use the bar on sway, replace the bar section of your config with:
```
bar {
    swaybar_command pybar
}
```

To update it, you can run:
```
$ git -C ~/Git/pybar pull --rebase
```
