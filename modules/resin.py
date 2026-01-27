#!/usr/bin/python3 -u
"""
Description: Genshin resin module refactored for unified state with original formatting
Author: thnikk
"""
import asyncio
from datetime import datetime, timezone
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

try:
    import genshin
except ImportError:
    genshin = None

def time_diff(now, future, rate):
    max_time = future - now
    until_next = (max_time.seconds // 60) % (rate * 40)
    return f"{until_next // 60}:{until_next % 60}"

def time_to_text(time_string) -> str:
    """ Convert time to text string """
    try:
        hours = int(time_string.split(':')[0])
        mins = int(time_string.split(':')[1])
        output = []
        for unit, value in {"hour": hours, "minute": mins}.items():
            if value > 1:
                output.append(f'{value} {unit}s')
            elif value == 1:
                output.append(f'{value} {unit}')
        return " ".join(output)
    except (ValueError, IndexError, AttributeError):
        return str(time_string)

async def get_genshin_data(config):
    if not genshin: return None
    try:
        client = genshin.Client({"ltuid": config["ltuid"], "ltoken": config["ltoken"]})
        notes = await client.get_notes()
        com_prog = notes.completed_commissions + int(notes.claimed_commission_reward)
        now = datetime.now(timezone.utc)
        
        return {
            "Name": "Genshin Impact",
            "Icon": "",
            "Resin": notes.current_resin,
            "Until next 40": time_diff(now, notes.resin_recovery_time, 8),
            "Dailies completed": f"{com_prog}/5",
            "Remaining boss discounts": notes.remaining_resin_discounts,
            "Realm currency": notes.current_realm_currency,
        }
    except Exception: return None

def fetch_data(config):
    if not genshin: return None
    try:
        data = asyncio.run(get_genshin_data(config))
        if not data: return None
        
        dailies = data["Dailies completed"].split("/")
        dailies_done = int(dailies[0]) == int(dailies[1])
        capped = data['Realm currency'] >= 2000
        
        cls = ""
        if not dailies_done and not capped: cls = "red"
        elif dailies_done and capped: cls = "yellow"
        elif not dailies_done and capped: cls = "orange"
        
        data["class"] = cls
        data["text"] = f"{data['Icon']} {data['Resin']}"
        return data
    except Exception: return None

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    return module

def update_ui(module, data):
    module.set_label(data['text'])
    module.reset_style()
    if data.get('class'):
        c.add_style(module, data['class'])
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(cache):
    """ Original Genshin widget formatting """
    main_box = c.box('v', spacing=20)
    c.add_style(main_box, 'small-widget')
    label = c.label(cache['Name'], style='heading')
    main_box.append(label)

    # Icons mapping
    icons = [{
        "Dailies completed": "", "Realm currency": "",
        "Remaining boss discounts": ""}]

    # Top section
    top_box = c.box('h', spacing=20)
    top_box.append(c.label(
        f"{cache['Icon']} {cache['Resin']}",
        style='today-weather', ha='start'))
    
    right_box = c.box('v')
    right_box.append(c.label(time_to_text(cache['Until next 40'])))
    right_box.append(c.label('until next 40', style='gray'))
    top_box.append(right_box)
    main_box.append(top_box)

    # Info section
    info_box = c.box('v', style='box')
    for line in icons:
        info_line = c.box('h')
        for name, icon in line.items():
            if name in cache:
                label = c.label(f'{icon} {cache[name]}', style='inner-box')
                label.set_tooltip_text(name)
                info_line.append(label)
                if name != list(line)[-1]:
                    info_line.append(c.sep('v'))
        info_box.append(info_line)
        if line != list(icons)[-1]:
            info_box.append(c.sep('h'))

    main_box.append(info_box)
    return main_box
