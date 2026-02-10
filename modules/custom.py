#!/usr/bin/python3 -u
"""
Description: Waybar-compatible custom module for executing external scripts
Author: thnikk
"""
from gi.repository import Gtk, Pango
import common as c
from subprocess import run, CalledProcessError, TimeoutExpired, Popen
import json
import os
import shlex
import gi
gi.require_version('Gtk', '4.0')


class SchemaWidgetBuilder:
    """
    Build GTK widgets from JSON schema definitions.
    """

    @staticmethod
    def build(schema, updateable_widgets=None):
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
                           'separator', 'scroll', 'levelbar', 'pillbar',
                           'graph', 'image', 'slider']:
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
            return builder_method(params, updateable_widgets)

        return None

    @staticmethod
    def _build_box(params, updateable_widgets=None):
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
            child = SchemaWidgetBuilder.build(child_schema, updateable_widgets)
            if child:
                box.append(child)

        return box

    @staticmethod
    def _build_vbox(params, updateable_widgets=None):
        """ Build a vertical box """
        params['orientation'] = 'v'
        return SchemaWidgetBuilder._build_box(params, updateable_widgets)

    @staticmethod
    def _build_hbox(params, updateable_widgets=None):
        """ Build a horizontal box """
        params['orientation'] = 'h'
        return SchemaWidgetBuilder._build_box(params, updateable_widgets)

    @staticmethod
    def _build_label(params, updateable_widgets=None):
        """ Build a label widget """
        text = params.get('text', '')
        label = Gtk.Label(label=str(text))

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': label,
                'type': 'label'
            }

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
    def _build_button(params, updateable_widgets=None):
        """ Build a button widget """
        label_text = params.get('label', '')
        button = Gtk.Button(label=label_text)

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': button,
                'type': 'button'
            }

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
    def _build_separator(params, updateable_widgets=None):
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
    def _build_scroll(params, updateable_widgets=None):
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
            child = SchemaWidgetBuilder.build(children[0], updateable_widgets)
            if child:
                window.set_child(child)

        return window

    @staticmethod
    def _build_levelbar(params, updateable_widgets=None):
        """ Build a level bar widget """
        min_val = params.get('min', 0)
        max_val = params.get('max', 100)
        value = params.get('value', 0)

        levelbar = Gtk.LevelBar.new_for_interval(min_val, max_val)
        levelbar.set_value(value)

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': levelbar,
                'type': 'levelbar'
            }

        if 'style' in params:
            c.add_style(levelbar, params['style'])

        return levelbar

    @staticmethod
    def _build_pillbar(params, updateable_widgets=None):
        """ Build a pill bar widget """
        height = params.get('height', 12)
        radius = params.get('radius', 6)

        pillbar = c.PillBar(height=height, radius=radius)

        # Set initial segments if provided
        segments = params.get('segments', [])
        if segments:
            pillbar.update(segments)

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': pillbar,
                'type': 'pillbar'
            }

        if 'style' in params:
            c.add_style(pillbar, params['style'])

        return pillbar

    @staticmethod
    def _build_graph(params, updateable_widgets=None):
        """ Build a graph widget """
        data = params.get('data', [])
        height = params.get('height', 120)
        width = params.get('width', 300)
        min_val = params.get('min')
        max_val = params.get('max')

        graph = c.Graph(
            data=data,
            height=height,
            width=width,
            min_config=min_val,
            max_config=max_val
        )

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': graph,
                'type': 'graph'
            }

        if 'style' in params:
            c.add_style(graph, params['style'])

        return graph

    @staticmethod
    def _build_slider(params, updateable_widgets=None):
        """ Build a slider widget """
        value = params.get('value', 0)
        min_val = params.get('min', 0)
        max_val = params.get('max', 100)

        slider = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            min_val,
            max_val,
            1
        )
        slider.set_value(value)
        slider.set_draw_value(False)

        # Store reference if widget has an ID
        widget_id = params.get('id')
        if widget_id and updateable_widgets is not None:
            updateable_widgets[widget_id] = {
                'widget': slider,
                'type': 'slider'
            }

        if 'style' in params:
            c.add_style(slider, params['style'])

        return slider

    @staticmethod
    def _build_image(params, updateable_widgets=None):
        """ Build an image widget """
        file_path = params.get('path')
        width = params.get('width')
        height = params.get('height')

        if file_path:
            image = Gtk.Picture.new_for_filename(file_path)
        else:
            image = Gtk.Picture.new()

        if width:
            image.set_content_width(width)
        if height:
            image.set_content_height(height)

        if 'style' in params:
            c.add_style(image, params['style'])

        return image


