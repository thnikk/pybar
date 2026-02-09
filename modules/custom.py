#!/usr/bin/python3 -u
"""
Description: Waybar-compatible custom module for executing external scripts
Author: thnikk
"""
import common as c
from subprocess import run, CalledProcessError, TimeoutExpired, Popen
import json
import os
import shlex
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk


class CustomModule(c.BaseModule):
    DEFAULT_INTERVAL = 60

    SCHEMA = {
        'exec': {
            'type': 'string',
            'default': '',
            'label': 'Executable Script',
            'description': 'Command to execute (supports arguments and '
                           'quotes)'
        },
        'return-type': {
            'type': 'string',
            'default': 'json',
            'label': 'Return Type',
            'description': 'Output format: json or text'
        },
        'interval': {
            'type': 'integer',
            'default': 60,
            'label': 'Update Interval',
            'description': 'Time between updates in seconds',
            'min': 1
        },
        'on-click-middle': {
            'type': 'string',
            'default': '',
            'label': 'Middle Click Command',
            'description': 'Command to run on middle click'
        },
        'on-click-right': {
            'type': 'string',
            'default': '',
            'label': 'Right Click Command',
            'description': 'Command to run on right click'
        }
    }

    def fetch_data(self):
        """Execute script and parse output"""
        exec_cmd = self.config.get('exec', '')
        return_type = self.config.get('return-type', 'json')

        if not exec_cmd:
            c.print_debug(
                f"Custom module {self.name}: no exec command specified",
                color='yellow'
            )
            return {}

        # Parse command string (handles quotes and escaping)
        try:
            command = shlex.split(os.path.expanduser(exec_cmd))
        except ValueError as e:
            c.print_debug(
                f"Custom module {self.name}: invalid exec syntax: {e}",
                color='red'
            )
            return {}

        if not command:
            return {}

        # Validate executable exists and is executable
        exec_path = command[0]
        if not os.path.exists(exec_path):
            c.print_debug(
                f"Custom module {self.name}: exec path not found: "
                f"{exec_path}",
                color='red'
            )
            return {}

        if not os.access(exec_path, os.X_OK):
            c.print_debug(
                f"Custom module {self.name}: exec path not executable: "
                f"{exec_path}",
                color='red'
            )
            return {}

        # Prepare environment with module-specific variables
        env = os.environ.copy()
        env['PYBAR_MODULE_NAME'] = self.name
        env['PYBAR_MODULE_TYPE'] = 'custom'

        try:
            output = run(
                command,
                check=True,
                capture_output=True,
                timeout=30,
                env=env
            ).stdout.decode('utf-8').strip()

            if return_type == 'json':
                # Parse JSON output
                data = json.loads(output)
                return {
                    'text': data.get('text', ''),
                    'icon': data.get('icon', ''),
                    'class': data.get('class', '')
                }
            else:
                # Plain text output
                return {
                    'text': output,
                    'icon': '',
                    'class': ''
                }
        except CalledProcessError as e:
            c.print_debug(
                f"Custom module {self.name} exec failed with code "
                f"{e.returncode}",
                color='red'
            )
            return {}
        except TimeoutExpired:
            c.print_debug(
                f"Custom module {self.name} exec timed out (30s)",
                color='red'
            )
            return {}
        except json.JSONDecodeError as e:
            c.print_debug(
                f"Custom module {self.name} invalid JSON: {e}",
                color='red'
            )
            return {}
        except Exception as e:
            c.print_debug(
                f"Custom module {self.name} error: {e}",
                color='red'
            )
            return {}

    def create_widget(self, bar):
        """Create bar widget with click handlers"""
        m = c.Module()
        m.set_position(bar.position)

        # Add middle-click handler
        on_click_middle = self.config.get('on-click-middle', '')
        if on_click_middle:
            middle_controller = Gtk.GestureClick.new()
            middle_controller.set_button(2)
            middle_controller.connect(
                'released',
                lambda _c, _n, _x, _y: self._execute_click_command(
                    on_click_middle
                )
            )
            m.add_controller(middle_controller)

        # Add right-click handler
        on_click_right = self.config.get('on-click-right', '')
        if on_click_right:
            right_controller = Gtk.GestureClick.new()
            right_controller.set_button(3)
            right_controller.connect(
                'released',
                lambda _c, _n, _x, _y: self._execute_click_command(
                    on_click_right
                )
            )
            m.add_controller(right_controller)

        # Subscribe to state updates
        import weakref
        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def _execute_click_command(self, command):
        """Execute click command in background"""
        try:
            cmd = shlex.split(os.path.expanduser(command))
            if cmd:
                # Prepare environment
                env = os.environ.copy()
                env['PYBAR_MODULE_NAME'] = self.name
                env['PYBAR_MODULE_TYPE'] = 'custom'

                # Fire and forget
                Popen(cmd, env=env)
                c.print_debug(
                    f"Custom module {self.name}: executed click command",
                    color='green'
                )
        except Exception as e:
            c.print_debug(
                f"Custom module {self.name}: click command failed: {e}",
                color='red'
            )

    def update_ui(self, widget, data):
        """Update widget with new data"""
        if not data:
            widget.set_visible(False)
            return

        # Update text
        text = data.get('text', '')
        widget.set_label(text)
        widget.set_visible(bool(text))

        # Update icon - only show if specified and non-empty
        icon = data.get('icon', '')
        if icon:
            widget.set_icon(icon)
        else:
            widget.set_icon('')

        # Update CSS classes
        widget.reset_style()
        css_class = data.get('class', '')
        if css_class:
            c.add_style(widget, css_class)

        # Show stale indicator if data is stale
        if data.get('stale'):
            c.add_style(widget, 'stale')


# Export module
module_map = {
    'custom': CustomModule
}
