#!/usr/bin/python3 -u
"""
Description: Widgets
Author: thnikk
"""
import common as c
from subprocess import run, Popen
import gi
import math
import cairo
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk


def format_duration(seconds):
    """ Format duration in seconds to human readable string """
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds/60)}m"
    return f"{int(seconds/3600)}h"


class Graph(Gtk.DrawingArea):
    """ Smooth history graph """
    def __init__(self, data, state=None, unit=None, min_config=None, max_config=None, height=120, width=300):
        super().__init__()
        self.set_content_height(height)
        self.set_content_width(width)
        self.set_hexpand(True)
        self.data = data
        self.state = state
        self.unit = unit
        self.min_config = min_config
        self.max_config = max_config
        self.set_draw_func(self.on_draw)

    def update_data(self, data, state):
        self.data = data
        self.state = state
        self.queue_draw()

    def on_draw(self, area, cr, width, height, *args):
        if not self.data or len(self.data) < 2:
            return

        # Use full width/height for the fill, but slight padding for line
        w = width
        h = height

        min_val = self.min_config if self.min_config is not None else min(self.data)
        max_val = self.max_config if self.max_config is not None else max(self.data)
        range_val = max_val - min_val if max_val != min_val else 1

        def get_coords(i):
            x = (i / (len(self.data) - 1)) * w
            # Leave 10px padding top/bottom for the line and markers
            val = self.data[i]
            # Clip value to min/max
            val = max(min(val, max_val), min_val)
            y = 10 + (h - 20) - ((val - min_val) / range_val) * (h - 20)
            return x, y

        # Colors from style.css (blue #8fa1be)
        color = (0.56, 0.63, 0.75)

        # Draw grid lines (Levels)
        cr.set_line_width(1)
        cr.set_source_rgba(color[0], color[1], color[2], 0.1)
        for level in [0, 0.5, 1]:
            y = 10 + (h - 20) * level
            cr.move_to(0, y)
            cr.line_to(w, y)
            cr.stroke()

        # Draw smooth curves
        x0, y0 = get_coords(0)
        cr.move_to(x0, y0)

        for i in range(len(self.data) - 1):
            x1, y1 = get_coords(i)
            x2, y2 = get_coords(i + 1)
            cr.curve_to(x1 + (x2 - x1) / 2, y1, x1 + (x2 - x1) / 2, y2, x2, y2)
        
        cr.set_line_width(2)
        cr.set_source_rgb(*color)
        path = cr.copy_path()
        cr.stroke()

        # Fill the area
        cr.append_path(path)
        cr.line_to(w, h)
        cr.line_to(0, h)
        cr.close_path()

        linpat = cairo.LinearGradient(0, 0, 0, h)
        linpat.add_color_stop_rgba(0, color[0], color[1], color[2], 0.3)
        linpat.add_color_stop_rgba(1, color[0], color[1], color[2], 0)
        cr.set_source(linpat)
        cr.fill()

        # Draw Legend (Min/Max values)
        cr.set_source_rgba(color[0], color[1], color[2], 0.5)
        cr.select_font_face("Nunito", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(10)
        
        # Max label
        cr.move_to(5, 15)
        cr.show_text(f"{max_val:.1f}")
        # Min label
        cr.move_to(5, h - 5)
        cr.show_text(f"{min_val:.1f}")

        # Draw current value overlay (Bottom Right)
        if self.state:
            text = f"{self.state}{self.unit}"
            cr.set_font_size(24)
            extents = cr.text_extents(text)
            
            # Text position
            tx = w - extents.width - 15
            ty = h - 15
            
            # Subtle background for readability
            padding = 10
            radius = 10
            bg_x = tx - padding
            bg_y = ty - extents.height - padding
            bg_w = extents.width + padding * 2
            bg_h = extents.height + padding * 2
            
            cr.set_source_rgba(0, 0, 0, 0.4)
            # Rounded rectangle
            cr.new_sub_path()
            cr.arc(bg_x + radius, bg_y + radius, radius, math.pi, 3 * math.pi / 2)
            cr.arc(bg_x + bg_w - radius, bg_y + radius, radius, 3 * math.pi / 2, 2 * math.pi)
            cr.arc(bg_x + bg_w - radius, bg_y + bg_h - radius, radius, 0, math.pi / 2)
            cr.arc(bg_x + radius, bg_y + bg_h - radius, radius, math.pi / 2, math.pi)
            cr.close_path()
            cr.fill()
            
            cr.set_source_rgb(1, 1, 1)
            cr.move_to(tx, ty)
            cr.show_text(text)


def hass(name, module, cache):
    """ Home Assistant history widget """
    main_box = c.box('v', spacing=10)
    c.add_style(main_box, 'small-widget')
    
    header = c.box('h')
    header.append(c.label(cache['name'], style='heading', ha='start', he=True))
    main_box.append(header)
    
    if cache.get('history'):
        graph_box = c.box('v', style='box')
        # Ensure the box clips the drawing to keep rounded corners looking clean
        graph_box.set_overflow(Gtk.Overflow.HIDDEN)
        graph = Graph(
            cache['history'], 
            state=cache['state'], 
            unit=cache['unit'],
            min_config=cache.get('min'),
            max_config=cache.get('max')
        )
        graph_box.append(graph)
        main_box.append(graph_box)
        
        # Time legend below graph
        time_box = c.box('h')
        duration_str = f"{format_duration(cache.get('duration', 0))} ago"
        duration_label = c.label(duration_str, style='gray', ha='start', he=True)
        time_box.append(duration_label)
        time_box.append(c.label('Now', style='gray', ha='end'))
        main_box.append(time_box)
        
        # Store a reference to the graph and duration label for updates
        main_box.graph = graph
        main_box.duration_label = duration_label
    
    return main_box


def generic_widget(name, module, cache):
    """ Generic widget """
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label(name.capitalize(), style='heading')
    main_box.append(label)

    for category, items in cache.items():
        if not items:
            continue
        category_box = c.box('v', spacing=10)
        category_box.append(c.label(
            category, style='title', ha='start', he=True))
        item_box = c.box('v', style='box')
        if not isinstance(items, list):
            continue
        for item in items:
            item_box.append(c.label(item, style='box-item'))
            if item != items[-1]:
                item_box.append(c.sep('h'))
        category_box.append(item_box)
        main_box.append(category_box)

    return main_box


def weather(name, module, cache):
    """ Weather widget """
    widget = c.box('v', spacing=20)

    today = cache['Today']['info'][0]
    today_box = c.box('h', spacing=10)

    today_left = c.box('v')
    widget.append(c.label(cache['City'], style="heading"))
    temp = c.label(
        f"{today['temperature']}° {today['icon']}", 'today-weather')
    today_left.append(temp)

    extra = c.box('h', spacing=10)
    for item in [
        f" {today['humidity']}%",
        f" {today['wind']}mph",
    ]:
        extra.append(c.label(item))
    today_left.append(extra)

    today_right = c.box('v')
    for item in [
        today['description'],
        f"Feels like {today['feels_like']}°",
        f"{today['quality']} air quality"
    ]:
        today_right.append(c.label(item, he=True, ha="end"))

    today_box.append(today_left)

    sun_box = c.box('v')
    try:
        sun_box.append(c.label(f' {today["sunset"]}pm'))
    except KeyError:
        sun_box.append(c.label(f' {today["sunrise"]}am'))
    today_box.append(sun_box)

    today_box.append(today_right)

    widget.append(today_box)

    hourly_container = c.box('v', spacing=10)
    hourly_container.append(c.label('Hourly forecast', he=True, ha="start"))
    hourly_box = c.box('h', style='box')
    for hour in cache['Hourly']['info']:
        hour_box = c.box('v', style='inner-box-wide')
        hour_box.append(c.label(f"{hour['temperature']}°"))
        hour_box.append(c.label(f"{hour['humidity']}%"))
        icon = c.label(hour['icon'], style='icon-small')
        icon.props.tooltip_text = hour['description']
        hour_box.append(icon)
        hour_box.append(c.label(hour['time']))
        hourly_box.append(hour_box)
        if hour != cache['Hourly']['info'][-1]:
            hourly_box.append(c.sep('v'))
    hourly_container.append(hourly_box)
    widget.append(hourly_container)

    daily_container = c.box('v', spacing=10)
    daily_container.append(c.label(
        'Daily forecast', style='title', ha='start'))
    daily_box = c.box('v', style='box')
    for day in cache['Daily']['info']:
        day_box = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        day_box.get_style_context().add_class('inner-box')
        day_box.set_start_widget(c.label(day['time']))
        day_box.set_end_widget(c.label(f"{day['high']}° / {day['low']}°"))
        icon = c.label(day['icon'])
        icon.props.tooltip_text = day['description']
        day_box.set_center_widget(icon)

        daily_box.append(day_box)
        if day != cache['Daily']['info'][-1]:
            daily_box.append(c.sep('h'))
    daily_container.append(daily_box)
    widget.append(daily_container)
    return widget


def updates(name, module, cache):
    """ Update widget """
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('Updates', style='heading')
    main_box.append(label)

    urls = {
        "Pacman": "https://archlinux.org/packages/",
        "AUR": "https://aur.archlinux.org/packages/",
        "Flatpak": "https://flathub.org/apps/search?q=",
    }

    commands = [
        info['command']
        for manager, info in cache['managers'].items()
        if info['packages']
    ] + ['echo "Packages updated, press enter to close terminal."', 'read x']

    def update_packages(widget, module):
        """ Update all packages """
        module.get_popover().popdown()
        Popen([
            cache['terminal'], 'sh', '-c',
            '; '.join(commands)
        ])

    def click_link(_, url):
        """ Click action """
        Popen(['xdg-open', url])

    for manager, info in cache['managers'].items():
        packages = info['packages']
        if not packages:
            continue
        manager_box = c.box('v', spacing=10)
        heading = c.label(
            f"{manager} ({len(packages)} updates)", style='title', ha='start')
        manager_box.append(heading)
        packages_box = c.box('v')
        scroll_box = c.scroll(0, 348)
        for package in packages:
            package_box = c.box('h', style='inner-box', spacing=20)
            package_label = c.button(package[0], style='minimal')
            try:
                package_label.connect(
                    'clicked', click_link,
                    f'{urls[manager]}{package[0]}')
            except KeyError:
                pass
            package_box.append(package_label)
            package_box.append(c.label(package[1], style='green-fg'))
            packages_box.append(package_box)
            if package != packages[-1]:
                packages_box.append(c.sep('h'))

        if len(packages) > 10:
            scroll_box.get_style_context().add_class('box')
            scroll_box.set_child(packages_box)
            manager_box.append(scroll_box)
        else:
            packages_box.get_style_context().add_class('box')
            manager_box.append(packages_box)

        main_box.append(manager_box)

    if cache:
        update_button = c.button(' Update all', style='box')
        update_button.connect('clicked', update_packages, module)
        main_box.append(update_button)

    return main_box


def git(name, module, cache):
    """ Git widget """
    commits = cache["commits"]

    main_box = c.box('v', spacing=20)
    main_box.get_style_context().add_class('widget-medium')
    main_box.append(c.label(cache["name"]))

    commits_box = c.box('v', spacing=10)
    commits_box.append(c.label('Commits'))
    scroll_holder = c.box('v', spacing=10)
    scroll_box = c.scroll(0, 700, style='scroll-mask')
    for commit, info in commits.items():
        commit_box = c.box('v', style='box')

        title_box = c.box('h', style='inner-box', spacing=20)
        title = c.label(info['msg'], length=30, ha='start')
        title.props.tooltip_text = info['msg']
        title_box.append(title)
        title_box.append(c.label(info['date']))
        commit_box.append(title_box)

        commit_box.append(c.sep('h'))

        file_box = c.box('v', style='inner-box')
        for file in info['files']:
            file_box.append(c.label(file))
        commit_box.append(file_box)

        bottom_box = c.box('h', style='inner-box')
        bottom_box.append(c.label(info['author']))
        bottom_box.append(c.label(commit))
        commit_box.append(bottom_box)

        scroll_holder.set_child(commit_box)
    if len(commits) > 5:
        scroll_box.set_child(scroll_holder)
        commits_box.append(scroll_box)
    else:
        commits_box.append(scroll_holder)
    main_box.append(commits_box)

    def update(event, module, cache):
        """ Update """
        module.get_popover().popdown()
        run(["git", "-C", cache["path"], "stash"])
        run(["git", "-C", cache["path"], "pull", "--rebase"])
        run(["swaymsg", "reload"])

    if commits:
        update_button = c.button(' Update', style='box')
        update_button.connect('clicked', update, module, cache)
        main_box.append(update_button)

    return main_box


def ups(name, module, cache):
    """ UPS widget """
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('UPS stats', style='heading')
    main_box.append(label)

    wide_box = c.box('h', spacing=20)
    wide_box.append(c.label(f"{cache['load_percent']}%"))
    detail_box = c.box('v')
    detail_box.append(c.label(f"{cache['runtime']} minutes"))
    detail_box.append(c.label("runtime"))
    wide_box.append(detail_box)
    main_box.append(wide_box)

    icons = {
        "load_watts": "W", "charging": "", "ac_power": "", "battery": ""}

    info_box = c.box('v', style='box')
    info_line = c.box('h')
    info_items = []
    for name, icon in icons.items():
        if isinstance(cache[name], bool):
            if cache[name]:
                info_items.append(icon)
        elif isinstance(cache[name], int):
            info_items.append(f"{icon} {cache[name]}")
    for item in info_items:
        info_line.append(c.label(item))
        if item != info_items[-1]:
            info_line.append(c.sep('v'))
    info_box.append(info_line)

    main_box.append(info_box)

    return main_box


def hoyo(name, module, cache):
    """ Genshin widget """
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label(cache['Name'], style='heading')
    main_box.append(label)

    # Icons
    icons = [{
        "Dailies completed": "", "Realm currency": "",
        "Remaining boss discounts": ""},
        {"Abyss progress": "", "Abyss stars": ""}]

    # Top section
    top_box = c.box('h', spacing=20)
    top_box.append(c.label(
        f"{cache['Icon']} {cache['Resin']}",
        style='today-weather', va='fill', ha='start'),
        False, False, 0)
    right_box = c.box('v')
    for line in [
        time_to_text(cache['Until next 40']),
        'until next 40'
    ]:
        right_box.append(c.label(line))
    top_box.append(right_box)
    main_box.append(top_box)

    # Info section
    info_box = c.box('v', style='box')
    for line in icons:
        info_line = c.box('h')
        for name, icon in line.items():
            try:
                label = c.label(f'{icon} {cache[name]}', style='inner-box')
                label.set_tooltip_text(name)
                info_line.append(label)
                if name != list(line)[-1]:
                    info_line.append(c.sep('v'))
            except KeyError:
                pass
        info_box.append(info_line)
        if line != list(icons)[-1]:
            info_box.append(c.sep('h'))

    main_box.append(info_box)

    return main_box


def power_supply(name, module, cache):
    """ Power supply widget """
    main_box = c.box('v', spacing=20, style='small-widget')
    outer_box = c.box('v', style='box')
    for device in cache:
            name, value = next(iter(device.items()))
            device_box = c.box('h', spacing=10, style="inner-box")
            device_box.append(c.label(name, ha="start"))
            device_box.append(c.level(0, 100, value * 25 if value != -1 else 0))
            if value != -1:
                device_box.append(c.label(f"{value*25}%", style='percent'))
            else:
                device_box.append(c.label("??%", style='percent'))
            outer_box.append(device_box)
            if device != list(cache)[-1]:
                outer_box.append(c.sep('v'))
    main_box.append(outer_box)
    return main_box


def xdrip(name, module, cache):
    """ XDrip widget """
    main_box = c.box('v', spacing=20)
    main_box.append(c.label('XDrip+'))

    wide_box = c.box('h', spacing=20)
    sgv_box = c.box('h', spacing=5)
    sgv_box.append(c.label(
        f"{cache['sgv']}", style='large-text'))
    sgv_box.append(c.label(cache['direction']))
    wide_box.append(sgv_box)
    detail_box = c.box('v')
    detail_box.append(c.label(f"{cache['since_last']} minutes ago"))
    wide_box.append(detail_box)
    main_box.append(wide_box)

    bottom_box = c.box('h', style='box')
    items = [f" {cache['delta']}", f" {cache['date']}"]
    for item in items:
        bottom_box.append(c.label(item))
        if item != items[-1]:
            bottom_box.append(c.sep('v'))
    main_box.append(bottom_box)

    return main_box


def network(name, module, cache):
    """ Network widget """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Network'))

    names = {
        'GENERAL.DEVICE': 'Device', "GENERAL.CONNECTION": "SSID",
        'IP4.ADDRESS[1]': 'IP'
    }

    for device in cache['Network']:
        if '(connected)' not in device['GENERAL.STATE']:
            continue
        network_box = c.box('v', spacing=10)
        network_box.append(c.label(
            device['GENERAL.TYPE'], style='title', ha='start'))
        device_box = c.box('v', style='box')
        for long, short in names.items():
            if short == 'SSID' and device['GENERAL.TYPE'] != 'wifi':
                continue
            line = c.box('h', style='inner-box')
            line.append(c.label(short))
            line.append(c.label(device[long]))
            device_box.append(line)
            if long != list(names)[-1]:
                device_box.append(c.sep('h'))
        network_box.append(device_box)

        main_box.append(network_box)

    return main_box


def power_action(button, command):
    """ Action for power menu buttons """
    run(command, check=False, capture_output=False)


def power():
    main_box = c.box('v', spacing=30)
    # main_box.append(c.label('Power menu'))

    buttons = {
        "Lock  ": ["swaylock"],
        "Log out  ": ["swaymsg", "exit"],
        "Suspend  ": ["systemctl", "suspend"],
        "Reboot  ": ["systemctl", "reboot"],
        "Reboot to UEFI  ": ["systemctl", "reboot", "--firmware-setup"],
        "Shut down  ": ["systemctl", "poweroff"],
    }

    power_box = c.box('v', style='box')
    for icon, command in buttons.items():
        button = c.button(label=icon, ha='end', style='power-item')
        button.connect('clicked', power_action, command)
        power_box.append(button)
        if icon != list(buttons)[-1]:
            power_box.append(c.sep('h'))
    main_box.append(power_box)

    return main_box


def sales(name, module, cache):
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    main_box.append(c.label('Sales'))

    total = 0
    for order in cache["orders"]:
        order_box = c.box('v', style='box')
        for item in order:
            line = c.box('h', style='inner-box', spacing=20)
            line.append(c.label(f"{item['item']}"))
            line.append(c.label(f"x{item['quantity']}"))
            line_total = item['price'] * item['quantity']
            price = c.label(f"${line_total:.2f}")
            total += line_total
            c.add_style(price, 'green-fg')
            line.append(price)
            order_box.append(line)
        main_box.append(order_box)
    total_box = c.box('h', style='inner-box')
    total_box.append(c.label('Total'))
    total_box.append(
        c.label(f'${total:.2f}', ha='end', style='green-fg'), 0, 0, 0)
    main_box.append(total_box)

    return main_box


def time_to_text(time_string) -> str:
    """ Convert time to text string """
    hours = int(time_string.split(':')[0])
    mins = int(time_string.split(':')[1])
    output = []
    for unit, value in {"hour": hours, "minute": mins}.items():
        if value > 1:
            output.append(f'{value} {unit}s')
        if value == 1:
            output.append(f'{value} {unit}')
    return " ".join(output)
