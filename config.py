#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import re


def load(path):
    """ Load config from file """
    config_path = os.path.expanduser(path)
    if not os.path.exists(config_path):
        os.makedirs(config_path)
        default_config = """// vim:ft=jsonc
{
    "modules-left": ["workspaces", "privacy"],
    "modules-center": ["updates"],
    "modules-right": [
        "weather", "volume", "network", "tray", "clock", "power"],
    "popover-autohide": true,
    "popover-exclusive": false,
    "modules": {
        "weather": {
            "zip_code": "94102"
        },
        "updates": {
            "interval": 300
        },
        "network": {
            "always_show": true
        }
    }
}"""
        with open(f"{config_path}/config.json", 'w', encoding='utf-8') as file:
            file.write(default_config)
        output = default_config
        output = re.sub(re.compile(r"/\*.*?\*/", re.DOTALL), "", output)
        output = re.sub(re.compile(r"//.*?\n"), "", output)
        return json.loads(output)
    with open(
        os.path.expanduser(f'{config_path}/config.json'),
        'r', encoding='utf=8'
    ) as file:
        output = file.read()
        output = re.sub(re.compile(r"/\*.*?\*/", re.DOTALL), "", output)
        output = re.sub(re.compile(r"//.*?\n"), "", output)
        return json.loads(output)
