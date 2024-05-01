#!/usr/bin/python3 -u
"""
Description: Genshin widget
Author: thnikk
"""
import argparse
import os
import json
import common as c


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
