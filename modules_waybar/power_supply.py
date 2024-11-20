#!/usr/bin/python3 -u
"""
Description: Get info for power supply devices
Author: thnikk
"""
from glob import glob


icon_lookup = {
    "Mouse": "",
    "Controller": "",
}

capacity_lookup = [
    "critical", "low", "normal", "high", "full"
]


def parse(uevent) -> dict:
    """ Parse uevent file """
    output = {}
    for line in uevent.splitlines():
        left = line.split('=')[0].replace(
            'POWER_SUPPLY_', '').replace('_', ' ').capitalize()
        right = line.split('=')[-1]
        output[left] = right
    return output


def module(config) -> dict:
    """ Module function """
    icons = []
    devices = []
    for path in glob('/sys/class/power_supply/*'):
        with open(f"{path}/uevent") as file:
            # Read the file
            uevent = file.read()
            # Parse the data
            parsed = parse(uevent)

            # Set the device name
            if "Model name" in parsed:
                device_name = parsed["Model name"]
            elif "Name" in parsed:
                device_name = parsed["Name"]
                device_name = device_name.split(
                    "battery")[0].replace('-', ' ').strip().title()
            else:
                device_name = "Unknown"

            # Set the battery level
            if "Capacity level" in parsed:
                level = capacity_lookup.index(parsed["Capacity level"].lower())
            elif "Capacity" in parsed:
                level = int(parsed["Capacity"])//20
            else:
                level = -1

            # Create device dictionary
            device = {device_name: level}

            # Set a default icon if the device type isn't in the icon lookup
            device_icon = ""
            for name, icon in icon_lookup.items():
                if name.lower() in device_name.lower():
                    device_icon = icon
            # Append the icon to the icons list
            icons.append(device_icon)

            # Append the device to the devices list
            devices.append(device)

    # Return the output with the widget data
    output = {"text": "  ".join(set(icons)), "widget": devices}
    return output


def main() -> None:
    """ Main function for debugging """
    print(module(None))


if __name__ == "__main__":
    main()
