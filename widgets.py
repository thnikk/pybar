#!/usr/bin/python3 -u
"""
Description: Widgets
Author: thnikk
"""
import common as c


def generic_widget(name, cache):
    """ Generic widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label(name.capitalize(), style='heading')
    main_box.add(label)

    for category, items in cache.items():
        category_box = c.box('v', spacing=10)
        category_box.add(c.label(category, style='title', ha='start'))
        item_box = c.box('v', style='box')
        for item in items:
            item_box.add(c.label(item, style='inner-box'))
            if item != items[-1]:
                item_box.add(c.sep('h'))
        category_box.add(item_box)
        main_box.add(category_box)

    return main_box


def weather_widget(cache):
    """ Weather widget """
    widget = c.box('v', style='widget', spacing=20)

    today = cache['Today']['info'][0]
    today_box = c.box('h', spacing=10)

    today_left = c.box('v')
    widget.add(c.label(cache['City'], style='heading'))
    temp = c.label(
        f"{today['temperature']}° {today['icon']}", 'today-weather')
    today_left.add(temp)

    extra = c.h_lines([
        f" {today['humidity']}%",
        f" {today['wind']}mph",
    ], style='extra')
    today_left.add(extra)

    today_right = c.box('v')
    today_right.pack_start(c.v_lines([
        today['description'],
        f"Feels like {today['feels_like']}°",
        f"{today['quality']} air quality"
    ], right=True), True, False, 0)

    today_box.pack_start(today_left, False, False, 0)

    sun_box = c.box('v')
    try:
        sun_box.add(c.label(f' {today["sunset"]}pm', 'sun'))
    except KeyError:
        sun_box.add(c.label(f' {today["sunrise"]}am', 'sun'))
    today_box.pack_start(sun_box, False, False, 0)

    today_box.pack_end(today_right, False, False, 0)

    widget.add(today_box)

    hourly_container = c.box('v', spacing=10)
    hourly_container.add(c.label('Hourly forecast', style='title', ha="start"))
    hourly_box = c.box('h', style='box')
    for hour in cache['Hourly']['info']:
        hour_box = c.box('v', style='inner-box-wide')
        hour_box.add(c.label(f"{hour['temperature']}°", style='hour-temp'))
        hour_box.add(c.label(f"{hour['humidity']}%"))
        icon = c.label(hour['icon'], style='icon-small')
        icon.props.tooltip_text = hour['description']
        hour_box.add(icon)
        hour_box.add(c.label(hour['time']))
        hourly_box.pack_start(hour_box, True, False, 0)
        if hour != cache['Hourly']['info'][-1]:
            hourly_box.add(c.sep('v'))
    hourly_container.add(hourly_box)
    widget.add(hourly_container)

    daily_container = c.box('v', spacing=10)
    daily_container.add(c.label(
        'Daily forecast', style='title', ha='start'))
    daily_box = c.box('v', style='box')
    for day in cache['Daily']['info']:
        day_box = c.box('h', style='inner-box')
        day_box.add(c.label(day['time']))
        day_box.pack_end(
            c.label(f"{day['high']}° / {day['low']}°"), False, False, 0)
        icon = c.label(day['icon'])
        icon.props.tooltip_text = day['description']
        day_box.set_center_widget(icon)

        daily_box.add(day_box)
        if day != cache['Daily']['info'][-1]:
            daily_box.add(c.sep('h'))
    daily_container.add(daily_box)
    widget.add(daily_container)
    return widget


def updates_widget(info):
    """ Update widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('Updates', style='heading')
    main_box.add(label)

    urls = {
        "Pacman": "https://archlinux.org/packages/",
        "AUR": "https://aur.archlinux.org/packages/",
        "Flatpak": "https://flathub.org/apps/search?q=",
    }

    for manager, packages in info.items():
        if not packages:
            continue
        manager_box = c.box('v', spacing=10)
        heading = c.label(manager, style='title', ha='start')
        manager_box.add(heading)
        packages_box = c.box('v')
        scroll_box = c.scroll(0, 348)
        for package in packages:
            package_box = c.box('h', style='inner-box', spacing=20)
            package_label = c.button(package[0], style='none')
            try:
                package_label.connect(
                    'clicked', c.click_link,
                    f'{urls[manager]}{package[0]}')
            except KeyError:
                pass
            package_box.pack_start(package_label, False, False, 0)
            package_box.pack_end(
                c.label(package[1], style='green-fg'), False, False, 0)
            packages_box.add(package_box)
            if package != packages[-1]:
                packages_box.pack_start(c.sep('h'), 1, 1, 0)

        if len(packages) > 10:
            scroll_box.get_style_context().add_class('box')
            scroll_box.add(packages_box)
            manager_box.add(scroll_box)
        else:
            packages_box.get_style_context().add_class('box')
            manager_box.add(packages_box)

        main_box.add(manager_box)

    return main_box


