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
            "modules-center": [],
            "modules-right": ["clock"],
            "modules": {
                "test": {
                    "command": ["test"],
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
