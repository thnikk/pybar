#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import time
import common as c


def waybar_module(label, command, interval):
    """ d """
    while True:
        output = c.dict_from_cmd(command)
        if output['text']:
            label.set_visible(True)
        else:
            label.set_visible(False)
        label.set_label(output['text'])
        try:
            label.get_style_context().add_class(output['class'])
        except KeyError:
            pass
        try:
            label.props.tooltip_markup = output['tooltip']
        except KeyError:
            pass
        time.sleep(interval)
