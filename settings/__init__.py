#!/usr/bin/python3 -u
"""
Description: Main settings window - runs as separate process
Author: thnikk
"""
import subprocess
import sys
import os


def launch_settings_window(config_path):
    """Launch settings window as a separate process to avoid CSS conflicts"""
    main_script = os.path.abspath(os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'main.py'
    ))
    subprocess.Popen([
        sys.executable,
        main_script,
        '--settings',
        '--config',
        os.path.expanduser(config_path)
    ])
