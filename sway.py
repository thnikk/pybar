#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from subprocess import check_output, Popen, PIPE, STDOUT
import json
import os


def cache():
    """ Cache sway workspaces to file on change """
    with Popen(['swaymsg', '-t', 'subscribe', '["workspace"]', '-m'],
               stdin=PIPE, stdout=PIPE, stderr=STDOUT) as p:
        for _ in p.stdout:
            raw = json.loads(check_output(
                ['swaymsg', '-t', 'get_workspaces']))
            workspaces = [workspace['name'] for workspace in raw]
            workspaces.sort()
            focused = [
                workspace['name'] for workspace in raw
                if workspace['focused']
            ][0]
            with open(
                os.path.expanduser('~/.cache/pybar/sway.json'),
                'w', encoding='utf-8'
            ) as file:
                file.write(json.dumps({
                    'workspaces': workspaces,
                    'focused': focused
                }))
