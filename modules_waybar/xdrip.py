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
from modules_waybar.common import Cache


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


def get_data(config):
    """ Get new data from API """
    # Build header for http request with api key
    h = {"api-secret": config['api_secret']}
    cache = Cache(os.path.expanduser("~/.cache/beetus.json"))
    try:
        data = requests.get((f"http://{config['ip']}:"
                            f"{config['port']}/sgv.json"),
                            headers=h, timeout=3).json()
        cache.save(data)
    except requests.exceptions.ConnectionError:
        try:
            data = cache.load()
        except FileNotFoundError:
            print("Couldn't connect to api or use cache file.",
                  file=sys.stderr)
            sys.exit(1)
    return data


def module(config):
    """ Module """
    if (
        "ip" not in list(config) or
        "port" not in list(config) or
        "api_secret" not in list(config)
    ):
        return None

    try:
        data = get_data(config)
    except (requests.exceptions.ReadTimeout, TimeoutError):
        return None

    sgv = data[0]["sgv"]
    try:
        last_sgv = data[1]["sgv"]
    except IndexError:
        last_sgv = sgv
    delta = sgv - last_sgv
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
        "widget": {
            "sgv": sgv,
            "delta": delta,
            "direction": arrows[direction],
            "date": date.strftime("%m/%d/%y %I:%M:%S %p"),
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
