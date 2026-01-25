#!/usr/bin/python3 -u
"""
Description: Backlight module
Author: thnikk
"""
print("!!! BACKLIGHT MODULE LOADED !!!")
import common as c
import os
import sys
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa


def get_brightness_info(device=None):
    base_dir = "/sys/class/backlight"
    base_path = None

    if device:
        path = os.path.join(base_dir, device)
        if os.path.exists(path):
            base_path = path

    if not base_path:
        # Check commonly used backlight devices
        common_devices = ["intel_backlight", "acpi_video0"]
        for dev in common_devices:
            path = os.path.join(base_dir, dev)
            if os.path.exists(path):
                base_path = path
                break

    if not base_path and os.path.exists(base_dir):
        # Fallback to first available device
        try:
            devices = os.listdir(base_dir)
            if devices:
                base_path = os.path.join(base_dir, devices[0])
        except OSError:
            pass

    if not base_path:
        c.print_debug(f"No backlight device found in {base_dir}", color='red')
        return None

    c.print_debug(f"Using backlight device: {base_path}", color='blue')
    info = {}
    try:
        for item in ["brightness", "max_brightness"]:
            with open(f'{base_path}/{item}', 'r', encoding='utf-8') as file:
                info[item] = int(file.read().strip())
        info['path'] = base_path
        return info
    except Exception as e:
        c.print_debug(f"Error reading backlight info: {e}", color='red')
        return None


def fetch_data(config):
    """ Get backlight data """
    return get_brightness_info(config.get('device'))


def run_worker(name, config):
    """ Background worker for backlight """
    print("!!! BACKLIGHT MODULE worker starting !!!")
    c.print_debug(f"Starting backlight worker for {name}", color='cyan')
    interval = config.get('interval', 5)
    
    # Temporary test crash
    # raise Exception("Test crash to verify exception handling")
    
    try:
        while True:
            try:
                data = fetch_data(config)
                if data:
                    c.state_manager.update(name, data)
                else:
                    # Update with None to make module show error state
                    c.state_manager.update(name, None)
            except Exception as e:
                c.print_debug(f"Backlight worker failed: {e}", color='red')
                c.state_manager.update(name, None)
            
            time.sleep(interval)
    except Exception as e:
        import traceback
        # Print to both stderr and file
        error_msg = f"CRITICAL: {name} worker crashed: {e}\n{traceback.format_exc()}"
        c.print_debug(error_msg, color='red')
        print(error_msg, file=sys.stderr)
        # Re-raise to make thread die visibly
        raise


def set_backlight(widget, path):
    """ Action for backlight slider """
    try:
        with open(f'{path}/brightness', 'w', encoding='utf-8') as file:
            file.write(str(round(widget.get_value())))
    except PermissionError:
        c.print_debug("Permission denied to write to brightness file", color='red')


def widget_content(cache):
    """ Backlight widget content """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Backlight', style='heading'))
    
    outer_box = c.box('h', style='box')
    outer_box.set_hexpand(True)
    outer_box.append(c.label('', style='inner-box'))
    
    level = c.slider(cache['brightness'], 10, cache['max_brightness'])
    level.set_hexpand(True)
    level.set_margin_end(10)
    level.connect('value-changed', set_backlight, cache['path'])
    
    outer_box.append(level)
    main_box.append(outer_box)
    return main_box


def create_widget(bar, config):
    """ Backlight module """
    print("!!! BACKLIGHT MODULE create_widget CALLED !!!")
    module = c.Module()
    module.set_position(bar.position)
    c.add_style(module, 'module-fixed')
    module.set_icon('')
    module.set_label('...')  # Set initial loading state
    module.set_visible(True)  # Ensure visible from start

    def scroll_action(controller, dx, dy):
        """ Scroll action """
        info = get_brightness_info(config.get('device'))
        if not info:
            return
        m, b = info['max_brightness'], info['brightness']

        # dy < 0 is scroll up (increase), dy > 0 is scroll down (decrease)
        if dy < 0:
            b = round(b + (m * 0.05))
        elif dy > 0:
            b = round(b - (m * 0.05))

        # Max/min values
        b = round(max(min(b, m), m * 0.01))

        try:
            with open(f"{info['path']}/brightness", 'w', encoding='utf-8') as file:
                file.write(f'{b}')
        except PermissionError:
            pass
        
        # Trigger an immediate local update for better responsiveness
        info['brightness'] = b
        update_ui(module, info)
        
    # Add scroll controller
    scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
    scroll_controller.connect("scroll", scroll_action)
    module.add_controller(scroll_controller)

    return module


def update_ui(module, data):
    """ Update backlight UI """
    if not data:
        c.print_debug("Backlight: No data received", color='yellow')
        module.set_label("No Dev")
        module.set_visible(True)
        return
    
    if not module.get_active():
        module.set_widget(widget_content(data))
        
    percentage = round((data['brightness']/data['max_brightness'])*100)
    module.set_label(f'{percentage}%')
    module.set_visible(True)
