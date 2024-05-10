#!/usr/bin/python3
"""
Upower module for battery info
Author: thnikk
"""
import json
import subprocess
import jc

# Get upower output through subprocess
upower_output = subprocess.check_output(['upower', '-d'], text=True)
# Format output for json
upower_json = jc.parse('upower', upower_output)

device_icons = {
    "mouse": "",
    "gaming-input": "",
    "headphones": "",
}

battery_icons = ["<span color=\"#bf616a\"></span>", "", "", "", ""]

out_dict = {
    "text": "",
    "alt": "",
    "tooltip": "",
}


def get_icon(name, icon_table) -> str:
    """ Get icon for name """
    for item, icon in icon_table.items():
        if item.lower() in name.lower():
            return icon
    return '?'


def main():
    """ Main """
    # Iterate through devices
    for device in upower_json:
        # Check to see if the detail section exists for the device
        if 'detail' in device.keys():
            # print(device)
            # Check to see if the percentage isn't 0
            if device['detail']['percentage'] != 0.0:
                # Get the type of device
                try:
                    name = device['model']
                except KeyError:
                    continue
                # Only pull percentage up to . or % (first 2 digits)
                percent = int(str(device['detail']['percentage']
                                  ).split('.', 1)[0].split('%', 1)[0])

                battery_icon = battery_icons[percent // 25]

                ICON = get_icon(name, device_icons)

                out_dict["text"] = battery_icon
                out_dict["alt"] = out_dict["alt"] + \
                    ICON + " " + battery_icon + " "
                out_dict["tooltip"] = out_dict["tooltip"] + \
                    name + " " + str(percent) + "\n"

    # Remove trailing delimeters
    out_dict["text"] = out_dict["text"].rstrip(' ')
    out_dict["alt"] = out_dict["alt"].rstrip(' ')
    out_dict["tooltip"] = out_dict["tooltip"].rstrip('\n')

    print(json.dumps(out_dict))


if __name__ == "__main__":
    main()
