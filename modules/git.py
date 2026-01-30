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


class Git(c.BaseModule):
    def get_repo_name(self, path):
        try:
            output = run(
                ['git', '-C', path, 'config', '--get', 'remote.origin.url'],
                check=True, capture_output=True).stdout.decode('utf-8')
            name = output.strip().split('/')[-1].split(
                '.')[0].replace('-', ' ')
            return name.capitalize()
        except Exception:
            return os.path.basename(path).capitalize()

    def get_commits(self, path):
        try:
            run(['git', '-C', path, 'fetch'], check=True, capture_output=True)

            # Try main then master
            cmd = ['git', '-C', path, 'log', '--name-only']
            try:
                res = run(cmd + ['main..origin'], check=True,
                          capture_output=True).stdout.decode('utf-8')
            except CalledProcessError:
                res = run(cmd + ['master..origin'], check=True,
                          capture_output=True).stdout.decode('utf-8')

            output = {}
            chash = None
            for line in res.splitlines():
                if re.match('^commit', line):
                    chash = line.split()[1][:7]
                    output[chash] = {
                        "author": None, "date": None, "msg": None, "files": []}
                elif re.match('^Author:', line) and chash:
                    output[chash]['author'] = line.split(
                        ":")[1].split("<")[0].strip()
                elif re.match('^Date:', line) and chash:
                    date_str = ':'.join(line.split(":")[1:]).strip()
                    dt = datetime.strptime(date_str, '%a %b %d %H:%M:%S %Y %z')
                    delta = datetime.now(timezone.utc) - dt
                    if delta.days > 0:
                        output[chash]['date'] = \
                            f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
                    elif delta.seconds // 3600 > 0:
                        output[chash]['date'] = (
                            f"{delta.seconds // 3600} hour"
                            f"{'s' if delta.seconds // 3600 > 1 else ''} ago")
                    else:
                        output[chash]['date'] = (
                            f"{delta.seconds // 60} minute"
                            f"{'s' if delta.seconds // 60 > 1 else ''} ago")
                elif re.match('^ ', line) and chash:
                    output[chash]['msg'] = line.strip().replace('&', 'and')
                elif line and chash:
                    output[chash]['files'].append(line)
            return output
        except Exception:
            return {}

    def fetch_data(self):
        path = os.path.expanduser(self.config.get('path', '~/'))
        icon = self.config.get('icon', '')

        commits = self.get_commits(path)
        name = self.get_repo_name(path)

        return {
            "text": f"{icon} {len(commits)}" if commits else "",
            "name": name,
            "commits": commits,
            "path": path,
            "icon": icon
        }

    def toggle_details(self, _btn, details_box, indicator):
        visible = not details_box.get_visible()
        indicator.set_text('' if visible else '')
        details_box.set_visible(visible)

    def on_update_clicked(self, _btn, data):
        run(["git", "-C", data["path"], "pull", "--rebase"], check=False)
        run(["swaymsg", "reload"], check=False)

    def build_popover(self, data):
        main_box = c.box('v', spacing=20)
        main_box.get_style_context().add_class('widget-medium')
        main_box.append(c.label(data["name"], style='heading'))

        commits_box = c.box('v', spacing=10)
        scroll_holder = c.box('v', spacing=10)

        for chash, info in data['commits'].items():
            item_con = c.box('v')

            btn = c.button()
            c.add_style(btn, ['minimal', 'inner-box'])

            btn_content = c.box('h', spacing=10)
            indicator = c.label('', style='gray')

            # Message and date in the header
            msg_label = c.label(info['msg'], length=30, ha='start', he=True)
            msg_label.props.tooltip_text = info['msg']

            btn_content.append(indicator)
            btn_content.append(msg_label)
            btn_content.append(c.label(info['date'], ha='end'))

            btn.set_child(btn_content)

            # Container for details
            details_box = c.box('v')
            details_box.set_visible(False)
            c.add_style(details_box, 'expanded-status')

            details_box.append(c.sep('h'))

            inner_details = c.box('v', style='inner-box', spacing=10)

            # Files list
            file_box = c.box('v')
            for f in info['files'][:10]:  # Show more files in expanded view
                file_box.append(c.label(f, ha='start', style='small'))
            if len(info['files']) > 10:
                file_box.append(
                    c.label(
                        f"...and {len(info['files']) - 10} more", style='gray'))

            inner_details.append(file_box)
            inner_details.append(c.sep('h'))

            # Author and Hash
            bottom_box = c.box('h')
            bottom_box.append(c.label(info['author'], ha='start', style='gray'))
            bottom_box.append(c.label(chash, ha='end', he=True, style='gray'))
            inner_details.append(bottom_box)

            details_box.append(inner_details)

            btn.connect(
                'clicked', self.toggle_details, details_box, indicator)

            item_con.append(btn)
            item_con.append(details_box)

            # Wrap the whole item in a box to match the look
            outer_box = c.box('v', style='box')
            outer_box.append(item_con)
            scroll_holder.append(outer_box)

        if len(data['commits']) > 5:
            scroll = c.scroll(height=600, style='scroll')
            scroll.set_child(scroll_holder)
            commits_box.append(scroll)
        else:
            commits_box.append(scroll_holder)

        main_box.append(commits_box)

        if data['commits']:
            btn = c.button(' Update', style='box')
            btn.connect('clicked', self.on_update_clicked, data)
            main_box.append(btn)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        m.set_visible(False)

        c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        return m

    def update_ui(self, widget, data):
        if not data:
            return
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))
        if data.get('stale'):
            c.add_style(widget, 'stale')

        if not widget.get_active():
            widget.set_widget(self.build_popover(data))


module_map = {
    'git': Git
}
