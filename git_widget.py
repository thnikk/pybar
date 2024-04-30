#!/usr/bin/python3 -u
"""
Description: Git widget
Author: thnikk
"""
import re
import os
import sys
from datetime import datetime, timezone
from subprocess import run, check_output, CalledProcessError
import common as c


class Git:
    """ Git class """
    def __init__(self, path):
        self.path = path
        self.name = self.get_name()

    def fetch(self) -> None:
        """ Fetch """
        try:
            run(
                ['git', '-C', self.path, 'fetch'],
                check=True, capture_output=True
            )
        except CalledProcessError as e:
            print(e.output)

    def get_name(self) -> str:
        """ Get name of repo """
        name = check_output(
            ['git', '-C', os.path.expanduser(self.path),
             'config', '--get', 'remote.origin.url']
        ).decode().strip().split('/')[-1].split('.')[0].replace('-', ' ')
        return name.capitalize()

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
        except CalledProcessError as e:
            lines = e.stderr.decode('utf-8').splitlines()
            for line in lines:
                print(line)
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


def git_widget(repo):
    """ Git widget """
    git = Git(os.path.expanduser(repo))
    commits = git.commits()

    main_box = c.box('v', style='widget', spacing=20)
    main_box.get_style_context().add_class('wide')
    main_box.add(c.label(git.name, style='heading'))

    commits_box = c.box('v', spacing=10)
    commits_box.add(c.label('Commits', style='title', ha='start'))
    scroll_holder = c.box('v', spacing=10)
    scroll_box = c.scroll(0, 700, style='scroll-mask')
    for commit, info in commits.items():
        commit_box = c.box('v', style='box')

        title_box = c.box('h', style='inner-box', spacing=20)
        title = c.label(info['msg'], length=100, ha='start')
        title.props.tooltip_text = info['msg']
        title_box.add(title)
        title_box.pack_end(c.label(info['date'], style='green-fg'), 0, 0, 0)
        commit_box.add(title_box)

        commit_box.add(c.sep('h'))

        file_box = c.box('v', style='inner-box')
        for file in info['files']:
            file_box.add(c.label(file, ha='start'))
        commit_box.add(file_box)

        bottom_box = c.box('h', style='inner-box')
        bottom_box.pack_end(c.label(info['author']), 0, 0, 0)
        bottom_box.pack_start(c.label(commit, style='blue-fg'), 0, 0, 0)
        commit_box.add(bottom_box)

        scroll_holder.add(commit_box)
    if len(commits) > 5:
        scroll_box.add(scroll_holder)
        commits_box.add(scroll_box)
    else:
        commits_box.add(scroll_holder)
    main_box.add(commits_box)

    return main_box
