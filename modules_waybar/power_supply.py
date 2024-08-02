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
            # Try to set the battery level
            try:
                device = {
                    parsed["Model name"]:
                    capacity_lookup.index(parsed["Capacity level"].lower())
                }
            # If the battery level is unknown, set the value to -1
            except ValueError:
                device = {parsed["Model name"]: -1}

            # Set a default icon if the device type isn't in the icon lookup
            device_icon = ""
            for name, icon in icon_lookup.items():
                if name in parsed["Model name"]:
                    device_icon = icon
                    for key, value in device.items():
                        if value == 1 or value == 0:
                            device_icon = (
                                "<span color='#FF0000'>"
                                f"{device_icon}</span")
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
