#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import common as c


def ups_widget(info):
    """ UPS widget """
    main_box = c.box('v', style='widget', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label('UPS stats', style='heading')
    main_box.add(label)

    wide_box = c.box('h', spacing=20)
    wide_box.add(c.label(f"{info['load_percent']}%", style='today-weather'))
    detail_box = c.box('v')
    detail_box.add(c.label(f"{info['runtime']} minutes"))
    detail_box.add(c.label("runtime", ha='end'))
    wide_box.pack_end(detail_box, 0, 0, 0)
    main_box.add(wide_box)

    icons = {
        "load_watts": "W", "charging": "", "ac_power": "", "battery": ""}

    info_box = c.box('v', style='box')
    info_line = c.box('h')
    info_items = []
    for name, icon in icons.items():
        if isinstance(info[name], bool):
            if info[name]:
                info_items.append(icon)
        elif isinstance(info[name], int):
            info_items.append(f"{icon} {info[name]}")
    for item in info_items:
        info_line.pack_start(c.label(item, style='inner-box'), 1, 0, 0)
        if item != info_items[-1]:
            info_line.add(c.sep('v'))
    info_box.add(info_line)

    main_box.add(info_box)

    return main_box
