#!/usr/bin/python3 -u
"""
Description: Daily Etsy sales tracker that uses subprocess
Author: thnikk
"""
from subprocess import run
from datetime import datetime
import json


def get_messages():
    """ Get email messages from notmuch matching criteria """
    mail = [
        line.split(':')[1].split()[0] for line in
        run([
            "notmuch", "search",
            "from:transaction@etsy.com and date:today "
            "and (subject:'Etsy order confirmation for' or "
            "subject:'You made a sale on Etsy')"],
            check=False, capture_output=True
            ).stdout.decode('utf-8').splitlines()
    ]

    messages = [
        run(
            ["notmuch", "show", id], check=False, capture_output=True
        ).stdout.decode('utf-8')
        for id in mail
    ]
    return messages


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


def module(_):
    """ Module """
    widget = []
    messages = get_messages()
    for message in messages:
        order = []
        for item, info in parse_order(message.splitlines()).items():
            order.append({
                "item": item, "quantity": info["quantity"],
                "price": info["price"]})
        widget.append(order)

    if messages:
        output = {
            "text": f' {len(messages)}',
            "widget": {"orders": widget}
        }
    else:
        output = {"text": ""}

    return output


def main():
    """ Main function """
    print(json.dumps(module()))


if __name__ == "__main__":
    main()
