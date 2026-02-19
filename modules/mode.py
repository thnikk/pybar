#!/usr/bin/python3 -u
"""
Description: Mode module for Sway modes and Hyprland submaps
Author: thnikk
"""
from subprocess import Popen, PIPE, STDOUT
import json
import os
import socket
import common as c


class Mode(c.BaseModule):
    DEFAULT_INTERVAL = 0  # Event-based module

    SCHEMA = {
        'format': {
            'type': 'string',
            'default': '{}',
            'label': 'Format',
            'description': 'Format string for the mode name'
        }
    }

    def run_worker(self):
        """ Listen for mode changes based on active WM """
        wm = self._detect_wm()
        c.print_debug(f"Mode module detected WM: {wm}")

        # Initial state: hidden
        c.state_manager.update(self.name, {"text": "", "class": "mode"})

        if wm == 'sway':
            self._run_sway()
        elif wm == 'hyprland':
            self._run_hyprland()

    def _detect_wm(self):
        if os.getenv('HYPRLAND_INSTANCE_SIGNATURE'):
            return 'hyprland'
        try:
            from subprocess import run, DEVNULL
            run(['swaymsg', '-q'], check=True, stdout=DEVNULL, stderr=DEVNULL)
            return 'sway'
        except Exception:
            return 'unknown'

    def _run_sway(self):
        while True:
            try:
                with Popen(
                        ['swaymsg', '-t', 'subscribe', '["mode"]', '-m'],
                        stdout=PIPE, stderr=STDOUT, text=True) as p:
                    if p.stdout:
                        for line in p.stdout:
                            try:
                                data = json.loads(line)
                                mode = data.get('change', 'default')
                                self._update_mode(mode)
                            except (json.JSONDecodeError, KeyError):
                                continue
            except Exception as e:
                c.print_debug(f"Sway mode listener error: {e}", color='red')
                import time
                time.sleep(5)

    def _run_hyprland(self):
        signature = os.getenv('HYPRLAND_INSTANCE_SIGNATURE')
        if not signature:
            return

        # Check common socket locations
        runtime_dir = os.getenv('XDG_RUNTIME_DIR')
        socket_paths = [
            f"/tmp/hypr/{signature}/.socket2.sock",
            f"{runtime_dir}/hypr/{signature}/.socket2.sock"
        ]

        socket_path = None
        for path in socket_paths:
            if os.path.exists(path):
                socket_path = path
                break

        if not socket_path:
            c.print_debug("Hyprland socket2 not found", color='red')
            return

        while True:
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.connect(socket_path)
                    while True:
                        data = s.recv(4096).decode('utf-8')
                        if not data:
                            break
                        for line in data.split('\n'):
                            if line.startswith('submap>>'):
                                mode = line.split('>>')[1]
                                # Hyprland sends empty string by default
                                if not mode:
                                    mode = 'default'
                                self._update_mode(mode)
            except Exception as e:
                c.print_debug(
                    f"Hyprland mode listener error: {e}", color='red')
                import time
                time.sleep(5)

    def _update_mode(self, mode):
        fmt = self.config.get('format', '{}')
        if mode == 'default' or not mode:
            c.state_manager.update(self.name, {"text": "", "class": "mode"})
        else:
            c.state_manager.update(
                self.name, {
                    "text": fmt.format(mode),
                    "class": "mode"
                }
            )


module_map = {
    'mode': Mode
}
