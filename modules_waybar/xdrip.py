#!/usr/bin/python3
"""
Description: Waybar module for use with xdrip+ using the web service API
Shows sgv on bar and time since last received value and delta in the tooltip
Author: thnikk
"""
import json
from datetime import datetime, timezone
import os
import configparser
import sys
import requests
from modules_waybar.common import print_debug, Cache


def get_config() -> configparser.ConfigParser:
    """ Get config """
    config_file = os.path.expanduser("~/.config/beetus.ini")
    if not os.path.exists(config_file):
        with open(config_file, "a", encoding='utf-8') as f:
            f.write("[settings]\napi_secret = \nip = \nport = ")
            f.close()
    config = configparser.ConfigParser()
    config.read(config_file)
    return config


def print_error_to_bar(string):
    """ Print an error to the bar and exit """
    print(json.dumps({"text": string}))
    sys.exit(1)


def config_check(config):
    """ Check config file for values """
    check_values = ['api_secret', 'ip', 'port']
    for key in list(config['settings']):
        check_values.remove(key)
    if check_values:
        print_error_to_bar(
            f"Set {' and '.join(check_values)} in ~/.config/beetus.ini"
        )
        sys.exit(1)


def get_data(config):
    """ Get new data from API """
    # Build header for http request with api key
    h = {"api-secret": config['settings']['api_secret']}
    cache = Cache(os.path.expanduser("~/.cache/beetus.json"))
    try:
        data = requests.get((f"http://{config['settings']['ip']}:"
                            f"{config['settings']['port']}/sgv.json"),
                            headers=h, timeout=3).json()
        cache.save(data)
    except requests.exceptions.ConnectionError:
        try:
            data = cache.load()
        except FileNotFoundError:
            print_debug('Something is fucked up, bruh.')
            print_error_to_bar("Couldn't connect to api or use cache file.")
            sys.exit(1)
    return data


def module(_):
    """ Module """
    config = get_config()
    config_check(config)

    data = get_data(config)

    sgv = data[0]["sgv"]
    delta = data[0]["delta"]
    direction = data[0]["direction"]
    date = datetime.strptime(data[0]["dateString"], "%Y-%m-%dT%H:%M:%S.%f%z")
    now = datetime.now(timezone.utc)

    since_last = int((now - date).total_seconds() / 60)

    arrows = {
        "DoubleUp": "↑↑",
        "SingleUp": "↑",
        "FortyFiveUp": "↗️",
        "Flat": "→",
        "FortyFiveDown": "↘️",
        "SingleDown": "↓",
        "DoubleDown": "↓↓"
    }

    out_dict = {
        "text": f" {sgv} {arrows[direction]}",
        "tooltip": f"{since_last} minute(s) ago\ndelta: {delta}",
        "widget": {
            "sgv": sgv,
            "delta": delta,
            "direction": arrows[direction],
            "date": date.strftime("%m/%d/%y %H:%M:%S"),
            "since_last": since_last
        }
    }

    if sgv < 80:
        out_dict['class'] = 'red'
    elif sgv > 180:
        out_dict['class'] = 'orange'
    if since_last > 5:
        out_dict['class'] = 'gray'

    return out_dict


def main():
    """ Main function """
    print(json.dumps(module(), indent=4))


if __name__ == "__main__":
    main()
