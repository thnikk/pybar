#!/usr/bin/python3 -u
"""
Description: Genshin widget
Author: thnikk
"""
import argparse
import os
import json
import common as c


def hoyo_widget(game):
    """ Genshin widget """
    main_box = c.box('v', style='widget', spacing=20)

    with open(
        os.path.expanduser('~/.cache/hoyo-stats.json'), 'r', encoding='utf-8'
    ) as file:
        cache = json.loads(file.read())[game]

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
        right_box.add(c.label(line, ha='end'))
    top_box.pack_end(right_box, False, False, 0)
    main_box.add(top_box)

    # Info section
    info_section = c.box('v', spacing=10)
    info_box = c.box('v', style='box')
    info = convert_list(cache)
    for line in info:
        info_line = c.box('h')
        for item in line:
            info_line.pack_start(
                c.label(item, style='inner_box'), True, False, 0)
            if item != line[-1] and item:
                info_line.add(c.sep('v'))
            info_box.add(info_line)
        if line != info[-1] and line:
            info_box.add(c.sep('h'))
    info_section.add(info_box)
    main_box.add(info_section)

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
