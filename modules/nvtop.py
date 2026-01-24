#!/usr/bin/python3 -u
"""
Description: NVTop module restored to original customized layout
Author: thnikk
"""
import json
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def fetch_data(config):
    """ Get GPU data from nvtop """
    try:
        res = run(['nvtop', '-s'], capture_output=True, check=True).stdout.decode('utf-8')
        devices = json.loads(res)
        return {"devices": devices}
    except Exception:
        return None

def create_widget(bar, config):
    """ Create GPU module widget with original layout """
    module = c.Module(text=False)
    
    # Store UI elements for updating
    module.bar_gpu_levels = [] # List of (load_bar, mem_bar) pairs
    module.popover_widgets = [] # List of dicts with levelbars and labels per device

    # Bar icon structure: cards_box contains levels_box per GPU
    module.cards_box = c.box('h', spacing=15)
    module.cards_box.set_margin_start(5)
    module.box.append(module.cards_box)

    module.set_icon('')
    module.box.set_spacing(5)
    module.set_visible(True)
    
    for _ in range(2):
        levels_box = c.box('h', spacing=4)
        l1 = Gtk.LevelBar.new_for_interval(0, 100)
        l1.set_min_value(0)
        l1.set_max_value(100)
        Gtk.Orientable.set_orientation(l1, Gtk.Orientation.VERTICAL)
        l1.set_inverted(True)
        
        l2 = Gtk.LevelBar.new_for_interval(0, 100)
        l2.set_min_value(0)
        l2.set_max_value(100)
        Gtk.Orientable.set_orientation(l2, Gtk.Orientation.VERTICAL)
        l2.set_inverted(True)
        
        levels_box.append(l1)
        levels_box.append(l2)
        module.bar_gpu_levels.append((l1, l2))
        module.cards_box.append(levels_box)
        
    return module

def safe_parse_percent(val):
    """ Safely parse percentage string to int """
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    try:
        return int(str(val).strip('%'))
    except (ValueError, TypeError):
        return 0

def update_ui(module, data):
    """ Update GPU UI including bar and popover """
    if not data:
        return
    devices = data.get('devices', [])
    
    if devices:
        module.set_visible(True)
    else:
        module.set_visible(False)
    
    # Update bar icons
    for i, (l1, l2) in enumerate(module.bar_gpu_levels):
        if i < len(devices):
            dev = devices[i]
            load = safe_parse_percent(dev.get('gpu_util'))
            mem = safe_parse_percent(dev.get('mem_util'))
            l1.set_value(load)
            l2.set_value(mem)
            l1.get_parent().set_visible(True)
            module._update_spacing() # Ensure spacing if indicators become visible
        else:
            l1.get_parent().set_visible(False)

    # Rebuild or update popover
    if not module.get_active():
        # Re-create the popover structure with SizeGroups
        module.set_widget(build_popover(module, data))
    else:
        # If active, we try to update existing widgets to avoid flickering
        for i, device_widgets in enumerate(module.popover_widgets):
            if i < len(devices):
                dev = devices[i]
                load = safe_parse_percent(dev.get('gpu_util'))
                mem = safe_parse_percent(dev.get('mem_util'))
                
                device_widgets['load']['level'].set_value(load)
                device_widgets['load']['label'].set_text(f"{load}%")
                device_widgets['mem']['level'].set_value(mem)
                device_widgets['mem']['label'].set_text(f"{mem}%")
                
                if 'device_label' in device_widgets:
                    device_widgets['device_label'].set_text(dev.get('device_name', f'Device {i}'))

def build_popover(module, data):
    """ Build the complex original popover layout """
    devices = data.get('devices', [])
    module.popover_widgets = []
    
    main_box = c.box('v', spacing=10)
    main_box.append(c.label('GPU info', style="heading"))
    
    devices_box = c.box('v', spacing=10)
    
    # Groups for alignment
    bar_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
    label_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
    
    for i in range(2):
        card_box = c.box('v', spacing=4)
        
        # Device title
        dev_name = devices[i].get('device_name', f'Device {i}') if i < len(devices) else f'Device {i}'
        device_label = c.label(dev_name, style='title', ha='start', he=True)
        card_box.append(device_label)
        
        info_outer_box = c.box('v', spacing=0, style='box')
        inner_info_box = c.box('v', spacing=10, style='inner-box')
        
        device_widgets = {'device_label': device_label}
        
        # Rows for GPU and Memory utilization icons
        for item_key, label_icon in [('gpu_util', ''), ('mem_util', '')]:
            line_box = c.box('h', spacing=10)
            line_box.append(c.label(label_icon))
            
            lvl = Gtk.LevelBar.new_for_interval(0, 100)
            lvl.set_min_value(0)
            lvl.set_max_value(100)
            lvl.set_hexpand(True)
            c.add_style(lvl, 'level-horizontal')
            bar_group.add_widget(lvl)
            
            val = safe_parse_percent(devices[i].get(item_key)) if i < len(devices) else 0
            lvl.set_value(val)
            
            pct_label = Gtk.Label.new(f'{val}%')
            pct_label.set_xalign(1)
            label_group.add_widget(pct_label)
            
            line_box.append(lvl)
            line_box.append(pct_label)
            inner_info_box.append(line_box)
            
            short_key = 'load' if 'gpu' in item_key else 'mem'
            device_widgets[short_key] = {'level': lvl, 'label': pct_label}
            
        info_outer_box.append(inner_info_box)
        card_box.append(info_outer_box)
        devices_box.append(card_box)
        module.popover_widgets.append(device_widgets)
        
        if i >= len(devices):
            card_box.set_visible(False)
            
    main_box.append(devices_box)
    return main_box
