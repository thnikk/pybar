#!/usr/bin/python3 -u
"""
Description: Sales module refactored for unified state
Author: thnikk
"""
from subprocess import run
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def get_messages():
    try:
        mail = [
            line.split(':')[1].split()[0] for line in
            run(["notmuch", "search", "from:transaction@etsy.com and date:today and (subject:'Etsy order confirmation for' or subject:'You made a sale on Etsy')"],
                check=False, capture_output=True).stdout.decode('utf-8').splitlines()
        ]
        messages = [run(["notmuch", "show", mid], check=False, capture_output=True).stdout.decode('utf-8') for mid in mail]
        return messages
    except Exception: return []

def parse_order(lines):
    output = {}
    item = None
    for line in lines:
        if "Item:" in line:
            item = line.split(':', 1)[1].strip()
            if item not in output: output[item] = {'quantity': 0, 'price': 0.0}
        if "Quantity:" in line and item:
            output[item]['quantity'] += int(line.split(':', 1)[1].strip())
        if "Item price:" in line and item:
            output[item]['price'] = float(line.split("$", 1)[1])
    return output

def fetch_data(config):
    messages = get_messages()
    orders = []
    for msg in messages:
        parsed = parse_order(msg.splitlines())
        if parsed:
            orders.append([{"item": k, "quantity": v["quantity"], "price": v["price"]} for k, v in parsed.items()])
            
    total_sales = len(orders)
    return {
        "text": f' {total_sales}' if total_sales else "",
        "orders": orders
    }

def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    module.set_visible(False)
    return module

def update_ui(module, data):
    module.text.set_label(data['text'])
    module.set_visible(bool(data['text']))
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(data):
    main_box = c.box('v', spacing=20, style='small-widget')
    main_box.append(c.label('Sales', style='heading'))

    total_amount = 0
    for order in data["orders"]:
        order_box = c.box('v', style='box')
        for item in order:
            line = c.box('h', style='inner-box', spacing=20)
            line.append(c.label(item['item'], ha='start', he=True))
            line.append(c.label(f"x{item['quantity']}"))
            line_total = item['price'] * item['quantity']
            total_amount += line_total
            line.append(c.label(f"${line_total:.2f}", style='green-fg'))
            order_box.append(line)
        main_box.append(order_box)
        
    main_box.append(c.sep('h'))
    total_box = c.box('h', style='inner-box')
    total_box.append(c.label('Total', ha='start', he=True))
    total_box.append(c.label(f'${total_amount:.2f}', style='green-fg'))
    main_box.append(total_box)

    return main_box
