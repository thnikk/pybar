#!/usr/bin/python3 -u
"""
Description: Newer OpenMeteo weather module that takes a zip code as an
argument instead of in a config file.
Author: thnikk
"""
from datetime import datetime, timedelta
import json
import os
import argparse
import requests
from modules_waybar.common import print_debug, Cache


def parse_args():
    """ Parse arguments """
    parser = argparse.ArgumentParser(
        description="Get weather formatted for waybar")
    parser.add_argument(
        'zip', type=str, help="Zip code")
    parser.add_argument(
        '-n', action='store_true', help="Enable night icons")
    parser.add_argument(
        '-f', type=int, const=5, nargs='?',
        help="How many hours to show in tooltip (default is 5)")
    return parser.parse_args()


class OpenMeteo():  # pylint: disable=too-few-public-methods
    """ Class for OpenMeteo """
    def __init__(self, zip_code):
        """ Initialize class"""
        geo = self.__cache__(
            os.path.expanduser(f"~/.cache/geocode-{zip_code}.json"),
            "https://geocoding-api.open-meteo.com/v1/search",
            {
                "name": zip_code, "count": 1,
                "language": "en", "format": "json"
            },
            zip_code
        )
        self.latitude = geo['results'][0]['latitude']
        self.longitude = geo['results'][0]['longitude']
        self.timezone = geo['results'][0]['timezone']
        self.city = geo['results'][0]['name']
        self.weather = Weather(
            self.latitude, self.longitude, self.timezone, zip_code)
        self.pollution = Pollution(
            self.latitude, self.longitude, self.timezone, zip_code)

    def __cache__(self, path, url, qs, zip_code):
        """ Update cache file if enough time has passed. """
        cache = Cache(path)
        try:
            data = cache.load()
            if str(zip_code) not in data['results'][0]['postcodes']:
                raise ValueError("Updated postcode")
            # print_debug(f"Loading data from cache at {path}.")
        except (FileNotFoundError, ValueError):
            try:
                print_debug("Fetching new geocode data.")
                data = requests.get(url, params=qs, timeout=3).json()
                cache.save(data)
            except requests.exceptions.ConnectionError:
                data = cache.load()
        return data


def lookup(code, mode, night=False):
    """ Get description for weather code """
    weather_lookup = {
        0:  ["", "Clear"],
        1:  ["", "Mostly clear"],
        2:  ["", "Partly cloudy"],
        3:  ["", "Overcast"],
        45: ["", "Fog"],
        48: ["", "Depositing rime fog"],
        51: ["", "Light drizzle"],
        53: ["", "Moderate drizzle"],
        55: ["", "Dense drizzle"],
        56: ["", "Light freezing drizzle"],
        57: ["", "Dense freezing drizzle"],
        61: ["", "Slight rain"],
        63: ["", "Moderate rain"],
        65: ["", "Heavy rain"],
        66: ["", "Light freezing rain"],
        67: ["", "Heavy freezing rain"],
        71: ["", "Slight snow"],
        73: ["", "Moderate snow"],
        75: ["", "Heavy snow"],
        77: ["", "Snow grains"],
        80: ["", "Slight rain showers"],
        81: ["", "Moderate rain showers"],
        82: ["", "Violent rain showers"],
        85: ["", "Slight snow showers"],
        86: ["", "Heavy snow showers"],
        95: ["", "Thunderstorm"],
        96: ["", "Slight hailing thunderstorm"],
        99: ["", "Heavy hailing thunderstorm"]
    }
    if night:
        weather_lookup[0][0] = ""
        weather_lookup[1][0] = ""
        weather_lookup[2][0] = ""
    return weather_lookup[code][mode]


