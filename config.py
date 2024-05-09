#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json


def load():
    """ Load config from file """
    config_path = os.path.expanduser('~/.config/pybar/')
    if not os.path.exists(config_path):
        os.makedirs(config_path)
        default_config = {
            "workspaces": {},
            "modules-left": ["workspaces"],
            "modules-center": ["updates"],
            "modules-right": ["volume", "network", "clock", "power"],
            "modules": {
                "updates": {
                    "command": ["~/.local/bin/bar/updates.py"],
                    "interval": 300
                },
                "network": {
                    "command": ["~/.local/bin/bar/network.py"],
                    "interval": 60
                }
            }
        }
        with open(f"{config_path}/config.json", 'w', encoding='utf-8') as file:
            file.write(json.dumps(default_config, indent=4))
        return default_config
    with open(
        os.path.expanduser('~/.config/pybar/config.json'),
        'r', encoding='utf=8'
    ) as file:
        return json.loads(file.read())
