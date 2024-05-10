#!/usr/bin/python3 -u
"""
Description: Privacy module that doesn't crash waybar.
Author: thnikk
"""
from subprocess import run, CalledProcessError
import json
from glob import glob
import sys
from common import print_debug


def process_name(pid):
    """ Get process name for PID """
    with open(f'/proc/{pid}/cmdline', 'r', encoding='utf-8') as file:
        return file.read().split('\x00')[0].split()[0].split('/')[-1]


def get_webcams():
    """ Get processes using video devices """
    webcams = {}
    for device in glob("/dev/video*"):
        try:
            output = run(
                ['fuser', device], check=True, capture_output=True
            ).stdout.decode('utf-8').strip().split()
            names = []
            for pid in output:
                name = process_name(pid)
                if 'wireplumber' not in name:
                    names.append(name)
            if names:
                webcams[device] = names
        except CalledProcessError:
            pass
    return webcams


def json_output(command):
    """ Get json for command output """
    try:
        command_output = run(
            command, capture_output=True, check=True
        ).stdout.decode('utf-8')
    except CalledProcessError:
        print_debug('Not using pipewire, quitting.')
        sys.exit(1)

    if "]\n[" in command_output:
        combined = "[\n" + "],\n[".join(command_output.split(']\n[')) + "\n]"
        output = []
        for item in json.loads(combined):
            output += item
    else:
        output = command_output

    return output


def get_prop(full_props, prop_list):
    """ Return first prop in prop list found in full_props """
    for prop in prop_list:
        try:
            return full_props[prop]
        except KeyError:
            pass
    return None


def get_categories(pw):
    """ Get dictionary of running category by programs """
    running = {}
    for item in pw:
        try:
            if (
                item['info']['state'] == 'running' and
                'Stream/Input' in item['info']['props']['media.class']
            ):
                mtype = item['info']['props']['media.class'].split('/')[-1]
                program = get_prop(
                    item['info']['props'],
                    ['application.process.binary', 'node.name']).lower()
                try:
                    running[mtype]
                except KeyError:
                    running[mtype] = []
                if program not in running[mtype]:
                    running[mtype].append(program)
        except (KeyError, TypeError):
            pass
    webcams = get_webcams()
    running.update(webcams)
    return running


def get_icons(categories):
    """ Get string of icons for active categories """
    icon_lookup = {'Audio': '', 'Video': '', 'Webcam': ''}
    icons = []
    for category in categories:
        if '/dev/video' in category:
            category = 'Webcam'
        if icon_lookup[category] not in icons:
            icons.append(icon_lookup[category])
    return ' '.join(icons)


def module(_):
    """ Module """
    pw = json_output(['pw-dump'])
    categories = get_categories(pw)

    output = {'class': 'green'}

    output['text'] = get_icons(categories)

    tooltip = []
    for category, progs in categories.items():
        tooltip.append(
            f'\n<span color="#8fa1be" font_size="16pt">{category}</span>')
        for prog in progs:
            tooltip.append(prog)
    output['widget'] = categories
    output['tooltip'] = '\n'.join(tooltip).lstrip()
    return output


def main():
    """ Main function """
    print(json.dumps(module(), indent=4))


if __name__ == "__main__":
    main()
