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


def git_widget(cache):
    """ Git widget """
    commits = cache["commits"]

    main_box = c.box('v', style='widget', spacing=20)
    main_box.get_style_context().add_class('wide')
    main_box.add(c.label(cache["name"], style='heading'))

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
