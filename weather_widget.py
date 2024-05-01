#!/usr/bin/python3 -u
"""
Description: Weather widget
Author: thnikk
"""
import argparse
import json
import os
import common as c


def weather_widget(cache):
    """ Weather widget """

    widget = c.box('v', style='widget', spacing=20)

    today = cache['Today']['info'][0]
    today_box = c.box('h', spacing=10)

    today_left = c.box('v')
    widget.add(c.label(cache['City'], style='heading'))
    temp = c.label(
        f"{today['temperature']}° {today['icon']}", 'today-weather')
    today_left.add(temp)

    extra = c.h_lines([
        f" {today['humidity']}%",
        f" {today['wind']}mph",
    ], style='extra')
    today_left.add(extra)

    today_right = c.box('v')
    today_right.pack_start(c.v_lines([
        today['description'],
        f"Feels like {today['feels_like']}°",
        f"{today['quality']} air quality"
    ], right=True), True, False, 0)

    today_box.pack_start(today_left, False, False, 0)

    sun_box = c.box('v')
    try:
        sun_box.add(c.label(f' {today["sunset"]}pm', 'sun'))
    except KeyError:
        sun_box.add(c.label(f' {today["sunrise"]}am', 'sun'))
    today_box.pack_start(sun_box, False, False, 0)

    today_box.pack_end(today_right, False, False, 0)

    widget.add(today_box)

    hourly_container = c.box('v', spacing=10)
    hourly_container.add(c.label('Hourly forecast', style='title', ha="start"))
    hourly_box = c.box('h', style='box')
    for hour in cache['Hourly']['info']:
        hour_box = c.box('v', style='inner-box')
        hour_box.add(c.label(f"{hour['temperature']}°", style='hour-temp'))
        hour_box.add(c.label(f"{hour['humidity']}%"))
        icon = c.label(hour['icon'], style='icon-small')
        icon.props.tooltip_text = hour['description']
        hour_box.add(icon)
        hour_box.add(c.label(hour['time']))
        hourly_box.pack_start(hour_box, True, False, 0)
        if hour != cache['Hourly']['info'][-1]:
            hourly_box.add(c.sep('v'))
    hourly_container.add(hourly_box)
    widget.add(hourly_container)

    daily_container = c.box('v', spacing=10)
    daily_container.add(c.label(
        'Daily forecast', style='title', ha='start'))
    daily_box = c.box('v', style='box')
    for day in cache['Daily']['info']:
        day_box = c.box('h', style='inner-box')
        day_box.add(c.label(day['time']))
        day_box.pack_end(
            c.label(f"{day['high']}° / {day['low']}°"), False, False, 0)
        icon = c.label(day['icon'])
        icon.props.tooltip_text = day['description']
        day_box.set_center_widget(icon)

        daily_box.add(day_box)
        if day != cache['Daily']['info'][-1]:
            daily_box.add(c.sep('h'))
    daily_container.add(daily_box)
    widget.add(daily_container)
    return widget
