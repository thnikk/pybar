#!/usr/bin/python3 -u
"""
Description: Main GTK bar class that spawns the bar
Author: thnikk
"""
# For GTK4 Layer Shell to get linked before libwayland-client we must explicitly load it before importing with gi
from ctypes import CDLL
CDLL('libgtk4-layer-shell.so')

import gi
import os
import logging
from subprocess import run, CalledProcessError
import json
import time
import common as c
import module
import ipc
gi.require_version('Gtk', '4.0')
gi.require_version('Gtk4LayerShell', '1.0')
from gi.repository import Gtk, Gdk, Gtk4LayerShell, GLib  # noqa

# Import DBus for sleep/resume handling
from gi.repository import Gio


class Display:
    """ Display class """
    def __init__(self, config, app):
        self.app = app
        self.display = Gdk.Display.get_default()
        self.display.connect('closed', self._on_display_closed)
        monitors = self.display.get_monitors()
        monitors.connect("items-changed", self.on_monitors_changed)
        self.wm = self.get_wm()
        self.config = config
        self.bars = {}
        self.monitors = self.get_monitors()
        self.plugs = self.get_plugs()

        # Track loaded CSS providers to prevent leaks
        self.css_providers = []

        # Load CSS once and store as string for PyInstaller temp path safety
        self.default_css_data = None
        css_path = c.get_resource_path('style.css')
        try:
            with open(css_path, 'r') as f:
                self.default_css_data = f.read()
        except Exception as e:
            c.print_debug(
                f"Failed to load default CSS: {e}",
                name='display', color='red'
            )

        # Apply initial CSS
        self.apply_css()

        # Track sleep/wake state to serialise suspend and wake redraws
        self.is_sleeping = False
        # Set True between PrepareForSleep(false) and the first successful
        # post-wake redraw so that on_monitors_changed does not race with
        # the dedicated wake handler.
        self._is_waking = False
        # GLib source ID of any pending _redraw_bars timer so it can be
        # cancelled when the extended-delay wake path supersedes it.
        self._redraw_timer_id = None
        self._setup_dbus_sleep_handler()

        # Watch for reload signal from settings
        self.reload_file = os.path.expanduser('~/.cache/pybar/.reload')
        self.reload_done_file = os.path.expanduser(
            '~/.cache/pybar/.reload_done'
        )
        GLib.timeout_add_seconds(1, self._check_reload_signal)

        # Start IPC socket server
        self.ipc = ipc.IPCServer(self)
        self.ipc.start()

    def get_wm(self):
        try:
            run(['swaymsg', '-q'], check=True)
            return 'sway'
        except CalledProcessError:
            return 'hyprland'

    def apply_css(self):
        """Apply default and user CSS"""
        self.clear_css()
        
        # Load default CSS
        if self.default_css_data:
            self._add_css_provider(self.default_css_data, from_string=True)
            
        # Apply dynamic overrides from config
        dynamic_css = self._generate_dynamic_css()
        if dynamic_css:
            self._add_css_provider(dynamic_css, from_string=True)

        # Load custom CSS
        if 'style' in self.config:
            self._add_css_provider(self.config['style'], from_string=False)

    def _generate_dynamic_css(self):
        """Generate CSS from config values"""
        css = []
        
        bar_height = self.config.get('bar-height')
        font_size = self.config.get('font-size')
        floating_mode = self.config.get('floating-mode', False)
        corner_radius = self.config.get('corner-radius', 0)
        
        # Generate .bar CSS if any bar properties are set
        if (bar_height is not None or font_size is not None or
                floating_mode or corner_radius > 0):
            css.append(".bar {")
            if bar_height is not None:
                css.append(f"    min-height: {bar_height}px;")
            if font_size is not None:
                css.append(f"    font-size: {font_size}px;")
            
            # Apply full border when floating mode is enabled
            if floating_mode:
                css.append("    border: 1px solid rgba(255, 255, 255, 0.1);")
                if corner_radius > 0:
                    css.append(f"    border-radius: {corner_radius}px;")
                else:
                    css.append("    border-radius: 0px;")
            else:
                # Only top border when floating mode is disabled
                css.append("    border: none;")
                css.append(
                    "    border-top: 1px solid rgba(255, 255, 255, 0.1);"
                )
                css.append("    border-radius: 0px;")
            
            css.append("}")
            
        return "\n".join(css) if css else None

    def _add_css_provider(self, data, from_string=False):
        """Helper to create and attach a CSS provider"""
        try:
            css_provider = Gtk.CssProvider()
            if from_string:
                css_provider.load_from_data(data.encode('utf-8'))
            else:
                css_provider.load_from_path(os.path.expanduser(data))
            
            Gtk.StyleContext.add_provider_for_display(
                self.display, css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_USER
            )
            self.css_providers.append(css_provider)
        except GLib.GError as e:
            c.print_debug(
                f"Failed to load CSS: {e}",
                name='display', color='red'
            )

    def clear_css(self):
        """Remove all attached CSS providers"""
        for provider in self.css_providers:
            Gtk.StyleContext.remove_provider_for_display(
                self.display, provider
            )
        self.css_providers.clear()

    def _setup_dbus_sleep_handler(self):
        """ Setup DBus listener for sleep/resume events """
        try:
            # Connect to systemd-logind's PrepareForSleep signal
            self.dbus_proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM,
                Gio.DBusProxyFlags.NONE,
                None,
                'org.freedesktop.login1',
                '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager',
                None
            )
            if self.dbus_proxy:
                self.dbus_proxy.connect(
                    'g-signal::PrepareForSleep',
                    self._on_prepare_for_sleep
                )
                logging.info("DBus sleep handler registered successfully")
        except Exception as e:
            logging.error(f"Failed to setup DBus sleep handler: {e}")

    def _on_display_closed(self, display, is_error):
        """Restart if the GDK display is closed due to an error."""
        if not is_error:
            return
        import sys
        logging.warning("GDK display closed with error; restarting")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _on_prepare_for_sleep(self, proxy, sender_name, signal_name, parameters):
        """ Handle PrepareForSleep signal from logind """
        if len(parameters) > 0:
            entering = parameters[0]
            if entering:
                logging.info("System entering sleep - pausing bar operations")
                self.is_sleeping = True
                # Optionally: hide bars during sleep
                # for bar in self.bars.values():
                #     if hasattr(bar.window, 'set_visible'):
                #         bar.window.set_visible(False)
            else:
                logging.info("System waking from sleep - reloading bars")
                self.is_sleeping = False
                # Block on_monitors_changed from racing the wake reload
                self._is_waking = True
                # Schedule reload on main loop after wake
                GLib.idle_add(self._on_wake_from_sleep)

    def _on_wake_from_sleep(self):
        """ Reload bars after waking from sleep """
        try:
            # Give the compositor longer to rebuild Wayland/Vulkan surfaces.
            # 500 ms is not enough; 3 s covers slow GPU/compositor wake paths.
            GLib.timeout_add_seconds(3, self._safe_reload_after_sleep)
        except Exception as e:
            logging.error(f"Error during wake handling: {e}")

    def _safe_reload_after_sleep(self):
        """ Safely reload all bars after sleep """
        try:
            # Reinitialize display connection if needed
            self.display = Gdk.Display.get_default()
            if self.display is None:
                logging.error("Failed to get GDK display after sleep")
                return False

            # Force refresh of monitor list
            self.monitors = self.get_monitors()
            self.plugs = self.get_plugs()

            # Redraw all bars safely
            self._redraw_bars()

            logging.info("Successfully reloaded bars after sleep")
            return False
        except Exception as e:
            logging.error(
                f"Error reloading bars after sleep: {e}", exc_info=True
            )
            return False
        finally:
            # Always clear the waking flag so future monitor-change events
            # are handled normally.
            self._is_waking = False

    def get_monitors(self):
        """ Get monitor objects from gdk """
        monitors = self.display.get_monitors()
        return [monitors.get_item(i) for i in range(monitors.get_n_items())]

    def get_plugs(self):
        """
        Get monitor plug names for Wayland outputs.
        Tries multiple methods and retries to get proper connector names.
        """
        plugs = []
        for monitor in self.monitors:
            name = self._get_monitor_name(monitor, len(plugs))
            plugs.append(name)
        return plugs

    def _get_monitor_name(self, monitor, index, max_retries=3):
        """
        Get monitor name with retry logic.
        After suspend, connector info may not be immediately available.
        """
        for attempt in range(max_retries):
            # Try to get the connector name (e.g., eDP-1, HDMI-A-1)
            name = None
            try:
                name = monitor.get_connector()
            except AttributeError:
                pass

            if name:
                logging.debug(
                    f"Got connector name '{name}' for monitor {index}"
                )
                return name

            # Try model as fallback
            if not name:
                try:
                    name = monitor.get_model()
                    if name:
                        logging.debug(
                            f"Using model name '{name}' for monitor {index}"
                        )
                        return name
                except AttributeError:
                    pass

            # If we still don't have a name and haven't exhausted retries
            if attempt < max_retries - 1:
                logging.debug(
                    f"Connector not available for monitor {index}, "
                    f"retrying... (attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(0.2)

        # Last resort: use generic name but log warning
        fallback = f"monitor_{index}"
        logging.warning(
            f"Could not get connector name for monitor {index}, "
            f"using fallback '{fallback}'. "
            f"This may cause issues with outputs filter."
        )
        return fallback

    def on_monitors_changed(self, model, position, removed, added):
        """
        Handle monitor changes by redrawing all bars.
        Skip during a wake-from-sleep cycle; the dedicated wake handler
        manages that redraw on a longer, safer timeline.
        When monitors are added (reconnect), use the same extended-delay
        path as wake-from-sleep to let the compositor rebuild surfaces.
        """
        if self._is_waking:
            logging.debug(
                "on_monitors_changed skipped: "
                "wake-from-sleep/reconnect in progress"
            )
            return
        if added > 0:
            # Monitor reconnected; compositor may be rebuilding Wayland
            # surfaces. Cancel any short-delay redraw already scheduled
            # (e.g. from a preceding removal event in the same DPMS cycle)
            # then use the extended-delay safe-reload path.
            if self._redraw_timer_id is not None:
                GLib.source_remove(self._redraw_timer_id)
                self._redraw_timer_id = None
                logging.debug(
                    "on_monitors_changed: cancelled pending redraw timer"
                )
            logging.debug(
                "on_monitors_changed: %d monitor(s) added, "
                "using extended-delay reload", added
            )
            self._is_waking = True
            GLib.timeout_add_seconds(3, self._safe_reload_after_sleep)
        else:
            # Only removals; a quick redraw is safe.
            self._redraw_timer_id = GLib.timeout_add(
                500, self._redraw_bars
            )

    def draw_bar(self, monitor):
        """ Draw a bar on a monitor """
        # Skip if system is sleeping
        if self.is_sleeping:
            logging.debug("Skipping bar creation during sleep")
            return

        # Validate monitor is still valid
        if monitor and hasattr(monitor, 'is_valid') and not monitor.is_valid():
            logging.warning(f"Monitor is invalid, skipping: {monitor}")
            return

        try_count = 0
        plug = None
        while try_count < 3:
            try:
                # Check if monitor is in our list
                if monitor not in self.monitors:
                    logging.warning(f"Monitor not in active monitors list: {monitor}")
                    return

                index = self.monitors.index(monitor)
                plug = self.plugs[index]
                break
            except (IndexError, ValueError) as e:
                logging.warning(f"Failed to find monitor index (attempt {try_count}): {e}")
                try_count += 1
                if try_count >= 3:
                    logging.error("Max retries reached for monitor lookup")
                    return
                time.sleep(1)

        if plug is None:
            logging.error("Failed to determine monitor plug name")
            return

        # Check against outputs filter
        if 'outputs' in list(self.config):
            if plug not in self.config['outputs']:
                logging.debug(f"Skipping bar for output {plug} (not in config)")
                return

        try:
            bar = Bar(self, monitor)
            bar.populate()
            # CSS is now handled globally by Display
            bar.start()
            self.bars[plug] = bar
            logging.info(f"Successfully created bar on {plug}")
        except Exception as e:
            logging.error(f"Failed to create bar on {plug}: {e}", exc_info=True)

    def _redraw_bars(self):
        """ Redraw all bars (called from idle callback) """
        self._redraw_timer_id = None

        # Skip if the extended-delay wake path has taken over
        if self._is_waking:
            logging.debug("Skipping bar redraw: wake/reconnect in progress")
            return False

        # Skip if system is sleeping
        if self.is_sleeping:
            logging.debug("Skipping bar redraw during sleep")
            return False

        try:
            # Destroy existing bars safely
            for plug, bar in list(self.bars.items()):
                try:
                    if bar:
                        bar.cleanup_modules()
                        if hasattr(bar, 'window') and bar.window:
                            bar.window.destroy()
                except Exception as e:
                    logging.warning(f"Error destroying bar {plug}: {e}")
            self.bars.clear()

            # Reinitialize display connection if needed
            self.display = Gdk.Display.get_default()
            if self.display is None:
                logging.error("Failed to get GDK display during redraw")
                return False

            # Update monitor list with error handling
            self.monitors = self.get_monitors()
            self.plugs = self.get_plugs()

            # Redraw all
            self.draw_all()
            return False
        except Exception as e:
            logging.error(f"Error during bar redraw: {e}", exc_info=True)
            return False

    def draw_all(self):
        """ Initialize all monitors """
        for monitor in self.monitors:
            self.draw_bar(monitor)

    def reload(self):
        """ Reload by replacing the process image """
        import sys
        # Signal completion before exec so the settings window
        # isn't left waiting for a response that will never come.
        try:
            with open(self.reload_done_file, 'w') as f:
                f.write('done')
        except Exception as e:
            c.print_debug(
                f"Failed to signal reload completion: {e}",
                name='display', color='red'
            )
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _check_reload_signal(self):
        """ Check if settings window has signaled a reload """
        if os.path.exists(self.reload_file):
            try:
                os.remove(self.reload_file)
                GLib.idle_add(self.reload)
            except Exception as e:
                c.print_debug(
                    f"Failed to handle reload signal: {e}",
                    name='display', color='red'
                )
        return True  # Continue checking


class Bar:
    """ Bar class"""
    def __init__(self, display, monitor):
        self.window = Gtk.Window()
        self.window.set_application(display.app)
        self.display = display
        self.config = display.config
        self.spacing = self.config['spacing'] if 'spacing' in self.config \
            else 5
        try:
            self.position = display.config['position']
        except KeyError:
            self.position = 'bottom'
        self.bar = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        self.bar.get_style_context().add_class('bar')
        self.left = c.box('h', style='modules-left', spacing=self.spacing)
        self.center = c.box('h', style='modules-center', spacing=self.spacing)
        self.right = c.box('h', style='modules-right', spacing=self.spacing)
        self.bar.set_start_widget(self.left)
        self.bar.set_center_widget(self.center)
        self.bar.set_end_widget(self.right)
        self.window.set_child(self.bar)
        self.monitor = monitor

        # Widget registry for IPC lookups (name -> widget)
        self.module_widgets = {}

        # Add right-click handler for settings
        right_click = Gtk.GestureClick()
        right_click.set_button(3)  # Right click
        right_click.connect('pressed', self._on_right_click)
        self.bar.add_controller(right_click)

    def cleanup_modules(self):
        """ Manually cleanup all modules to prevent leaks """
        count = 0
        widgets_to_cleanup = []

        # First, collect all module widgets
        for section in [self.left, self.center, self.right]:
            child = section.get_first_child()
            while child:
                widgets_to_cleanup.append(child)
                child = child.get_next_sibling()

        # Now cleanup and remove them
        for widget in widgets_to_cleanup:
            # Call cleanup BEFORE removing from parent
            if hasattr(widget, 'cleanup'):
                widget.cleanup()
                count += 1

            # Find which section it's in and remove
            parent = widget.get_parent()
            if parent:
                parent.remove(widget)

            # Disconnect all signals to break reference cycles
            try:
                c.GObject.signal_handlers_destroy(widget)
            except Exception:
                pass

            # Actually destroy the widget to free GTK resources
            if hasattr(widget, 'unparent'):
                widget.unparent()

            # Run disposal if available
            if hasattr(widget, 'run_dispose'):
                widget.run_dispose()

        c.print_debug(f"Cleaned up {count} modules")

    def populate(self):
        """ Populate bar with modules """
        for section_name, section in {
            "modules-left": self.left,
            "modules-center": self.center,
            "modules-right": self.right,
        }.items():
            for name in self.config[section_name]:
                loaded_module = module.module(self, name, self.config)
                if loaded_module:
                    section.append(loaded_module)
                    # Track widget by name for IPC lookups
                    self.module_widgets[name] = loaded_module
                else:
                    logging.warning(
                        f"Module '{name}' could not be loaded and will "
                        "be skipped."
                    )

    def _on_right_click(self, gesture, n_press, x, y):
        """ Handle right-click on bar to show context menu """
        # Check if the click is on a module widget (not blank bar area)
        # Get the widget at the click coordinates
        widget = self.bar.pick(x, y, Gtk.PickFlags.DEFAULT)

        # Only show menu if clicking on the bar itself or section boxes
        # (not on module widgets which have their own right-click handlers)
        if widget is not None:
            # Walk up the widget tree to check if we're on a module
            current = widget
            while current is not None:
                style_context = current.get_style_context()
                # Check if this is a module widget
                if (style_context.has_class('module') or
                        style_context.has_class('workspaces') or
                        style_context.has_class('tray-module')):
                    # Click is on a module, don't show bar context menu
                    return
                # Check if we've reached the bar/section level
                if (current == self.bar or
                        current == self.left or
                        current == self.center or
                        current == self.right):
                    break
                current = current.get_parent()

        # Create popover menu
        popover = Gtk.Popover()
        popover.set_position(Gtk.PositionType.TOP)
        popover.set_autohide(True)
        popover.get_style_context().add_class('bar-context-menu')

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Settings button
        settings_btn = c.icon_button("", "Settings")
        settings_btn.get_style_context().add_class('flat')
        settings_btn.connect('clicked', self._open_settings, popover)
        menu_box.append(settings_btn)

        # Reload button
        reload_btn = c.icon_button(' ', 'Reload')
        reload_btn.get_style_context().add_class('flat')
        reload_btn.connect('clicked', self._reload_bar, popover)
        menu_box.append(reload_btn)

        if c.state_manager.get('debug'):
            # Screenshot button
            screenshot_btn = c.icon_button(' ', 'Screenshot')
            screenshot_btn.get_style_context().add_class('flat')
            screenshot_btn.connect('clicked', self._take_screenshot, popover)
            menu_box.append(screenshot_btn)

            # Inspector button
            inspector_btn = c.icon_button('', 'Inspector')
            inspector_btn.get_style_context().add_class('flat')
            inspector_btn.connect('clicked', self._open_inspector, popover)
            menu_box.append(inspector_btn)

        popover.set_child(menu_box)

        # Position the popover at click location
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.set_parent(self.bar)
        popover.popup()

    def _open_settings(self, btn, popover):
        """ Open settings window """
        popover.popdown()
        from settings import launch_settings_window
        config_path = self.display.app.config_path
        launch_settings_window(config_path)

    def _reload_bar(self, btn, popover):
        """ Reload bar configuration in-process """
        popover.popdown()
        # Reload configuration and rebuild bars without spawning new process
        GLib.idle_add(self.display.reload)

    def _take_screenshot(self, btn, popover):
        """ Take a screenshot of the bar """
        popover.popdown()
        # Small delay to ensure popover is gone
        # take_screenshot returns False, stopping the timeout
        GLib.timeout_add(500, lambda: c.take_screenshot(self.bar))

    def _open_inspector(self, btn, popover):
        """ Open GTK Inspector """
        popover.popdown()
        Gtk.Window.set_interactive_debugging(True)

    def modules(self, modules):
        """ Add modules to bar """
        main = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        main.get_style_context().add_class("bar")

        for index, position in enumerate(["left", "center", "right"]):
            section = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
            section.get_style_context().add_class(position)
            if position == "center":
                section.set_hexpand(True)
            for item in modules[index]:
                section.append(item())
            main.append(section)

        self.window.set_child(main)

    def start(self):
        """ Start bar """
        Gtk4LayerShell.init_for_window(self.window)

        pos = {
            "bottom": Gtk4LayerShell.Edge.BOTTOM,
            "top": Gtk4LayerShell.Edge.TOP
        }

        try:
            position = pos[self.position]
        except KeyError:
            position = pos['bottom']

        # Anchor and stretch to bottom of the screen
        Gtk4LayerShell.set_anchor(self.window, position, 1)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, 1)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.RIGHT, 1)

        # Set margin only when floating mode is enabled
        floating_mode = self.config.get('floating-mode', False)
        margin = self.config.get('margin', 10) if floating_mode else 0

        Gtk4LayerShell.set_margin(
            self.window, Gtk4LayerShell.Edge.LEFT, margin)
        Gtk4LayerShell.set_margin(
            self.window, Gtk4LayerShell.Edge.RIGHT, margin)
        Gtk4LayerShell.set_margin(self.window, position, margin)

        # Set namespace based on config
        if 'namespace' in list(self.config):
            Gtk4LayerShell.set_namespace(self.window, self.config['namespace'])
        else:
            Gtk4LayerShell.set_namespace(self.window, 'pybar')

        Gtk4LayerShell.set_monitor(self.window, self.monitor)

        # Reserve part of screen
        Gtk4LayerShell.auto_exclusive_zone_enable(self.window)

        self.window.present()
