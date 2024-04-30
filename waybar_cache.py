#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output
import json
import time
import os


def save_cache(name, command, interval):
    """ Save command output to cache file """
    while True:
        command = [os.path.expanduser(arg) for arg in command]
        with open(
            os.path.expanduser(f'~/.cache/pybar/{name}.json'),
            'w', encoding='utf-8'
        ) as file:
            file.write(json.loads(check_output(command)))
        time.sleep(interval)
