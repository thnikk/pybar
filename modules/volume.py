#!/usr/bin/python3 -u
"""
Description: Pulse module refactored for unified state
Author: thnikk
"""
import common as c
import pulsectl
import threading
import time
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, GLib, GObject, Pango  # noqa

def get_volume_data(pulse):
    """ Get current pulse data """
    try:
        default_sink = pulse.sink_default_get()
        sinks = pulse.sink_list()
        sources = pulse.source_list()
        sink_inputs = pulse.sink_input_list()
        
        def serialize_device(d):
            # For programs (sink inputs), we often need to look at proplist for a name
            name = getattr(d, 'name', None)
            description = getattr(d, 'description', None)
            proplist = dict(d.proplist) if hasattr(d, 'proplist') else {}
            
            if not description:
                description = proplist.get('application.name', proplist.get('media.name', name or 'Unknown'))
            if not name:
                name = proplist.get('application.process.binary', description)

            return {
                'index': d.index,
                'name': name,
                'description': description,
                'volume': d.volume.value_flat,
                'mute': bool(d.mute),
                'proplist': proplist
            }

        return {
            'default_sink': serialize_device(default_sink) if default_sink else None,
            'outputs': [serialize_device(s) for s in sinks],
            'inputs': [serialize_device(s) for s in sources],
            'programs': [serialize_device(s) for s in sink_inputs]
        }
    except Exception as e:
        c.print_debug(f"Error fetching volume data: {e}", color='red')
        return None

def run_worker(name, config):
    """ Background worker for volume """
    while True:
        try:
            with pulsectl.Pulse('pybar-volume-worker') as pulse:
                def update():
                    try:
                        data = get_volume_data(pulse)
                        if data:
                            c.state_manager.update(name, data)
                    except Exception as e:
                        c.print_debug(f"Volume update failed: {e}", color='red')

                # Initial update
                update()

                def event_callback(ev):
                    raise pulsectl.PulseLoopStop
                
                pulse.event_mask_set('sink', 'sink_input', 'source')
                pulse.event_callback_set(event_callback)
                
                while True:
                    pulse.event_listen()
                    update()
        except Exception as e:
            c.print_debug(f"Volume worker error: {e}", color='red')
            time.sleep(5)

def create_widget(bar, config):
    """ Create volume module widget """
    module = c.Module()
    module.set_position(bar.position)
    c.add_style(module, 'module-fixed')
    module.icons = config.get('icons', {})
    module.set_label('...')
    module.set_icon('')
    
    # Add scroll controller
    scroll_controller = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.BOTH_AXES)
    scroll_controller.connect('scroll', lambda c, dx, dy: handle_scroll(module, dx, dy))
    module.add_controller(scroll_controller)
    
    # Add right-click for mute
    click_controller = Gtk.GestureClick.new()
    click_controller.set_button(3) # Right click
    click_controller.connect('released', lambda c, n, x, y: toggle_default_mute())
    module.add_controller(click_controller)
    
    return module

def handle_scroll(module, dx, dy):
    """ Handle scroll on module """
    with pulsectl.Pulse('volume-action') as pulse:
        default = pulse.sink_default_get()
        if dy > 0:
            pulse.volume_change_all_chans(default, -0.01)
        elif dy < 0:
            if default.volume.value_flat < 1:
                pulse.volume_change_all_chans(default, 0.01)
            else:
                pulse.volume_set_all_chans(default, 1)

def toggle_default_mute():
    """ Toggle default sink mute """
    with pulsectl.Pulse('volume-action') as pulse:
        default = pulse.sink_default_get()
        if default:
            pulse.mute(default, not default.mute)

