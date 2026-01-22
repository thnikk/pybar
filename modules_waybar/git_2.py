#!/usr/bin/python3 -u
"""
Description: Track updates from git repo
Author: thnikk
"""
import os
from subprocess import run, CalledProcessError
import argparse
import json
import re
from datetime import datetime, timezone
import sys


class Git:
    """ Git class """
    def __init__(self, path):
        self.path = path
        self.name = self.get_name()

    def get_name(self) -> str:
        """ Get name of repo """
        output = run([
            'git', '-C', os.path.expanduser(self.path),
            'config', '--get', 'remote.origin.url'],
            check=True, capture_output=True
        ).stdout.decode('utf-8')
        name = output.strip().split('/')[-1].split('.')[0].replace('-', ' ')
        return name.capitalize()

    def fetch(self) -> None:
        """ Fetch """
        try:
            run(
                ['git', '-C', self.path, 'fetch'],
                check=True, capture_output=True
            )
        except CalledProcessError as e:
            print(e.output)

    def commits(self):
        """ Get commits """

        def plural(num) -> str:
            """ Pluralize word """
            if num > 1:
                return 's'
            return ''

        def get_time(input_list) -> str:
            """ Get string of x days/minutes/hours ago """
            for value, word in enumerate(['day', 'hour', 'minute', 'second']):
                if input_list[value]:
                    return (
                        f"{input_list[value]} "
                        f"{word}{plural(input_list[value])} ago")
            return None

        try:
            command_output = run(
                [
                    'git', '-C', os.path.expanduser(self.path), 'log',
                    '--name-only', 'main..origin'
                ],
                check=True, capture_output=True
            ).stdout.decode('utf-8')
        except CalledProcessError:
            try:
                command_output = run(
                    [
                        'git', '-C', os.path.expanduser(self.path), 'log',
                        '--name-only', 'master..origin'
                    ],
                    check=True, capture_output=True
                ).stdout.decode('utf-8')
            except CalledProcessError as e:
                print(e, file=sys.stderr)
                sys.exit(1)
        output = {}
        for line in command_output.splitlines():
            if re.match('^commit', line):
                chash = line.split()[1][:7]
                output[chash] = {
                    "author": None, "date": None, "msg": None, "files": []}
            elif re.match('^Author:', line):
                output[chash]['author'] = \
                    line.split(":")[1].split("<")[0].strip()
            elif re.match('^Date:', line):
                date = ':'.join(line.split(":")[1:]).strip()
                delta = datetime.now(timezone.utc) - datetime.strptime(
                    date, '%a %b %d %H:%M:%S %Y %z')
                dhms = [
                    delta.days, delta.seconds // 60 // 60,
                    delta.seconds // 60, delta.seconds]
                output[chash]['date'] = get_time(dhms)
            elif re.match('^ ', line):
                output[chash]['msg'] = line.strip().replace('&', 'and')
            else:
                if line:
                    output[chash]['files'].append(line)
        return output


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help='Path to git repo')
    parser.add_argument('-i', '--icon', type=str, default='')
    return parser.parse_args()


def module(config):
    """ Module """
    if 'icon' not in list(config):
        config['icon'] = ''

    count = 0
    repos = []

    # Iterate through repos
    for repo in config["repos"]:
        git = Git(os.path.expanduser(repo))
        git.fetch()
        commits = git.commits()
        if commits:
            count += 1
            repos.append({
                "name": git.name, "commits": commits,
                "path": os.path.expanduser(config["path"])
            })

    if count:
        return {
            "text": f"{config['icon']} {count}",
            "widget": repos
        }
    else:
        return {"text": ""}


def main():
    """ Main function """
    args = parse_args()
    print(
        json.dumps(
          module({"path": args.path, "icon": args.icon})
        ))


if __name__ == "__main__":
    main()
