#!/usr/bin/python3 -u
"""
Description: Network module
Author: thnikk
"""
from subprocess import run
import json
import argparse
import sys


def get_args() -> argparse.ArgumentParser:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-d', action='store_true',
        help='Only show when no connection is available')
    return parser.parse_args()


def get_devices():
    """ Get active NetworkManager connections """
    raw = run(
        ['nmcli', 'd', 'show'], check=True,
        capture_output=True).stdout.decode('utf-8')
    devices = raw.split('\n\n')
    output = [
        {
            line.split(':')[0]: ":".join(line.split(':')[1:]).strip()
            for line in device.splitlines()}
        for device in devices
    ]
    return output


def module(config):
    """ Module """
    devices = get_devices()
    icons = {"ethernet": "", "wifi": "", "wifi-p2p": ""}
    connection_type = None
    connection_ip = None
    for device in devices:
        if '(connected)' in device['GENERAL.STATE']:
            connection_type = device['GENERAL.TYPE']
            connection_ip = device['IP4.ADDRESS[1]'].split('/')[0]

    if 'always_show' not in config:
        config['always_show'] = True
    if not config['always_show']:
        if not connection_type:
            return {"text": " "}
        else:
            return {"text": ""}
        sys.exit(0)

    if connection_type and connection_ip:
        return {
            "text": icons[connection_type],
            "tooltip": f"{connection_type}\n{connection_ip}",
            "widget": {"Network": [
                device for device in devices
            ]}
        }
    else:
        return {"text": ""}


def main():
    """ Main function """
    args = get_args()
    print(json.dumps(module(args.d), indent=4))


if __name__ == "__main__":
    main()
