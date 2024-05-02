# Pybar

![Screenshot](screenshot.png)
> A waybar-like statusbar with widgets

Pybar is a statusbar for Wayland desktops. The main goal of the project is to be compatible with modules written for waybar and to add custom widgets for modules when clicked.

### To-do
- [x] Accept waybar-formatted json for modules
- [x] Sway workspaces
    - [ ] Subscribe to swaymsg and only update when there's a change
- [x] Widgets for modules
    - [x] Spawn in the correct position
    - [x] Get data for widget directly from module output
- [ ] Configurable
- [ ] Handle display disconnection
- [x] Support multiple displays
