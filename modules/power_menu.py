#!/usr/bin/python3 -u
import common as c


def module():
    module = c.Module(text=False)
    module.icon.set_label("")
    module.set_widget("Power menu")
    power_box = c.box('v', style='split-container')
    menu_items = [
        "Lock ", "Log out ", "Suspend ",
        "Reboot ", "Reboot to UEFI ", "Shutdown "
    ]
    for item in menu_items:
        item_label = c.label(item, he=True, ha='end', style='split-box')
        power_box.append(item_label)
        if item != menu_items[-1]:
            power_box.append(c.sep('v'))
    module.widget_content.append(power_box)
    return module
