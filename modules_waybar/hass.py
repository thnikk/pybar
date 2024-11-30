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

    if data['state'] == 'unavailable':
        return {"text": ""}

    output = {
        "text": config['format'].replace('{}', data['state'].split('.')[0])
    }
    try:
        tooltip = []
        for name, item in config['widget'].items():
            data = get_data(config['server'], item, config['bearer_token'])
            tooltip.append(
                f"{name}: {data['state']}"
                f"{data['attributes']['unit_of_measurement']}"
            )
        output['tooltip'] = "\n".join(tooltip)
    except (NameError, KeyError):
        pass
    return output
