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
from gi.repository import Gtk, Pango


class SchemaWidgetBuilder:
    """
    Build GTK widgets from JSON schema definitions.
    """

    @staticmethod
    def build(schema):
        """
        Build a widget from a schema definition.
        Schema format:
        {
            "type": "box",
            "orientation": "v",
            "spacing": 10,
            "children": [...]
        }
        or shorthand:
        {"box": {"orientation": "v", "children": [...]}}
        """
        if not schema or not isinstance(schema, dict):
            return None

        # Handle shorthand format: {"box": {...}}
        widget_type = None
        params = {}

        if 'type' in schema:
            widget_type = schema['type']
            params = {k: v for k, v in schema.items() if k != 'type'}
        else:
            # Try to find widget type from keys
            for key in schema:
                if key in ['box', 'vbox', 'hbox', 'label', 'button',
                           'separator', 'scroll']:
                    widget_type = key
                    params = schema[key]
                    break

        if not widget_type:
            return None

        # Build the widget based on type
        builder_method = getattr(
            SchemaWidgetBuilder,
            f'_build_{widget_type.lower()}',
            None
        )
        if builder_method:
            return builder_method(params)

        return None

    @staticmethod
    def _build_box(params):
        """ Build a box container """
        orientation = params.get('orientation', 'h')
        spacing = params.get('spacing', 0)

        if orientation in ['v', 'vertical']:
            box = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=spacing
            )
        else:
            box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=spacing
            )

        # Set properties
        if 'style' in params:
            c.add_style(box, params['style'])
        if params.get('he'):
            box.set_hexpand(True)
        if params.get('ve'):
            box.set_vexpand(True)
        if 'ha' in params:
            box.set_halign(c.align.get(params['ha'], Gtk.Align.FILL))
        if 'va' in params:
            box.set_valign(c.align.get(params['va'], Gtk.Align.FILL))

        # Add children
        children = params.get('children', [])
        for child_schema in children:
            child = SchemaWidgetBuilder.build(child_schema)
            if child:
                box.append(child)

        return box

    @staticmethod
    def _build_vbox(params):
        """ Build a vertical box """
        params['orientation'] = 'v'
        return SchemaWidgetBuilder._build_box(params)

    @staticmethod
    def _build_hbox(params):
        """ Build a horizontal box """
        params['orientation'] = 'h'
        return SchemaWidgetBuilder._build_box(params)

    @staticmethod
    def _build_label(params):
        """ Build a label widget """
        text = params.get('text', '')
        label = Gtk.Label(label=str(text))

        # Set properties
        if 'style' in params:
            c.add_style(label, params['style'])
        if params.get('he'):
            label.set_hexpand(True)
        if params.get('ve'):
            label.set_vexpand(True)
        if 'ha' in params:
            label.set_halign(c.align.get(params['ha'], Gtk.Align.FILL))
        if 'va' in params:
            label.set_valign(c.align.get(params['va'], Gtk.Align.FILL))
        
        # Text alignment within the label (0.0=left, 0.5=center, 1.0=right)
        if 'xalign' in params:
            xalign_val = params['xalign']
            if isinstance(xalign_val, str):
                xalign_map = {'start': 0.0, 'center': 0.5, 'end': 1.0}
                xalign_val = xalign_map.get(xalign_val, 0.0)
            label.set_xalign(xalign_val)
        if 'yalign' in params:
            yalign_val = params['yalign']
            if isinstance(yalign_val, str):
                yalign_map = {'start': 0.0, 'center': 0.5, 'end': 1.0}
                yalign_val = yalign_map.get(yalign_val, 0.5)
            label.set_yalign(yalign_val)
        
        if 'wrap' in params:
            label.set_wrap(True)
            if isinstance(params['wrap'], int):
                label.set_max_width_chars(params['wrap'])
                label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        if 'length' in params:
            label.set_max_width_chars(params['length'])
            label.set_ellipsize(Pango.EllipsizeMode.END)

        return label

    @staticmethod
    def _build_button(params):
        """ Build a button widget """
        label_text = params.get('label', '')
        button = Gtk.Button(label=label_text)

        # Set properties
        if 'style' in params:
            c.add_style(button, params['style'])
        if params.get('he'):
            button.set_hexpand(True)
        if params.get('ve'):
            button.set_vexpand(True)
        if 'ha' in params:
            button.set_halign(c.align.get(params['ha'], Gtk.Align.FILL))

        return button

    @staticmethod
    def _build_separator(params):
        """ Build a separator widget """
        orientation = params.get('orientation', 'h')

        if orientation in ['v', 'vertical']:
            separator = Gtk.Separator(
                orientation=Gtk.Orientation.VERTICAL
            )
        else:
            separator = Gtk.Separator(
                orientation=Gtk.Orientation.HORIZONTAL
            )

        if 'style' in params:
            c.add_style(separator, params['style'])

        return separator

    @staticmethod
    def _build_scroll(params):
        """ Build a scrolled window """
        width = params.get('width', 0)
        height = params.get('height', 0)
        hexpand = params.get('he', True)
        vexpand = params.get('ve', False)

        window = Gtk.ScrolledWindow(hexpand=hexpand, vexpand=vexpand)
        window.set_overflow(Gtk.Overflow.HIDDEN)
        window.set_min_content_width(width)
        window.set_min_content_height(height)

        if height > 0:
            window.set_max_content_height(height)
        if width > 0:
            window.set_max_content_width(width)

        window.set_propagate_natural_width(True)
        window.set_propagate_natural_height(True)
        window.set_policy(
            Gtk.PolicyType.AUTOMATIC if width else Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC if height else Gtk.PolicyType.NEVER
        )

        if 'style' in params:
            c.add_style(window, params['style'])

        # Add child if present
        children = params.get('children', [])
        if children:
            child = SchemaWidgetBuilder.build(children[0])
            if child:
                window.set_child(child)

        return window


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
            'type': 'choice',
            'default': 'json',
            'label': 'Return Type',
            'description': 'Output format: json or text',
            'choices': ['json', 'text']
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
                result = {
                    'text': data.get('text', ''),
                    'icon': data.get('icon', ''),
                    'class': data.get('class', '')
                }
                # Include widget schema if present
                if 'widget' in data:
                    result['widget'] = data['widget']
                return result
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

        # Store widget schema for popover building
        self._widget_schema = None

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                # Store widget schema if present
                if 'widget' in data:
                    self._widget_schema = data['widget']
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

        # Build widget popover from schema if present
        if 'widget' in data and data['widget']:
            self._build_popover_widget(widget, data['widget'])

        # Update CSS classes
        widget.reset_style()
        css_class = data.get('class', '')
        if css_class:
            c.add_style(widget, css_class)

        # Show stale indicator if data is stale
        if data.get('stale'):
            c.add_style(widget, 'stale')


    def _build_popover_widget(self, module_widget, widget_schema):
        """
        Build a popover widget from schema definition.
        """
        try:
            # Create popover widget
            popover_widget = c.Widget()

            # Build children from schema
            children = widget_schema.get('children', [])
            for child_schema in children:
                child = SchemaWidgetBuilder.build(child_schema)
                if child:
                    popover_widget.box.append(child)

            # Draw and attach to module
            popover_widget.draw()
            module_widget.set_popover(popover_widget)

        except Exception as e:
            c.print_debug(
                f"Custom module {self.name}: failed to build widget: {e}",
                color='red'
            )


# Export module
module_map = {
    'custom': CustomModule
}
