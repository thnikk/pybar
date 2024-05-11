#!/usr/bin/python3 -u
"""
Description: Etsy sales module
Author: thnikk
"""

import email.parser
import email.header
from email.policy import default
import json
import os
from notmuch import Query, Database, Message


def parse_order(lines):
    """ Get lines matching info from file """
    output = {}
    for line in lines:
        if "Item:" in line:
            item = line.split(':', 1)[1].strip()
            output[item] = {}
        if "Quantity:" in line:
            try:
                output[item]['quantity'] += int(line.split(':', 1)[1].strip())
            except KeyError:
                output[item]['quantity'] = int(line.split(':', 1)[1].strip())
        if "Item price:" in line:
            output[item]['price'] = float(line.split("$", 1)[1])
    return output


def get_orders():
    """ Get sale data from email"""
    db = Database(os.path.expanduser('~/.local/share/mail'), create=False)
    all_mail = Query(db, (
        'from:transaction@etsy.com and date:today and (subject:"Etsy order '
        'confirmation for" or subject:"You made a sale on Etsy)"'
    )).search_messages()

    orders = []

    for mail in all_mail:
        filename = Message.get_filename(mail)
        msg = email.message_from_file(open(filename, 'r', encoding='utf-8'),
                                      policy=email.policy.default)
        body = msg.get_body(('plain',)).get_content()

        orders.append(parse_order(body.splitlines()))
    return orders


def module(config):
    """ Module """
    orders = get_orders()
    if not orders:
        return {"text": ""}
        return

    tooltip = []
    widget = []
    for order in orders:
        widget_order = []
        for item, info in order.items():
            tooltip.append(f'{item} x{info["quantity"]} ${info["price"]:.2f}')
            widget_order.append({
                "item": item, "quantity": info["quantity"],
                "price": info["price"]})
        widget.append(widget_order)

    return {
        "text": f' {len(orders)}',
        "tooltip": "\n".join(tooltip),
        "widget": {"orders": widget},
    }


def main():
    """ Main function """
    print(json.dumps(module(), indent=4))


if __name__ == "__main__":
    main()
