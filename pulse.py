#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output
import json
import argparse


def parse_args() -> argparse.ArgumentParser:
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('-w', '--whitelist', type=str)
    parser.add_argument('-s', '--switch', action='store_true')
    parser.add_argument('-v', '--volume', type=int)
    return parser.parse_args()


class Pulse():
    """ d """
    def __init__(self):
        self.sinks = self.get_sinks('sinks')
        self.sink_inputs = self.get_sinks('sink-inputs')

    def get_sinks(self, sink_type, whitelist=None) -> dict:
        """ Get pulse sinks """
        raw_output = check_output(
            ['pactl', 'list', sink_type]).decode().split('\n\n')

        sinks = []
        for item in raw_output:
            sink = {}
            for line in item.splitlines():
                for char in ['=', ':', '#']:
                    if char in line:
                        if not line.split(char)[1]:
                            continue
                        sink[
                            line.split(char)[0].strip()
                        ] = ":".join(
                            line.split(char)[1:]).strip().replace('\"', '')
                        break
            if whitelist:
                for item in whitelist:
                    if item.lower() in sink["Description"].lower():
                        sinks.append(sink)
                        break
            else:
                sinks.append(sink)

        return sinks

    def get_default_sink(self) -> str:
        """ Get default pulse sink """
        return check_output(['pactl', 'get-default-sink']).decode().strip()

    def set_default_sink(self, sink) -> None:
        """ Set default sink """
        check_output(['pactl', 'set-default-sink', sink])

    def inc_default_sink(self, whitelist) -> None:
        """ Increment default sink """
        devices = [
            sink["Name"]
            for sink in self.get_sinks('sinks', whitelist)
        ]
        index = devices.index(self.get_default_sink()) + 1
        if index > len(devices)-1:
            index = 0

        self.set_default_sink(devices[index])

    def get_sink_info(self, name):
        """ d """
        for sink in self.sinks:
            if sink['Name'] == name:
                return sink
        return None

    def get_sink_volume(self, sink):
        """ Get sink volume """
        raw = self.get_sink_info(sink)["Volume"]
        volume = raw.split("%")[0].split()[-1]
        return int(volume)

    def change_sink_volume(self, sink, value):
        """ Set sink volume """
        volume = self.get_sink_volume(sink) + value
        volume = max(min(volume, 150), 0)
        check_output(['pactl', 'set-sink-volume', sink, f'{volume}%'])


def main():
    """ Main function """
    # args = parse_args()
    p = Pulse()
    # if args.switch:
    #     if args.whitelist:
    #         whitelist = args.whitelist.split(',')
    #     else:
    #         whitelist = None
    #     p.inc_default_sink(whitelist)
    # if args.volume:
    #     p.change_sink_volume(p.get_default_sink(), args.volume)
    print(json.dumps(p.get_sinks('sinks'), indent=4))


if __name__ == "__main__":
    main()
