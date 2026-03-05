#!/usr/bin/python3 -u
"""
Description: Unix socket IPC server for pybar widget control
Author: thnikk
"""
import os
import socket
import threading
import json
import logging
import module as mod
from gi.repository import GLib

# Default socket path
SOCKET_PATH = os.path.expanduser('~/.cache/pybar/pybar.sock')


class IPCServer:
    """
    Listens on a Unix domain socket for JSON commands and dispatches
    widget actions on the GTK main loop via GLib.idle_add.

    Supported commands (sent as a single JSON line):
        {"action": "toggle", "widget": "clock"}
        {"action": "toggle", "widget": "clock", "monitor": "eDP-1"}
        {"action": "show",   "widget": "clock", "monitor": "eDP-1"}
        {"action": "hide",   "widget": "clock"}
        {"action": "reload", "module": "clock"}

    Responses are a single JSON line:
        {"status": "ok", "affected": ["eDP-1"]}
        {"status": "ok", "module": "clock"}
        {"status": "error", "message": "..."}
    """

    def __init__(self, display):
        self.display = display
        self._thread = None
        self._sock = None
        self._running = False

    def start(self):
        """Create the socket and start the accept thread."""
        cache_dir = os.path.dirname(SOCKET_PATH)
        os.makedirs(cache_dir, exist_ok=True)

        # Remove a stale socket left by a previous run
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError as e:
                logging.warning(f"Could not remove old IPC socket: {e}")

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.bind(SOCKET_PATH)
        self._sock.listen(5)
        self._running = True

        self._thread = threading.Thread(
            target=self._accept_loop, daemon=True
        )
        self._thread.start()
        logging.info("IPC server listening on %s", SOCKET_PATH)

    def stop(self):
        """Stop the server and clean up the socket file."""
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if os.path.exists(SOCKET_PATH):
            try:
                os.unlink(SOCKET_PATH)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _accept_loop(self):
        """Accept connections until stopped."""
        while self._running:
            try:
                conn, _ = self._sock.accept()
                threading.Thread(
                    target=self._handle_conn,
                    args=(conn,),
                    daemon=True
                ).start()
            except OSError:
                # Socket closed by stop()
                break

    def _handle_conn(self, conn):
        """Read one newline-terminated JSON message from a connection."""
        try:
            buf = b''
            while b'\n' not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                buf += chunk

            if not buf.strip():
                conn.close()
                return

            try:
                cmd = json.loads(buf.decode().strip())
            except json.JSONDecodeError as e:
                self._send(conn, {
                    'status': 'error',
                    'message': f'Invalid JSON: {e}'
                })
                conn.close()
                return

            # Hand off to GTK main loop; conn is closed inside _dispatch
            GLib.idle_add(self._dispatch, cmd, conn)

        except Exception as e:
            logging.error("IPC connection error: %s", e)
            try:
                conn.close()
            except OSError:
                pass

    def _dispatch(self, cmd, conn):
        """Execute a command on the GTK main loop thread."""
        try:
            result = self._handle_command(cmd)
        except Exception as e:
            result = {'status': 'error', 'message': str(e)}
        finally:
            self._send(conn, result)
            conn.close()
        return False  # Remove from idle queue

    def _send(self, conn, data):
        """Write a JSON response terminated by a newline."""
        try:
            conn.sendall(json.dumps(data).encode() + b'\n')
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    def _handle_command(self, cmd):
        """Route a parsed command dict to the appropriate handler."""
        action = cmd.get('action')
        if not action:
            return {'status': 'error', 'message': 'Missing action'}

        if action in ('toggle', 'show', 'hide'):
            widget_name = cmd.get('widget')
            if not widget_name:
                return {'status': 'error', 'message': 'Missing widget'}
            monitor = cmd.get('monitor')
            return self._widget_action(action, widget_name, monitor)

        if action == 'reload':
            module_name = cmd.get('module')
            if not module_name:
                return {'status': 'error', 'message': 'Missing module'}
            return self._reload_module(module_name)

        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def _widget_action(self, action, widget_name, monitor=None):
        """Show, hide, or toggle a named module widget."""
        bars = self.display.bars

        # Filter to a single monitor if specified
        if monitor is not None:
            if monitor not in bars:
                return {
                    'status': 'error',
                    'message': f'Monitor not found: {monitor}',
                }
            targets = {monitor: bars[monitor]}
        else:
            targets = dict(bars)

        affected = []
        for plug, bar in targets.items():
            widget = bar.module_widgets.get(widget_name)
            if widget is None:
                continue

            popover = widget.get_popover()
            if popover is None:
                continue

            if action == 'toggle':
                widget.set_active(not popover.get_visible())
            elif action == 'show':
                widget.set_active(True)
            elif action == 'hide':
                widget.set_active(False)

            affected.append(plug)

        if not affected:
            scope = f" on {monitor}" if monitor else ""
            return {
                'status': 'error',
                'message': (
                    f"Widget '{widget_name}' not found{scope}"
                ),
            }

        return {'status': 'ok', 'affected': affected}

    def _reload_module(self, module_name):
        """Force a module worker to update immediately."""
        if mod.force_update(module_name):
            return {'status': 'ok', 'module': module_name}
        return {
            'status': 'error',
            'message': f"Module '{module_name}' not found or not running",
        }