def update_ui(module, data):
    """ Update volume UI """
    default = data.get('default_sink')
    module.set_visible(True)
    if not default:
        module.set_label('ERR')
        module.set_icon('')
        return

    volume = round(default['volume'] * 100)
    module.set_label(f'{volume}%')
    
    # Set icon
    if default['mute']:
        module.set_icon('')
    else:
        found = False
        for name, icon in module.icons.items():
            if name.lower() in default['name'].lower():
                module.set_icon(icon)
                found = True
                break
        if not found:
            module.set_icon('')

    # Update popover content
    if not module.get_active():
        module.set_widget(build_popover_content(data))

def build_popover_content(data):
    """ Build popover for volume """
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Volume', style='heading'))
    
    content_box = c.box('v', spacing=20)
    
    sections = [
        ('Outputs', data.get('outputs', [])),
        ('Inputs', data.get('inputs', [])),
        ('Programs', data.get('programs', []))
    ]
    
    for name, devices in sections:
        if not devices:
            continue
        
        section_box = c.box('v', spacing=10)
        section_box.append(c.label(name, style='title', ha='start'))
        devices_box = c.box('v', style='box')
        
        for i, device in enumerate(devices):
            # Skip monitors
            if name != 'Programs' and 'Monitor of' in device.get('description', ''):
                continue
                
            dev_row = build_device_row(name, device)
            devices_box.append(dev_row)
            if i != len(devices) - 1:
                devices_box.append(c.sep('h'))
        
        section_box.append(devices_box)
        content_box.append(section_box)
        
    scroll = c.scroll(height=400)
    scroll.set_child(content_box)
    main_box.append(scroll)
    return main_box

def build_device_row(section, device):
    """ Build a row for a single pulse device """
    row = c.box('v', spacing=5, style='inner-box')
    
    top = c.box('h', spacing=10)
    
    # Mute switch
    mute_switch = Gtk.Switch()
    mute_switch.set_active(not device.get('mute', False))
    mute_switch.set_valign(Gtk.Align.CENTER)
    mute_switch.connect('state-set', lambda s, state: toggle_mute(section, device['index'], state))
    top.append(mute_switch)
    
    # Label
    label_text = device.get('proplist', {}).get('application.process.binary', device.get('description', 'Unknown'))
    btn = c.button(label_text, ha='start', style='minimal')
    if section != 'Programs':
        btn.connect('clicked', lambda b: set_default(section, device['name']))
    btn.set_hexpand(True)
    top.append(btn)
    
    row.append(top)
    
    # Volume slider
    slider = c.slider(round(device.get('volume', 0) * 100))
    slider.connect('value-changed', lambda s: set_dev_volume(section, device['index'], s.get_value()))
    if device.get('mute'):
        c.add_style(slider, 'muted')
    row.append(slider)
    
    return row

def toggle_mute(section, index, state):
    with pulsectl.Pulse('volume-action') as pulse:
        dev = None
        if section == 'Outputs':
            dev = next((s for s in pulse.sink_list() if s.index == index), None)
        elif section == 'Inputs':
            dev = next((s for s in pulse.source_list() if s.index == index), None)
        elif section == 'Programs':
            dev = next((s for s in pulse.sink_input_list() if s.index == index), None)
        
        if dev:
            pulse.mute(dev, not state)
    return True

def set_dev_volume(section, index, value):
    with pulsectl.Pulse('volume-action') as pulse:
        dev = None
        if section == 'Outputs':
            dev = next((s for s in pulse.sink_list() if s.index == index), None)
        elif section == 'Inputs':
            dev = next((s for s in pulse.source_list() if s.index == index), None)
        elif section == 'Programs':
            dev = next((s for s in pulse.sink_input_list() if s.index == index), None)
        
        if dev:
            pulse.volume_set_all_chans(dev, value / 100)

def set_default(section, name):
    with pulsectl.Pulse('volume-action') as pulse:
        if section == 'Outputs':
            sink = next((s for s in pulse.sink_list() if s.name == name), None)
            if sink: pulse.default_set(sink)
        elif section == 'Inputs':
            source = next((s for s in pulse.source_list() if s.name == name), None)
            if source: pulse.default_set(source)
