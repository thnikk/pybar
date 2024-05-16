#!/usr/bin/python3 -u
"""
Description: Improved version of the built-in systemd module.
Author: thnikk
"""
from subprocess import run
import modules_waybar.tooltip as tt


def get_output(command) -> list:
    """ Get output of shell command """
    output = run(
        command, check=True, capture_output=True
    ).stdout.decode('utf-8').strip().splitlines()
    return [line.split()[1] for line in output]


def filter_services(services, blacklist):
    """ Filter services through blacklist """
    return [
        service for service in services
        if service.split('.')[0] not in blacklist
    ]


def module(config={}):
    """ Module """
    if 'blacklist' not in list(config):
        config['blacklist'] = []

    failed_system = filter_services(
        get_output(['systemctl', '--failed', '--legend=no']),
        config['blacklist']
    )
    failed_user = filter_services(
        get_output(['systemctl', '--user', '--failed', '--legend=no']),
        config['blacklist']
    )

    num_failed = len(failed_system) + len(failed_user)

    output = {'text': '', 'tooltip': ''}
    if num_failed >= 1:
        output['class'] = 'alert'
        output['text'] = f' {num_failed}'
        output['tooltip'] = (
            f'{tt.heading("Systemd failed units")}\n\n')
        for name, failed_list in {
            'System': failed_system, "User": failed_user
        }.items():
            if failed_list:
                failed_string = "\n".join(failed_list)
                output['tooltip'] += f'{name}:\n{failed_string}\n'
    output['tooltip'] = output['tooltip'].strip()
    output['widget'] = {
        "System": failed_system,
        "User": failed_user
    }

    return output


def main():
    """ Main function """
    module()


if __name__ == "__main__":
    main()
