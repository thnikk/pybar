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

    info_box = c.box('v', style='events-box')
    for key, value in info.items():
        info_box.add(c.label(f"{key}: {value}", style='event-box'))
        if key != list(info)[-1]:
            info_box.add(c.sep('h'))

    main_box.add(info_box)

    return main_box
