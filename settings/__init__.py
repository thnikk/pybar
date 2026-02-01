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
    subprocess.Popen([
        sys.executable,
        '--settings',
        '--config',
        os.path.expanduser(config_path)
    ])
