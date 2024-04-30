#!/usr/bin/python3 -u
"""
Description:
Author:
"""
from datetime import datetime
import time
import calendar


def clock_module(label):
    """ d """
    while True:
        label.set_label(f" {datetime.now().strftime('%I:%M %m/%d')}")
        # now = datetime.now()
        # cal = calendar.TextCalendar(firstweekday=6)
        # label.props.tooltip_text = cal.formatmonth(
        #     now.year, now.month).rstrip()
        time.sleep(1)