class Weather():  # pylint: disable=too-few-public-methods
    """ Get daily weather data """
    def __init__(self, lat, lon, timezone, zip_code):
        weather = self.__cache__(
            os.path.expanduser(f"~/.cache/weather-{zip_code}.json"),
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": lat, "longitude": lon,
                "hourly": [
                    "temperature_2m", "relativehumidity_2m", "weathercode",
                    "windspeed_10m", "winddirection_10m",
                    "apparent_temperature"
                ],
                "daily": [
                    "weathercode", "temperature_2m_max", "temperature_2m_min",
                    "sunrise,sunset", "wind_speed_10m_max",
                    "wind_direction_10m_dominant"
                ],
                "temperature_unit": "fahrenheit",
                "timezone": timezone,
            },
            timedelta(hours=1)
        )
        self.hourly = Hourly(weather)
        self.daily = Daily(weather)

    def __cache__(self, path, url, qs, delta) -> dict:
        """ Update cache file if enough time has passed. """
        cache = Cache(path)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (datetime.now() - mtime) > delta:
                raise ValueError('old')
            data = cache.load()
            # print_debug(f"Loading data from cache at {path}.")
        except (FileNotFoundError, ValueError):
            try:
                print_debug("Fetching new data.")
                data = requests.get(url, params=qs, timeout=3).json()
                cache.save(data)
            except requests.exceptions.ConnectionError:
                data = cache.load()
        return data


class Hourly():
    """ Parse hourly data and split into objects """
    def __init__(self, weather):
        self.weathercodes = weather['hourly']['weathercode']
        self.temperatures = weather['hourly']['temperature_2m']
        self.feelslikes = weather['hourly']['apparent_temperature']
        self.windspeeds = weather['hourly']['windspeed_10m']
        self.humidities = weather['hourly']['relativehumidity_2m']

    def code(self, index):
        """ Get weathercode """
        return self.weathercodes[index]

    def description(self, index):
        """ Get description """
        return lookup(self.code(index), 1)

    def icon(self, index, night=False):
        """ Get icon """
        return lookup(self.code(index), 0, night)

    def temp(self, index):
        """ Get temperature """
        return round(self.temperatures[index])

    def feelslike(self, index):
        """ Get temperature """
        return round(self.feelslikes[index])

    def wind(self, index):
        """ Get windspeed """
        return self.windspeeds[index]

    def humidity(self, index):
        """ Get humidity """
        return self.humidities[index]


class Daily():
    """ Parse daily data and split into objects """
    def __init__(self, weather):
        self.sunrise = int(datetime.strptime(
            weather["daily"]["sunrise"][0],
            "%Y-%m-%dT%H:%M").strftime("%H"))
        self.sunset = int(datetime.strptime(
            weather["daily"]["sunset"][0],
            "%Y-%m-%dT%H:%M").strftime("%H"))
        self.weathercodes = weather['daily']['weathercode']
        self.lows = weather['daily']['temperature_2m_min']
        self.highs = weather['daily']['temperature_2m_max']
        self.windspeeds = weather['daily']['wind_speed_10m_max']
        self.winddirs = weather['daily']['wind_direction_10m_dominant']

    def code(self, index):
        """ Get weathercode """
        return self.weathercodes[index]

    def description(self, index) -> str:
        """ Get description of weather """
        return lookup(self.code(index), 1)

    def icon(self, index, night=False):
        """ Get icon """
        return lookup(self.code(index), 0, night)

    def low(self, index) -> int:
        """ Get min temperature """
        return round(self.lows[index])

    def high(self, index) -> int:
        """ Get max temperature """
        return round(self.highs[index])

    def wind(self, index) -> int:
        """ Get max wind speed """
        return round(self.windspeeds[index])

    def direction(self, index) -> int:
        """ Get max wind speed """
        return round(self.winddirs[index])


class Pollution():
    """ Get daily polution data """
    def __init__(self, lat, lon, timezone, zip_code) -> None:
        pollution = self.__cache__(
            os.path.expanduser(f"~/.cache/pollution-{zip_code}.json"),
            "https://air-quality-api.open-meteo.com/v1/air-quality",
            {
                "latitude": lat, "longitude": lon, "hourly": "us_aqi",
                "timezone": timezone,
            },
            timedelta(days=1)
        )
        self.aqi = pollution["hourly"]["us_aqi"]

    def __cache__(self, path, url, qs, delta) -> dict:
        """ Update cache file if enough time has passed. """
        cache = Cache(path)
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if (datetime.now() - mtime) > delta:
                raise ValueError('old')
            data = cache.load()
            # print_debug(f"Loading data from cache at {path}.")
        except (FileNotFoundError, ValueError):
            try:
                print_debug("Fetching new data.")
                data = requests.get(url, params=qs, timeout=3).json()
                cache.save(data)
            except requests.exceptions.ConnectionError:
                data = cache.load()
        return data

    def __aqi_to_desc__(self, value) -> str:
        """ Get description for aqi """
        for desc in [
            (50, "Good"), (100, "Moderate"), (150, "Unhealthy"),
            (200, "Unhealthy"), (300, "Very unhealthy"), (500, "Hazardous")
        ]:
            if 0 < value < desc[0]:
                return desc[1]
        return "Unknown"

    def description(self, index) -> str:
        """ Get air quality description for given hour """
        return self.__aqi_to_desc__(self.aqi[index])


