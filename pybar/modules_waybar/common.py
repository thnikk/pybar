#!/usr/bin/python3 -u
"""
Description: Common library
Author: thnikk
"""
import os
import sys
from datetime import datetime, timedelta
import time
import inspect
import json
import requests


def ellipse(string, length=20) -> str:
    """ Ellipse string past length """
    if len(string) > length:
        return f"{string[:length-3]}..."
    return string[:length]


def get_request(url, retries=3, timeout=3) -> dict:
    """ Auto-retry requests """
    for x in range(1, retries):
        try:
            return requests.get(url, timeout=timeout).json()
        except requests.exceptions.ConnectionError:
            print_debug(f"Request failed, trying again (attempt {x}).")
            time.sleep(3)
    raise ValueError


def colorize(text, color) -> str:
    """ Colorize tooltip text """
    return f'<span color="{color}">{text}</span>'


def print_debug(msg) -> None:
    """ Print debug message """
    # Get filename of program calling this function
    frame = inspect.stack()[1]
    name = frame[0].f_code.co_filename.split('/')[-1].split('.')[0]
    # Color the name using escape sequences
    colored_name = f"\033[38;5;3m{name}\033[0;0m"
    # Get the time in the same format as waybar
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    # Print the debug message
    print(f'[{timestamp}] [{colored_name}] {msg}', file=sys.stderr)


def print_bar(waybar_dict) -> None:
    """ Print output to bar """
    print(json.dumps(waybar_dict))


class Cache:
    """ Cache managment """
    def __init__(self, cache_file):
        self.cache_file = cache_file

    def save(self, cache):
        """ Save cache to file """
        with open(self.cache_file, 'w', encoding='utf-8') as file:
            file.write(json.dumps(cache, indent=4))

    def load(self):
        """ Load cache from file """
        with open(self.cache_file, 'r', encoding='utf-8') as file:
            return json.loads(file.read())


class Cache2:
    """ Cache managment """
    def __init__(self, cache_file, max_age=timedelta(minutes=5)):
        self.cache_file = os.path.expanduser(cache_file)
        self.cache_full = self.load()
        self.cache = self.cache_full['data']
        self.timestamp = self.cache_full['timestamp']
        self.max_age = max_age
        self.stale = self.stale_check()

    def save(self, cache):
        """ Save cache to file """
        with open(self.cache_file, 'w', encoding='utf-8') as file:
            file.write(json.dumps({
                "data": cache,
                "timestamp": datetime.now().timestamp()
            }, indent=4))

    def load(self):
        """ Load cache from file """
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as file:
                return json.loads(file.read())
        except (FileNotFoundError, json.decoder.JSONDecodeError):
            return {"data": {}, "timestamp": ""}

    def stale_check(self):
        """ Check if stale """
        try:
            timestamp = datetime.fromtimestamp(self.timestamp)
            return (datetime.now() - timestamp) > self.max_age
        except (KeyError, TypeError):
            return True
