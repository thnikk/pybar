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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([
        sys.executable,
        os.path.join(script_dir, 'window.py'),
        os.path.expanduser(config_path)
    ])
