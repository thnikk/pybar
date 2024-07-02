#!/usr/bin/python3 -u
"""
Description: Simple Home Assistant module for showing sensor data
Author: thnikk
"""
import requests


def get_data(server, sensor, bearer_token):
    """ Get HomeAssistant data for sensor """
    response = requests.get(
        f"http://{server}/api/states/{sensor}",
        headers={
            "Authorization": bearer_token,
            "content-type": "application/json",
        },
        timeout=3
    ).json()
    return response


def module(config):
    """ Module """
    data = get_data(config['server'], config['sensor'], config['bearer_token'])
    return {
        "text": config['format'].replace('{}', data['state'].split('.')[0])
    }