def widget(om, index, hours, night, min_val=None, max_val=None) -> dict:
    """ Generate tooltip """

    hourly = om.weather.hourly
    night_now = (
        om.weather.daily.sunrise > datetime.now().hour
        or datetime.now().hour > om.weather.daily.sunset) and night
    output = {
        "City": om.city,
        "Today": {
            "icon-class": "icon-large",
            "info": [{
                "icon": hourly.icon(index, night_now),
                "description": hourly.description(index),
                "temperature": hourly.temp(index),
                "feels_like": hourly.feelslike(index),
                "humidity": hourly.humidity(index),
                "wind": hourly.wind(index),
                "quality": om.pollution.description(index)
            }]
        },
        "Hourly": {
            "icon-class": "icon-small",
            "temperatures": [hourly.temp(int((datetime.now() + timedelta(hours=h)).strftime('%H'))) for h in range((hours or 5) + 1)],
            "hours": hours or 5,
            "min": min_val,
            "max": max_val
        },
        "Daily": {
            "icon-class": "icon-medium"
        }
    }

    if om.weather.daily.sunset > index > om.weather.daily.sunrise:
        output["Today"]["info"][0]["sunset"] = om.weather.daily.sunset - 12
    else:
        output["Today"]["info"][0]["sunrise"] = om.weather.daily.sunrise

    hourly_output = []
    for hour in range(1, (hours or 5) + 1):
        hour_index = int(
            (datetime.now() + timedelta(hours=hour)).strftime('%H'))
        text = (datetime.now() + timedelta(hours=hour)).strftime("%l%P")
        night_hour = (
            om.weather.daily.sunrise > hour_index
            or hour_index > om.weather.daily.sunset) and night
        hourly_output.append({
            "icon": om.weather.hourly.icon(hour_index, night_hour),
            "description": om.weather.hourly.description(hour_index),
            "humidity": om.weather.hourly.humidity(hour_index),
            "time": text,
            "temperature": om.weather.hourly.temp(hour_index)
        })
    output["Hourly"]["info"] = hourly_output

    daily_output = []
    for day in range(0, 5):
        abbr = (datetime.now() + timedelta(days=day)).strftime('%A')
        daily_output.append({
            "time": abbr,
            "high": om.weather.daily.high(day),
            "low": om.weather.daily.low(day),
            "wind": om.weather.daily.wind(day),
            "description": om.weather.daily.description(day),
            "icon": om.weather.daily.icon(day)
        })
    output["Daily"]["info"] = daily_output
    with open(
        os.path.expanduser('~/.cache/weather-widget.json'),
        'w', encoding='utf-8'
    ) as file:
        file.write(json.dumps(output, indent=4))
    return output


def module(config):
    """ Main function """
    if 'zip_code' not in list(config):
        config['zip_code'] = "94102"
    if 'night_icons' not in list(config):
        config['night_icons'] = True
    if 'hours' not in list(config):
        config['hours'] = 5

    om = OpenMeteo(config['zip_code'])
    now = datetime.now()
    hour_now = int(now.strftime('%H'))
    night = (
        om.weather.daily.sunrise > hour_now
        or hour_now > om.weather.daily.sunset) and config['night_icons']

    return {
            "text": f"{om.weather.hourly.icon(hour_now, night)} "
            f"{om.weather.hourly.temp(hour_now)}°F",
            "widget": widget(
                om, hour_now, config['hours'], config['night_icons'],
                config.get('min'), config.get('max'))
        }


def main():
    """ Main function """
    args = parse_args()
    print(json.dumps(
        module({"zip_code": args.zip, "night_icons": args.n, "hours": args.f})
    ))


if __name__ == "__main__":
    main()
