#!/usr/bin/python3 -u
"""
Description: Main settings window - runs as separate process
Author: thnikk
"""
import subprocess
import sys
import os


def launch_settings_window(config_path):
    """Launch settings window as separate process to avoid CSS conflicts"""
    import sys
    import os
    import subprocess

    # Use sys.argv[0] for PyInstaller, sys.executable for dev
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle
        cmd = [sys.argv[0]]
    else:
        # Running as script
        main_script = os.path.abspath(os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'main.py'
        ))
        cmd = [sys.executable, main_script]

    cmd.extend(['--settings', '--config', os.path.expanduser(config_path)])
    subprocess.Popen(cmd)
