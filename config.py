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
            "modules-left": ["workspaces", "privacy"],
            "modules-center": ["updates"],
            "modules-right": [
                "weather", "volume", "network", "clock", "power"],
            "modules": {
                "weather": {
                    "zip_code": "94102"
                },
                "updates": {
                    "interval": 300
                },
                "network": {
                    "always_show": True,
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
