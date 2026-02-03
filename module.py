#!/usr/bin/python3 -u
"""
Description: Load module and popover widgets
Author: thnikk
"""
import importlib
import threading
from subprocess import run, CalledProcessError
import json
import os
import time
from datetime import datetime
import gi
import common as c
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib  # noqa

_instances = {}
_module_map = {}
_worker_threads = {}
_worker_stop_flags = {}


def discover_modules():
    """Automatically discover modules in the modules/ directory"""
    global _module_map
    modules_dir = c.get_resource_path('modules')
    if not os.path.exists(modules_dir):
        return

    for filename in os.listdir(modules_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            try:
                mod = importlib.import_module(f'modules.{module_name}')
                if hasattr(mod, 'module_map'):
                    _module_map.update(mod.module_map)
            except Exception as e:
                c.print_debug(
                    f"Failed to load module {module_name}: {e}", color='red')


def get_instance(name, config):
    """Get or create a module instance"""
    if name in _instances:
        return _instances[name]

    if not _module_map:
        discover_modules()

    module_type = config.get('type', name)
    if module_type in _module_map:
        cls = _module_map[module_type]
        instance = cls(name, config)
        _instances[name] = instance
        return instance
    return None


def start_worker(name, config):
    """Start a background worker for a module"""
    # Stop existing worker if any
    stop_worker(name)

    # Create stop flag
    _worker_stop_flags[name] = threading.Event()

    instance = get_instance(name, config)
    if instance:
        thread = threading.Thread(
            target=instance.run_worker,
            daemon=True
        )
        _worker_threads[name] = thread
        thread.start()
        return

    # Fallback for waybar-style command modules
    if 'command' in config:
        thread = threading.Thread(
            target=command_worker,
            args=(name, config),
            daemon=True
        )
        _worker_threads[name] = thread
        thread.start()


def stop_worker(name):
    """Stop a specific worker thread"""
    if name in _worker_stop_flags:
        _worker_stop_flags[name].set()
    if name in _worker_threads:
        # Don't wait for thread to finish, it's daemon anyway
        del _worker_threads[name]
    # Keep stop flag for a bit so worker can see it
    # It will be cleaned up when a new worker starts


def stop_all_workers():
    """Stop all worker threads"""
    for name in list(_worker_threads.keys()):
        stop_worker(name)


def clear_instances():
    """Clear all module instances for reload"""
    global _instances
    _instances = {}


def command_worker(name, config):
    """Worker for waybar-style command modules"""
    stop_event = _worker_stop_flags.get(name)
    interval = config.get('interval', 60)
    module_type = config.get('type', name)
    is_hass = module_type.startswith('hass') or name.startswith('hass')
    cache_path = os.path.expanduser(f"~/.cache/pybar/{name}.json")

    last_data = None
    first_run = True
    while True:
        data = None

        if first_run and not is_hass and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached = json.load(f)
                if cached:
                    last_data = cached
                    stale_init = cached.copy()
                    stale_init['stale'] = True
                    stale_init['timestamp'] = datetime.now().timestamp()
                    c.state_manager.update(name, stale_init)
            except Exception:
                pass

        command = [os.path.expanduser(arg) for arg in config['command']]
        try:
            output = run(command, check=True,
                         capture_output=True).stdout.decode()
            new_data = json.loads(output)
            if new_data:
                data = new_data
                last_data = data
                if not is_hass:
                    try:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        with open(cache_path, 'w') as f:
                            json.dump(data, f)
                    except Exception:
                        pass
            else:
                if last_data:
                    data = last_data.copy()
                    data['stale'] = True
        except Exception:
            if last_data:
                data = last_data.copy()
                data['stale'] = True

        if data:
            if isinstance(data, dict):
                data['timestamp'] = datetime.now().timestamp()
            c.state_manager.update(name, data)

        first_run = False
        if stop_event:
            if stop_event.wait(timeout=interval):
                break
        else:
            time.sleep(interval)


def module(bar, name, config):
    """Factory to create a module widget"""
    module_config = config['modules'].get(name, {})
    instance = get_instance(name, module_config)

    if instance:
        return instance.create_widget(bar)

    # Generic fallback
    m = c.Module()
    m.set_position(bar.position)

    def generic_update(data):
        if not data:
            return
        if 'text' in data:
            m.set_label(data['text'])
            m.set_visible(bool(data['text']))
        if 'icon' in data:
            m.set_icon(data['icon'])
        if 'tooltip' in data:
            m.set_tooltip_text(str(data['tooltip']))
        m.reset_style()
        if 'class' in data:
            c.add_style(m, data['class'])
        if data.get('stale'):
            c.add_style(m, 'stale')

    sub_id = c.state_manager.subscribe(name, generic_update)
    m._subscriptions.append(sub_id)
    return m
