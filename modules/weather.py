#!/usr/bin/python3 -u
"""
Description: Weather module refactored for unified state with original formatting
Author: thnikk
"""
from datetime import datetime, timedelta, timezone
import requests
import common as c
import gi
import os
import json
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa

def lookup(code, mode, night=False):
    """ Get description for weather code """
    weather_lookup = {
        0:  ["", "Clear"], 1:  ["", "Mostly clear"], 2:  ["", "Partly cloudy"],
        3:  ["", "Overcast"], 45: ["", "Fog"], 48: ["", "Depositing rime fog"],
        51: ["", "Light drizzle"], 53: ["", "Moderate drizzle"], 55: ["", "Dense drizzle"],
        56: ["", "Light freezing drizzle"], 57: ["", "Dense freezing drizzle"],
        61: ["", "Slight rain"], 63: ["", "Moderate rain"], 65: ["", "Heavy rain"],
        66: ["", "Light freezing rain"], 67: ["", "Heavy freezing rain"],
        71: ["", "Slight snow"], 73: ["", "Moderate snow"], 75: ["", "Heavy snow"],
        77: ["", "Snow grains"], 80: ["", "Slight rain showers"], 81: ["", "Moderate rain showers"],
        82: ["", "Violent rain showers"], 85: ["", "Slight snow showers"], 86: ["", "Heavy snow showers"],
        95: ["", "Thunderstorm"], 96: ["", "Slight hailing thunderstorm"], 99: ["", "Heavy hailing thunderstorm"]
    }
    if night:
        weather_lookup[0][0] = ""
        weather_lookup[1][0] = ""
        weather_lookup[2][0] = ""
    return weather_lookup[code][mode]

def aqi_to_desc(value) -> str:
    """ Get description for aqi """
    for desc in [
        (50, "Good"), (100, "Moderate"), (150, "Unhealthy"),
        (200, "Unhealthy"), (300, "Very unhealthy"), (500, "Hazardous")
    ]:
        if 0 < value < desc[0]:
            return desc[1]
    return "Unknown"

def time_to_text(time_string) -> str:
    """ Convert time to text string """
    try:
        hours = int(time_string.split(':')[0])
        mins = int(time_string.split(':')[1])
        output = []
        for unit, value in {"hour": hours, "minute": mins}.items():
            if value > 1:
                output.append(f'{value} {unit}s')
            elif value == 1:
                output.append(f'{value} {unit}')
        return " ".join(output)
    except (ValueError, IndexError, AttributeError):
        return str(time_string)

def fetch_data(config):
    """ Fetch weather data from OpenMeteo """
    zip_code = config.get('zip_code', "94102")
    night_icons = config.get('night_icons', True)
    hours_to_show = config.get('hours', 5)
    
    try:
        # Geocode
        geo = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={
            "name": zip_code, "count": 1, "language": "en", "format": "json"
        }, timeout=5).json()
        
        if not geo.get('results'):
            return None
            
        res = geo['results'][0]
        lat, lon, tz, city = res['latitude'], res['longitude'], res['timezone'], res['name']
        
        # Weather
        w = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": lat, "longitude": lon, "temperature_unit": "fahrenheit", "timezone": tz,
            "hourly": ["temperature_2m", "relativehumidity_2m", "weathercode", "apparent_temperature", "windspeed_10m"],
            "daily": ["weathercode", "temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "wind_speed_10m_max"]
        }, timeout=5).json()
        
        # Pollution
        p = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
            "latitude": lat, "longitude": lon, "hourly": "us_aqi", "timezone": tz
        }, timeout=5).json()
        
        now = datetime.now()
        hour_now = now.hour
        
        sunrise_dt = datetime.strptime(w["daily"]["sunrise"][0], "%Y-%m-%dT%H:%M")
        sunset_dt = datetime.strptime(w["daily"]["sunset"][0], "%Y-%m-%dT%H:%M")
        sunrise = sunrise_dt.hour
        sunset = sunset_dt.hour
        
        is_night = (hour_now < sunrise or hour_now > sunset) and night_icons
        
        # Process Today data
        today_data = {
            "icon": lookup(w['hourly']['weathercode'][hour_now], 0, is_night),
            "description": lookup(w['hourly']['weathercode'][hour_now], 1),
            "temperature": round(w['hourly']['temperature_2m'][hour_now]),
            "feels_like": round(w['hourly']['apparent_temperature'][hour_now]),
            "humidity": w['hourly']['relativehumidity_2m'][hour_now],
            "wind": round(w['hourly']['windspeed_10m'][hour_now]),
            "quality": aqi_to_desc(p['hourly']['us_aqi'][hour_now]),
            "sunrise": sunrise_dt.strftime("%l %p").strip(),
            "sunset": sunset_dt.strftime("%l %p").strip()
        }
        today_data["sun_icon"] = "" if sunset > hour_now > sunrise else ""
        today_data["sun_time"] = today_data["sunset"] if sunset > hour_now > sunrise else today_data["sunrise"]

        # Process Hourly data
        hourly_info = []
        for h in range(1, hours_to_show + 1):
            target_time = now + timedelta(hours=h)
            h_idx = target_time.hour
            h_night = (h_idx < sunrise or h_idx > sunset) and night_icons
            hourly_info.append({
                "icon": lookup(w['hourly']['weathercode'][h_idx], 0, h_night),
                "description": lookup(w['hourly']['weathercode'][h_idx], 1),
                "humidity": w['hourly']['relativehumidity_2m'][h_idx],
                "time": target_time.strftime("%l%P").strip(),
                "temperature": round(w['hourly']['temperature_2m'][h_idx])
            })

        # Process Daily data
        daily_info = []
        for d in range(0, 5):
            target_day = now + timedelta(days=d)
            daily_info.append({
                "time": target_day.strftime('%A'),
                "high": round(w['daily']['temperature_2m_max'][d]),
                "low": round(w['daily']['temperature_2m_min'][d]),
                "description": lookup(w['daily']['weathercode'][d], 1),
                "icon": lookup(w['daily']['weathercode'][d], 0)
            })

        return {
            "City": city,
            "Today": {"info": [today_data]},
            "Hourly": {
                "info": hourly_info,
                "temperatures": [round(w['hourly']['temperature_2m'][now.hour + h]) for h in range(hours_to_show + 1)],
                "hours": hours_to_show,
                "min": config.get('min'),
                "max": config.get('max')
            },
            "Daily": {"info": daily_info},
            "text": f"{today_data['icon']} {today_data['temperature']}°F"
        }
    except Exception as e:
        c.print_debug(f"Weather fetch failed: {e}", color='red')
        return None

