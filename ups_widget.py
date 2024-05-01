#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import common as c


def ups_widget(info):
    """ UPS widget """
    main_box = c.box('v', style='widget', spacing=20)
    label = c.label('UPS stats', style='heading')
    main_box.add(label)

    wide_box = c.box('h', spacing=20)
    wide_box.add(c.label(f"{info['load_percent']}%", style='today-weather'))
    detail_box = c.box('v')
    detail_box.add(c.label(f"{info['runtime']} minutes"))
    detail_box.add(c.label("runtime", ha='end'))
    wide_box.pack_end(detail_box, 0, 0, 0)
    main_box.add(wide_box)

    icons = {"load_watts": "W", "charging": "", "ac_power": "", "battery": ""}
    # for item, icon in icons.items():
    #     pass

    info_box = c.box('v', style='events-box')
    info_line = c.box('h')
    for name, icon in icons.items():
        if isinstance(info[name], bool):
            if info[name]:
                info_line.pack_start(c.label(icon, style='event-box'), 1, 0, 0)
        elif isinstance(info[name], int):
            info_line.pack_start(c.label(
                f"{icon} {info[name]}", style='event-box'), 1, 0, 0)
    info_box.add(info_line)
    # for key, value in info.items():
    #     info_box.add(c.label(f"{key}: {value}", style='event-box'))
    #     if key != list(info)[-1]:
    #         info_box.add(c.sep('h'))

    main_box.add(info_box)

    return main_box
