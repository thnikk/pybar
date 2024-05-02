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
    parser.add_argument('-o', '--output', type=str, default=None,
                        help='Comma-separated list of outputs for the bar '
                        'to appear on.')
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

    if args.output:
        outputs = args.output.split(',')
    else:
        outputs = [None]

    for output in outputs:
        pybar = Bar(output, spacing=5)
        css_path = "/".join(__file__.split('/')[:-1]) + '/style.css'
        pybar.css(css_path)

        for section_name, section in {
            "modules-left": pybar.left, "modules-center": pybar.center,
            "modules-right": pybar.right
        }.items():
            for name in config[section_name]:
                section.add(modules.module(name))

        executor.submit(pybar.start)


if __name__ == "__main__":
    main()
