#!/usr/bin/python3 -u
"""
Description: Network module refactored for unified state
Author: thnikk
"""
from subprocess import run
import common as c
import gi
import socket
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def get_devices():
    """ Get active NetworkManager connections using a single nmcli call """
    try:
        res = run(['nmcli', '-t', '-f', 'DEVICE,TYPE,STATE,CONNECTION', 'd'], check=True, capture_output=True).stdout.decode('utf-8')
        devices = []
        for line in res.splitlines():
            parts = line.split(':')
            if len(parts) >= 4:
                dev_type = parts[1]
                if dev_type in ['loopback', 'bridge']:
                    continue
                dev = {
                    'GENERAL.DEVICE': parts[0],
                    'GENERAL.TYPE': dev_type,
                    'GENERAL.STATE': parts[2],
                    'GENERAL.CONNECTION': parts[3]
                }
                devices.append(dev)
        
        # Also get IPs for connected devices
        res_ip = run(['nmcli', '-t', '-f', 'GENERAL.DEVICE,IP4.ADDRESS', 'd', 'show'], check=True, capture_output=True).stdout.decode('utf-8')
        curr_dev = None
        for line in res_ip.splitlines():
            if 'GENERAL.DEVICE:' in line:
                curr_dev = line.split(':', 1)[1]
            elif 'IP4.ADDRESS[1]' in line and curr_dev:
                ip = line.split(':', 1)[1]
                for d in devices:
                    if d['GENERAL.DEVICE'] == curr_dev:
                        d['IP4.ADDRESS[1]'] = ip
                        break
        return devices
    except Exception as e:
        c.print_debug(f"Error fetching network devices: {e}", color='red')
        return []


def check_internet():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        return True
    except OSError:
        pass
    return False

def fetch_data(config):
    """ Fetch network data """
    has_internet = check_internet()
    devices = get_devices()
    icons = {"ethernet": "", "wifi": "", "wifi-p2p": ""}
    connection_type = None
    connection_ip = None
    
    for device in devices:
        state = device.get('GENERAL.STATE', '').lower()
        if 'connected' in state:
            connection_type = device.get('GENERAL.TYPE')
            connection_ip = device.get('IP4.ADDRESS[1]', '').split('/')[0] if 'IP4.ADDRESS[1]' in device else None
            if connection_type in icons:
                break

    always_show = config.get('always_show', True)
    
    if connection_type:
        text = icons.get(connection_type, "")
        tooltip = f"{connection_type}\n{connection_ip}"
    elif has_internet:
        text = ""
        tooltip = "Connected (Unknown device)"
    else:
        text = "" if always_show else ""
        tooltip = "No connection"

    return {
        "text": text,
        "tooltip": tooltip,
        "devices": devices,
        "connection_type": connection_type
    }

def create_widget(bar, config):
    """ Create network widget """
    module = c.Module()
    module.set_position(bar.position)
    module.text.set_label('...')
    module.popover_widgets = {}
    return module

def update_ui(module, data):
    """ Update network UI """
    module.text.set_label(data['text'] if data['text'] else "NET")
    module.set_tooltip_text(data['tooltip'])
    
    if not module.get_active():
        module.set_widget(build_popover(module, data))
    else:
        # Live update IP labels if they exist
        devices = {d['GENERAL.DEVICE']: d for d in data.get('devices', [])}
        for dev_name, widgets in module.popover_widgets.items():
            if dev_name in devices:
                dev = devices[dev_name]
                if 'ip_label' in widgets:
                    ip = dev.get('IP4.ADDRESS[1]', 'None')
                    widgets['ip_label'].set_text(ip)

def build_popover(module, data):
    """ Build popover for network """
    module.popover_widgets = {}
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Network', style='heading'))

    names = {
        'GENERAL.DEVICE': 'Device', "GENERAL.CONNECTION": "SSID",
        'IP4.ADDRESS[1]': 'IP'
    }

    connected_any = False
    for device in data['devices']:
        state = device.get('GENERAL.STATE', '').lower()
        if 'connected' not in state:
            continue
        
        connected_any = True
        dev_name = device.get('GENERAL.DEVICE', 'unknown')
        network_box = c.box('v', spacing=10)
        network_box.append(c.label(device.get('GENERAL.TYPE', 'unknown'), style='title', ha='start'))
        device_box = c.box('v', style='box')
        
        module.popover_widgets[dev_name] = {}
        
        items = []
        for long, short in names.items():
            if short == 'SSID' and device.get('GENERAL.TYPE') != 'wifi':
                continue
            if long in device:
                items.append((short, device[long], long))
        
        for i, (short, val, long) in enumerate(items):
            line = c.box('h', style='inner-box')
            line.append(c.label(short))
            val_label = c.label(val, ha='end', he=True)
            line.append(val_label)
            device_box.append(line)
            
            if long == 'IP4.ADDRESS[1]':
                module.popover_widgets[dev_name]['ip_label'] = val_label
                
            if i != len(items) - 1:
                device_box.append(c.sep('h'))
                
        network_box.append(device_box)
        main_box.append(network_box)

    if not connected_any:
        main_box.append(c.label("No active connections", style='gray'))

    return main_box