def create_widget(bar, config):
    """ Create weather module """
    module = c.Module()
    module.set_position(bar.position)
    return module

def update_ui(module, data):
    """ Update weather UI """
    if not data:
        module.set_visible(False)
        return
    module.set_label(data['text'])
    module.set_visible(True)
    if not module.get_active():
        module.set_widget(build_popover(data))

def build_popover(cache):
    """ Original Weather widget formatting """
    widget = c.box('v', spacing=20)

    today = cache['Today']['info'][0]
    today_box = c.box('h', spacing=10)

    today_left = c.box('v')
    widget.append(c.label(cache['City'], style="heading"))
    temp = c.label(
        f"{today['temperature']}° {today['icon']}", 'today-weather')
    today_left.append(temp)

    extra = c.box('h', spacing=10)
    for item in [
        f" {today['humidity']}%",
        f" {today['wind']}mph",
    ]:
        extra.append(c.label(item))
    today_left.append(extra)

    today_right = c.box('v')
    for item in [
        today['description'],
        f"Feels like {today['feels_like']}°",
        f"{today['quality']} air quality"
    ]:
        today_right.append(c.label(item, he=True, ha="end"))

    today_box.append(today_left)

    sun_box = c.box('v')
    sun_box.append(c.label(f'{today["sun_icon"]} {today["sun_time"]}'))
    today_box.append(sun_box)

    today_box.append(today_right)
    widget.append(today_box)

    hourly_container = c.box('v', spacing=10)
    hourly_container.append(c.label('Hourly forecast', he=True, ha="start"))
    
    # Add temperature graph
    if 'temperatures' in cache['Hourly']:
        graph_box = c.box('v', style='box')
        graph_box.set_overflow(Gtk.Overflow.HIDDEN)
        graph = c.Graph(
            cache['Hourly']['temperatures'], 
            height=80,
            min_config=cache['Hourly'].get('min'),
            max_config=cache['Hourly'].get('max')
        )
        graph_box.append(graph)
        hourly_container.append(graph_box)
        
        # Time legend for forecast
        time_box = c.box('h')
        time_box.append(c.label('Now', style='gray', ha='start', he=True))
        time_box.append(c.label(f"+{cache['Hourly'].get('hours', 5)}h", style='gray', ha='end'))
        hourly_container.append(time_box)

    hourly_box = c.box('h', style='box')
    hour_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
    for hour in cache['Hourly']['info']:
        hour_box = c.box('v', style='inner-box-wide')
        hour_group.add_widget(hour_box)
        hour_box.append(c.label(f"{hour['temperature']}°"))
        hour_box.append(c.label(f"{hour['humidity']}%"))
        icon = c.label(hour['icon'], style='icon-small')
        icon.props.tooltip_text = hour['description']
        hour_box.append(icon)
        hour_box.append(c.label(hour['time']))
        hourly_box.append(hour_box)
        if hour != cache['Hourly']['info'][-1]:
            hourly_box.append(c.sep('v'))
    hourly_container.append(hourly_box)
    widget.append(hourly_container)

    daily_container = c.box('v', spacing=10)
    daily_container.append(c.label(
        'Daily forecast', style='title', ha='start'))
    daily_box = c.box('v', style='box')
    for day in cache['Daily']['info']:
        day_box = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        day_box.get_style_context().add_class('inner-box')
        day_box.set_start_widget(c.label(day['time']))
        day_box.set_end_widget(c.label(f"{day['high']}° / {day['low']}°"))
        icon = c.label(day['icon'])
        icon.props.tooltip_text = day['description']
        day_box.set_center_widget(icon)

        daily_box.append(day_box)
        if day != cache['Daily']['info'][-1]:
            daily_box.append(c.sep('h'))
    daily_container.append(daily_box)
    widget.append(daily_container)
    return widget
