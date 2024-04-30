#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output
import json
import os
import time
import gi
import common as c
gi.require_version('Gtk', '3.0')
from gi.repository import GLib


def cache(name, command, interval):
    """ Save command output to cache file """
    while True:
        command = [os.path.expanduser(arg) for arg in command]
        with open(
            os.path.expanduser(f'~/.cache/pybar/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            file.write(check_output(command).decode())
        time.sleep(interval)


def module(name):
    """ Waybar module """
    button = c.button(style='module')
    button.hide()

    def get_output():
        try:
            with open(
                os.path.expanduser(f'~/.cache/pybar/{name}.json'),
                'r', encoding='utf-8'
            ) as file:
                output = json.loads(file.read())
            button.set_label(output['text'])
            if output['tooltip']:
                button.set_tooltip_markup(output['tooltip'])
            button.show()
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            pass
        return True
    if get_output():
        GLib.timeout_add(1000, get_output)
        return button
