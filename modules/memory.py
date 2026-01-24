#!/usr/bin/python3 -u
"""
Description: Memory module refactored for unified state with cleaned up layout
Author: thnikk
"""
import common as c
import psutil
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def fetch_data(config):
    """ Get memory usage """
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    total = round(mem.total / (1024.0 ** 3), 1)
    used = round(mem.used / (1024.0 ** 3), 1)
    
    total_swap = round(swap.total / (1024.0 ** 3), 1)
    used_swap = round(swap.used / (1024.0 ** 3), 1)
    
    return {
        "total": total,
        "used": used,
        "percent": mem.percent,
        "swap_total": total_swap,
        "swap_used": used_swap,
        "swap_percent": swap.percent,
        "text": f"{round(used)}"
    }

def create_widget(bar, config):
    """ Create memory module widget """
    module = c.Module()
    module.set_position(bar.position)
    module.icon.set_label('')
    return module

def update_ui(module, data):
    """ Update memory UI """
    module.text.set_label(data['text'])
    
    if not module.get_active():
        module.set_widget(build_popover(module, data))
    else:
        # Live update popover if open
        if hasattr(module, 'popover_widgets'):
            module.popover_widgets['ram_val'].set_text(f"{data['used']}GB / {data['total']}GB")
            module.popover_widgets['ram_lvl'].set_value(data['percent'])
            module.popover_widgets['swap_val'].set_text(f"{data['swap_used']}GB / {data['swap_total']}GB")
            module.popover_widgets['swap_lvl'].set_value(data['swap_percent'])

def build_popover(module, data):
    """ Build popover for memory with consistent layout """
    module.popover_widgets = {}
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Memory', style='heading'))
    
    usage_section = c.box('v', spacing=10)
    usage_section.append(c.label('Usage', style='title', ha='start'))
    
    usage_box = c.box('v', style='box')
    
    # RAM row
    ram_row = c.box('v', spacing=5, style='inner-box')
    ram_top = c.box('h')
    ram_top.append(c.label('RAM'))
    ram_val = c.label(f"{data['used']}GB / {data['total']}GB", ha='end', he=True)
    ram_top.append(ram_val)
    ram_row.append(ram_top)
    ram_level = Gtk.LevelBar.new_for_interval(0, 100)
    ram_level.set_min_value(0)
    ram_level.set_max_value(100)
    ram_level.set_value(data['percent'])
    ram_row.append(ram_level)
    usage_box.append(ram_row)
    
    usage_box.append(c.sep('h'))
    
    # Swap row
    swap_row = c.box('v', spacing=5, style='inner-box')
    swap_top = c.box('h')
    swap_top.append(c.label('Swap'))
    swap_val = c.label(f"{data['swap_used']}GB / {data['swap_total']}GB", ha='end', he=True)
    swap_top.append(swap_val)
    swap_row.append(swap_top)
    swap_level = Gtk.LevelBar.new_for_interval(0, 100)
    swap_level.set_min_value(0)
    swap_level.set_max_value(100)
    swap_level.set_value(data['swap_percent'])
    swap_row.append(swap_level)
    usage_box.append(swap_row)
    
    usage_section.append(usage_box)
    main_box.append(usage_section)
    
    module.popover_widgets = {
        'ram_val': ram_val, 'ram_lvl': ram_level,
        'swap_val': swap_val, 'swap_lvl': swap_level
    }
    return main_box
