#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import os
import json
import concurrent.futures
import argparse
from bar import Bar
import modules


def load_config():
    """ Load config from file """
    config_path = os.path.expanduser('~/.config/pybar/')
    if not os.path.exists(config_path):
        return {"modules-right": [], "modules-center": [], "modules-left": []}
    with open(
        os.path.expanduser('~/.config/pybar/config.json'),
        'r', encoding='utf=8'
    ) as file:
        return json.loads(file.read())


def parse_args() -> argparse.ArgumentParser:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', type=int, default=None)
    return parser.parse_args()


def main():
    """ Main function """
    executor = concurrent.futures.ThreadPoolExecutor()
    args = parse_args()
    config = load_config()

    try:
        for name, info in config['modules'].items():
            executor.submit(
                modules.cache, name, info['command'], info['interval'])
    except KeyError:
        pass

    # try:
    #     icons = config["workspaces"]
    # except KeyError:
    #     icons = {}

    # modules_left = [
    #     modules.module(name) for name in config["modules-left"]
    # ]
    #
    # modules_center = [
    #     modules.module(name) for name in config["modules-center"]
    # ]
    #
    # modules_right = [
    #     modules.module(name) for name in config["modules-right"]
    # ]

    pybar = Bar(args.output, spacing=5)
    pybar.css('style.css')

    for section_name, section in {
        "modules-left": pybar.left, "modules-center": pybar.center,
        "modules-right": pybar.right
    }.items():
        for name in config[section_name]:
            section.add(modules.module(name))
    #
    # for module in modules_left:
    #     pybar.left.pack_start(module, 0, 0, 0)
    # for module in modules_center:
    #     pybar.center.pack_start(module, 0, 0, 0)
    # for module in modules_right:
    #     pybar.right.pack_start(module, 0, 0, 0)

    executor.submit(pybar.start)


if __name__ == "__main__":
    main()
