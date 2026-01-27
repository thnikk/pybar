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

# We will move all modules here eventually
module_map = {
    'clock': 'modules.clock',
    'workspaces': 'modules.workspaces',
    'volume': 'modules.volume',
    'backlight': 'modules.backlight',
    'battery': 'modules.battery',
    'power': 'modules.power',
    'test': 'modules.test',
    'toggle': 'modules.toggle',
    'privacy': 'modules.privacy',
    'hass_2': 'modules.hass_2',
    'memory': 'modules.memory',
    'docker': 'modules.docker',
    'nvtop': 'modules.nvtop',
    'mpc': 'modules.mpc',
    'weather': 'modules.weather',
    'updates': 'modules.updates',
    'git': 'modules.git',
    'ups': 'modules.ups',
    'xdrip': 'modules.xdrip',
    'network': 'modules.network',
    'hass': 'modules.hass',
    'sales': 'modules.sales',
    'power_supply': 'modules.power_supply',
    'obs': 'modules.obs',
    'resin': 'modules.resin',
    'systemd': 'modules.systemd',
    'transmission': 'modules.transmission',
    'vm': 'modules.vm',
    'tray': 'modules.tray',
    'debug': 'modules.debug',
}

def start_worker(name, config):
    """Start a background worker for a module"""
    module_type = config.get('type', name)
    c.print_debug(f"Starting worker for {name} (type: {module_type})", color='cyan')
    
    # Try to load the module
    try:
        if module_type in module_map:
            mod = importlib.import_module(module_map[module_type])
            if hasattr(mod, 'run_worker'):
                thread = threading.Thread(
                    target=mod.run_worker, 
                    args=(name, config),
                    daemon=True
                )
                thread.start()
                return
            elif hasattr(mod, 'fetch_data'):
                thread = threading.Thread(
                    target=generic_worker, 
                    args=(name, config, mod.fetch_data),
                    daemon=True
                )
                thread.start()
                return
    except Exception as e:
        c.print_debug(f"Failed to start worker for {name}: {e}", color='red')

    # Fallback for waybar-style command modules
    if 'command' in config:
        thread = threading.Thread(
            target=command_worker,
            args=(name, config),
            daemon=True
        )
        thread.start()

def generic_worker(name, config, fetch_func):
    """Worker that calls a python fetch_data function"""
    interval = config.get('interval', 60)
    module_type = config.get('type', name)
    is_hass = module_type.startswith('hass') or name.startswith('hass')
    cache_path = os.path.expanduser(f"~/.cache/pybar/{name}.json")

    last_data = None
    first_run = True
    while True:
        data = None
        
        # Check cache on startup
        if first_run and not is_hass and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached = json.load(f)
                if cached:
                    last_data = cached
                    # Broadcast immediately as stale data while we wait for fresh update
                    stale_init = cached.copy()
                    stale_init['stale'] = True
                    stale_init['timestamp'] = datetime.now().timestamp()
                    c.state_manager.update(name, stale_init)
                    c.print_debug(f"Loaded {name} from cache", color='green')
            except Exception as e:
                c.print_debug(f"Failed to load cache for {name}: {e}", color='red')

        try:
            new_data = fetch_func(config)
            if new_data:
                data = new_data
                last_data = data
                if not is_hass:
                    try:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        with open(cache_path, 'w') as f:
                            json.dump(data, f)
                    except Exception as e:
                        c.print_debug(f"Failed to save cache for {name}: {e}", color='red')
            else:
                # If fetch fails, use last successful data
                if last_data:
                    data = last_data.copy()
                    data['stale'] = True
        except Exception as e:
            c.print_debug(f"Worker {name} failed: {e}", color='red')
            if last_data:
                data = last_data.copy()
                data['stale'] = True
        
        if data:
            if isinstance(data, dict):
                data['timestamp'] = datetime.now().timestamp()
            c.state_manager.update(name, data)
        
        first_run = False
        time.sleep(interval)

def command_worker(name, config):
    """Worker for waybar-style command modules"""
    interval = config.get('interval', 60)
    module_type = config.get('type', name)
    is_hass = module_type.startswith('hass') or name.startswith('hass')
    cache_path = os.path.expanduser(f"~/.cache/pybar/{name}.json")

    last_data = None
    first_run = True
    while True:
        data = None
        
        # Check cache on startup
        if first_run and not is_hass and os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached = json.load(f)
                if cached:
                    last_data = cached
                    # Broadcast immediately as stale data while we wait for fresh update
                    stale_init = cached.copy()
                    stale_init['stale'] = True
                    stale_init['timestamp'] = datetime.now().timestamp()
                    c.state_manager.update(name, stale_init)
                    c.print_debug(f"Loaded {name} from cache", color='green')
            except Exception as e:
                c.print_debug(f"Failed to load cache for {name}: {e}", color='red')

        command = [os.path.expanduser(arg) for arg in config['command']]
        try:
            output = run(command, check=True, capture_output=True).stdout.decode()
            new_data = json.loads(output)
            if new_data:
                data = new_data
                last_data = data
                if not is_hass:
                    try:
                        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
                        with open(cache_path, 'w') as f:
                            json.dump(data, f)
                    except Exception as e:
                        c.print_debug(f"Failed to save cache for {name}: {e}", color='red')
            else:
                if last_data:
                    data = last_data.copy()
                    data['stale'] = True
        except Exception as e:
            c.print_debug(f"Command worker {name} failed: {e}", color='red')
            if last_data:
                data = last_data.copy()
                data['stale'] = True
        
        if data:
            if isinstance(data, dict):
                data['timestamp'] = datetime.now().timestamp()
            c.state_manager.update(name, data)
        
        first_run = False
        time.sleep(interval)

def module(bar, name, config):
    """Factory to create a module and subscribe it to updates"""
    module_config = config['modules'].get(name, {})
    module_type = module_config.get('type', name)

    # Some modules might still want to be completely custom (like workspaces)
    # but for most, we want a standard Module that updates its UI.
    
    try:
        if module_type in module_map:
            mod = importlib.import_module(module_map[module_type])
            if hasattr(mod, 'create_widget'):
                # New pattern
                c.print_debug(f"Creating widget for {name}", color='cyan')
                m = mod.create_widget(bar, module_config)
                if hasattr(mod, 'update_ui'):
                    c.print_debug(f"Subscribing {name} to state updates", color='cyan')
                    def update_wrapper(data):
                        mod.update_ui(m, data)
                        if data.get('stale'):
                            c.add_style(m, 'stale')
                        else:
                            c.del_style(m, 'stale')
                    c.state_manager.subscribe(name, update_wrapper)
                return m
            elif hasattr(mod, 'module'):
                # Old pattern (temporary)
                return mod.module(bar, module_config)
    except Exception as e:
        c.print_debug(f"Failed to create module {name}: {e}", color='red')

    # Generic fallback for command modules or unknown types
    m = c.Module()
    m.set_position(bar.position)
    
    def generic_update(data):
        if 'text' in data:
            m.set_label(data['text'])
            m.set_visible(bool(data['text']))
        if 'icon' in data:
            m.set_icon(data['icon'])
        if 'tooltip' in data:
            m.set_tooltip_text(str(data['tooltip']))
        # Handle classes
        m.reset_style()
        if 'class' in data:
            c.add_style(m, data['class'])
        if data.get('stale'):
            c.add_style(m, 'stale')
            
    c.state_manager.subscribe(name, generic_update)
    return m
