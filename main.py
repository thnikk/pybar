#!/usr/bin/python3 -u
"""
Description:
Author:
"""
import concurrent.futures
import argparse
import sway
import config as Config
from bar import Bar
import modules


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
    config = Config.load()

    try:
        for name, info in config['modules'].items():
            executor.submit(
                modules.cache, name, info['command'], info['interval'])
    except KeyError:
        pass

    executor.submit(sway.cache)

    if args.output:
        outputs = args.output.split(',')
    else:
        outputs = [None]

    for output in outputs:
        pybar = Bar(output, spacing=5)
        css_path = "/".join(__file__.split('/')[:-1]) + '/style.css'
        pybar.css(css_path)
        pybar.css('~/.config/pybar/style.css')

        for section_name, section in {
            "modules-left": pybar.left, "modules-center": pybar.center,
            "modules-right": pybar.right
        }.items():
            for name in config[section_name]:
                section.add(modules.module(name))

        executor.submit(pybar.start)


if __name__ == "__main__":
    main()
