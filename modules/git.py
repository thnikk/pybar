#!/usr/bin/python3 -u
"""
Description: Git module refactored for unified state
Author: thnikk
"""
import os
import re
from subprocess import run, CalledProcessError
from datetime import datetime, timezone
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def get_repo_name(path):
    try:
        output = run(['git', '-C', path, 'config', '--get', 'remote.origin.url'], 
                     check=True, capture_output=True).stdout.decode('utf-8')
        name = output.strip().split('/')[-1].split('.')[0].replace('-', ' ')
        return name.capitalize()
    except Exception:
        return os.path.basename(path).capitalize()

def get_commits(path):
    try:
        run(['git', '-C', path, 'fetch'], check=True, capture_output=True)
        
        # Try main then master
        cmd = ['git', '-C', path, 'log', '--name-only']
        try:
            res = run(cmd + ['main..origin'], check=True, capture_output=True).stdout.decode('utf-8')
        except CalledProcessError:
            res = run(cmd + ['master..origin'], check=True, capture_output=True).stdout.decode('utf-8')
            
        output = {}
        chash = None
        for line in res.splitlines():
            if re.match('^commit', line):
                chash = line.split()[1][:7]
                output[chash] = {"author": None, "date": None, "msg": None, "files": []}
            elif re.match('^Author:', line) and chash:
                output[chash]['author'] = line.split(":")[1].split("<")[0].strip()
            elif re.match('^Date:', line) and chash:
                date_str = ':'.join(line.split(":")[1:]).strip()
                dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y %z')
                delta = datetime.now(timezone.utc) - dt
                if delta.days > 0:
                    output[chash]['date'] = f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
                elif delta.seconds // 3600 > 0:
                    output[chash]['date'] = f"{delta.seconds // 3600} hour{'s' if delta.seconds // 3600 > 1 else ''} ago"
                else:
                    output[chash]['date'] = f"{delta.seconds // 60} minute{'s' if delta.seconds // 60 > 1 else ''} ago"
            elif re.match('^ ', line) and chash:
                output[chash]['msg'] = line.strip().replace('&', 'and')
            elif line and chash:
                output[chash]['files'].append(line)
        return output
    except Exception:
        return {}

def fetch_data(config):
    path = os.path.expanduser(config.get('path', '~/'))
    icon = config.get('icon', '')
    
    commits = get_commits(path)
    name = get_repo_name(path)
    
    return {
        "text": f"{icon} {len(commits)}" if commits else "",
        "name": name,
        "commits": commits,
        "path": path,
        "icon": icon
    }

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    module.set_visible(bool(data['text']))
    
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    main_box = c.box('v', spacing=20)
    main_box.get_style_context().add_class('widget-medium')
    main_box.append(c.label(data["name"], style='heading'))

    commits_box = c.box('v', spacing=10)
    scroll_holder = c.box('v', spacing=10)
    
    for chash, info in data['commits'].items():
        commit_box = c.box('v', style='box')
        
        title_box = c.box('h', style='inner-box', spacing=20)
        title = c.label(info['msg'], length=30, ha='start')
        title.props.tooltip_text = info['msg']
        title_box.append(title)
        title_box.append(c.label(info['date'], ha='end', he=True))
        commit_box.append(title_box)

        commit_box.append(c.sep('h'))

        file_box = c.box('v', style='inner-box')
        for f in info['files'][:5]: # Limit files in UI
            file_box.append(c.label(f, ha='start'))
        if len(info['files']) > 5:
            file_box.append(c.label(f"...and {len(info['files'])-5} more", style='gray'))
        commit_box.append(file_box)

        bottom_box = c.box('h', style='inner-box')
        bottom_box.append(c.label(info['author'], ha='start'))
        bottom_box.append(c.label(chash, ha='end', he=True))
        commit_box.append(bottom_box)

        scroll_holder.append(commit_box)

    if len(data['commits']) > 5:
        scroll = c.scroll(height=600)
        scroll.set_child(scroll_holder)
        commits_box.append(scroll)
    else:
        commits_box.append(scroll_holder)
        
    main_box.append(commits_box)

    def on_update_clicked(btn):
        run(["git", "-C", data["path"], "pull", "--rebase"], check=False)
        run(["swaymsg", "reload"], check=False)

    if data['commits']:
        btn = c.button(' Update', style='box')
        btn.connect('clicked', on_update_clicked)
        main_box.append(btn)

    return main_box
