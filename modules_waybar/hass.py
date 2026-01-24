#!/usr/bin/python3 -u
"""
Description: Simple Home Assistant module for showing sensor data
Author: thnikk
"""
import requests
import time

HISTORY = {}


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

    sensor = config['sensor']
    history_len = config.get('history', 100)
    
    try:
        val = float(data['state'])
        if sensor not in HISTORY:
            HISTORY[sensor] = []
        HISTORY[sensor].append({"val": val, "time": time.time()})
        if len(HISTORY[sensor]) > history_len:
            HISTORY[sensor].pop(0)
    except (ValueError, KeyError):
        pass

    history_data = HISTORY.get(sensor, [])
    duration = 0
    if len(history_data) > 1:
        duration = history_data[-1]['time'] - history_data[0]['time']

    output = {
        "text": config['format'].replace('{}', data['state'].split('.')[0]),
        "widget": {
            "name": data['attributes'].get('friendly_name', sensor),
            "state": data['state'],
            "unit": data['attributes'].get('unit_of_measurement', ''),
            "history": [i['val'] for i in history_data],
            "duration": duration,
            "min": config.get('min'),
            "max": config.get('max')
        }
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
