#!/usr/bin/python3
"""
Description: Shows number of running VMs and lists the running VMs in the
tooltip.
Author: thnikk
"""
import glob
import json
from datetime import datetime


def get_libvirt():
    """ Get domains with list comprehension """
    return [
        domain_path.split("/")[-1:][0].rstrip(".xml")
        for domain_path in glob.glob("/var/run/libvirt/qemu/*.xml")]


def module(_):
    """ Module """
    domains = get_libvirt()
    if not domains:
        return {"text": ""}

    return {
        "text": f" {str(len(domains))}",
        "tooltip": datetime.now().timestamp(),
        "widget": {"libvirt": domains}
    }


def main():
    """ Main function """
    print(json.dumps(module(), indent=4))


if __name__ == "__main__":
    main()