class CustomModule(c.BaseModule):
    DEFAULT_INTERVAL = 60

    SCHEMA = {
        'exec': {
            'type': 'file',
            'default': '',
            'label': 'Executable Script',
            'description': 'Path to script or command to execute '
                           '(supports arguments and quotes)'
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

        # Store widget schema and updateable widgets
        self._widget_schema = None
        self._widget_schema_hash = None
        self._updateable_widgets = {}

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

        # Build widget popover from schema if present
        if 'widget' in data and data['widget']:
            self._build_popover_widget(widget, data['widget'])

        # Update widget values if present
        if 'widget_updates' in data and self._updateable_widgets:
            self._update_widget_values(data['widget_updates'])

        # Update CSS classes
        widget.reset_style()
        css_class = data.get('class', '')
        if css_class:
            c.add_style(widget, css_class)

        # Show stale indicator if data is stale
        if data.get('stale'):
            c.add_style(widget, 'stale')

    def _update_widget_values(self, updates):
        """
        Update widget values without rebuilding.
        """
        for widget_id, new_value in updates.items():
            if widget_id in self._updateable_widgets:
                widget_info = self._updateable_widgets[widget_id]
                widget_obj = widget_info['widget']
                widget_type = widget_info['type']

                try:
                    if widget_type == 'label':
                        widget_obj.set_text(str(new_value))
                    elif widget_type == 'button':
                        widget_obj.set_label(str(new_value))
                    elif widget_type == 'levelbar':
                        widget_obj.set_value(float(new_value))
                    elif widget_type == 'slider':
                        widget_obj.set_value(float(new_value))
                    elif widget_type == 'pillbar':
                        widget_obj.update(new_value)
                    elif widget_type == 'graph':
                        widget_obj.update_data(new_value, None)
                except Exception as e:
                    c.print_debug(
                        f"Custom module {self.name}: failed to update "
                        f"widget {widget_id}: {e}",
                        color='red'
                    )

    def _build_popover_widget(self, module_widget, widget_schema):
        """
        Build a popover widget from schema definition.
        Only rebuilds if schema changes.
        """
        try:
            # Calculate schema hash to detect changes
            import hashlib
            schema_str = json.dumps(
                widget_schema.get('children', []),
                sort_keys=True
            )
            schema_hash = hashlib.md5(schema_str.encode()).hexdigest()

            # Only rebuild if schema changed
            if schema_hash != self._widget_schema_hash:
                c.print_debug(
                    f"Custom module {self.name}: building widget",
                    color='green'
                )

                # Get existing popover or create new one
                popover_widget = module_widget.get_popover()
                is_new = False
                if not popover_widget:
                    popover_widget = c.Widget()
                    is_new = True
                else:
                    # Clear existing children
                    child = popover_widget.box.get_first_child()
                    while child:
                        next_child = child.get_next_sibling()
                        popover_widget.box.remove(child)
                        child = next_child

                # Clear previous updateable widgets
                self._updateable_widgets = {}

                # Build children from schema
                children = widget_schema.get('children', [])
                for child_schema in children:
                    child = SchemaWidgetBuilder.build(
                        child_schema,
                        self._updateable_widgets
                    )
                    if child:
                        popover_widget.box.append(child)

                # Draw and attach if new
                if is_new:
                    popover_widget.draw()
                    module_widget.set_popover(popover_widget)

                # Store hash
                self._widget_schema_hash = schema_hash

                c.print_debug(
                    f"Custom module {self.name}: widget built with "
                    f"{len(self._updateable_widgets)} updateable widgets",
                    color='green'
                )

        except Exception as e:
            c.print_debug(
                f"Custom module {self.name}: failed to build widget: {e}",
                color='red'
            )


# Export module
module_map = {
    'custom': CustomModule
}