def git_widget(cache):
    """ Git widget """
    commits = cache["commits"]

    main_box = c.box('v', style='widget', spacing=20)
    main_box.get_style_context().add_class('wide')
    main_box.add(c.label(cache["name"], style='heading'))

    commits_box = c.box('v', spacing=10)
    commits_box.add(c.label('Commits', style='title', ha='start'))
    scroll_holder = c.box('v', spacing=10)
    scroll_box = c.scroll(0, 700, style='scroll-mask')
    for commit, info in commits.items():
        commit_box = c.box('v', style='box')

        title_box = c.box('h', style='inner-box', spacing=20)
        title = c.label(info['msg'], length=100, ha='start')
        title.props.tooltip_text = info['msg']
        title_box.add(title)
        title_box.pack_end(c.label(info['date'], style='green-fg'), 0, 0, 0)
        commit_box.add(title_box)

        commit_box.add(c.sep('h'))

        file_box = c.box('v', style='inner-box')
        for file in info['files']:
            file_box.add(c.label(file, ha='start'))
        commit_box.add(file_box)

        bottom_box = c.box('h', style='inner-box')
        bottom_box.pack_end(c.label(info['author']), 0, 0, 0)
        bottom_box.pack_start(c.label(commit, style='blue-fg'), 0, 0, 0)
        commit_box.add(bottom_box)

        scroll_holder.add(commit_box)
    if len(commits) > 5:
        scroll_box.add(scroll_holder)
        commits_box.add(scroll_box)
    else:
        commits_box.add(scroll_holder)
    main_box.add(commits_box)

    return main_box


def ups_widget(cache):
    """ UPS widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('UPS stats', style='heading')
    main_box.add(label)

    wide_box = c.box('h', spacing=20)
    wide_box.add(c.label(f"{cache['load_percent']}%", style='today-weather'))
    detail_box = c.box('v')
    detail_box.add(c.label(f"{cache['runtime']} minutes"))
    detail_box.add(c.label("runtime", ha='end'))
    wide_box.pack_end(detail_box, 0, 0, 0)
    main_box.add(wide_box)

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
        info_line.pack_start(c.label(item, style='inner-box'), 1, 0, 0)
        if item != info_items[-1]:
            info_line.add(c.sep('v'))
    info_box.add(info_line)

    main_box.add(info_box)

    return main_box


def hoyo_widget(cache, game):
    """ Genshin widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label(cache['Name'], style='heading')
    main_box.add(label)

    # Top section
    top_box = c.box('h', spacing=20)
    top_box.pack_start(c.label(
        f"{cache['Icon']} {cache['Resin']}",
        style='today-weather', va='fill', ha='start'),
        False, False, 0)
    right_box = c.box('v')
    for line in [
        time_to_text(cache['Until next 40']),
        'until next 40'
    ]:
        right_box.pack_start(c.label(line, ha='end'), 0, 0, 0)
    top_box.pack_end(right_box, False, False, 0)
    main_box.add(top_box)

    # Info section
    info_box = c.box('v', style='box')
    info = convert_list(cache)
    for line in info:
        info_line = c.box('h')
        for item in line:
            info_line.pack_start(
                c.label(item, style='inner-box'), True, False, 0)
            if item != line[-1] and item:
                info_line.pack_start(c.sep('v'), 0, 0, 0)
        info_box.pack_start(info_line, 0, 0, 0)
        if line != info[-1] and line:
            info_box.pack_start(c.sep('h'), 0, 0, 0)
    main_box.add(info_box)

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


def convert_list(info) -> list:
    """ test """
    icons = [
        {
            "Dailies completed": "",
            "Realm currency": "",
            "SU weekly score": "",
            "Remaining boss discounts": ""
        },
        {
            "Abyss progress": "", "Abyss stars": ""
        }
    ]

    output = []
    for group in icons:
        line = []
        for item, icon in group.items():
            try:
                line.append(f'{icon} {info[item]}')
            except KeyError:
                pass
        output.append(line)
    return output
