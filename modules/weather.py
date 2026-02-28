#!/usr/bin/python3 -u
"""
Description: Weather module with detailed widget showing hourly and weekly
    forecasts.
Author: thnikk
"""
from datetime import datetime, timedelta
import weakref
import requests
import common as c
import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa


class Weather(c.BaseModule):
    DEFAULT_INTERVAL = 300
    STALE_INTERVAL = 600

    SCHEMA = {
        'zip_code': {
            'type': 'string',
            'default': '94102',
            'label': 'ZIP Code / City',
            'description':
                'Location for weather lookup (ZIP code or city name)'
        },
        'night_icons': {
            'type': 'boolean',
            'default': True,
            'label': 'Night Icons',
            'description': 'Use moon icons after sunset'
        },
        'interval': {
            'type': 'integer',
            'default': 300,
            'label': 'Update Interval',
            'description': 'Seconds between weather updates',
            'min': 60,
            'max': 3600
        },
        'min': {
            'type': 'integer',
            'default': None,
            'label': 'Graph Min Temp',
            'description': 'Minimum temperature on graph (auto if empty)'
        },
        'max': {
            'type': 'integer',
            'default': None,
            'label': 'Graph Max Temp',
            'description': 'Maximum temperature on graph (auto if empty)'
        }
    }

    def lookup(self, code, mode, night=False):
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

    def aqi_to_desc(self, value) -> str:
        """ Get description for aqi """
        for desc in [
            (50, "Good"), (100, "Moderate"), (150, "Unhealthy"),
            (200, "Unhealthy"), (300, "Very unhealthy"), (500, "Hazardous")
        ]:
            if 0 < value < desc[0]:
                return desc[1]
        return "Unknown"

    def time_to_text(self, time_string) -> str:
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

    def _get_session(self):
        # Reuse a single session to avoid accumulating connections.
        if not hasattr(self, '_session') or self._session is None:
            self._session = requests.Session()
        return self._session

    def fetch_data(self):
        """ Fetch weather data from OpenMeteo """
        zip_code = self.config.get('zip_code', "94102")
        night_icons = self.config.get('night_icons', True)
        hours_to_show = 24
        session = self._get_session()

        try:
            # Geocode
            with session.get(
                "https://geocoding-api.open-meteo.com/v1/search", params={
                    "name": zip_code, "count": 1,
                    "language": "en", "format": "json"
                }, timeout=5
            ) as _r:
                geo = _r.json()

            if not geo.get('results'):
                return {}

            res = geo['results'][0]
            lat, lon, tz, city = res['latitude'], res['longitude'], \
                res['timezone'], res['name']

            # Weather
            with session.get(
                "https://api.open-meteo.com/v1/forecast", params={
                    "latitude": lat, "longitude": lon,
                    "temperature_unit": "fahrenheit", "timezone": tz,
                    "hourly": [
                        "temperature_2m", "relativehumidity_2m",
                        "weathercode", "apparent_temperature",
                        "windspeed_10m"],
                    "daily": [
                        "weathercode", "temperature_2m_max",
                        "temperature_2m_min", "sunrise", "sunset",
                        "wind_speed_10m_max"]
                }, timeout=5
            ) as _r:
                w = _r.json()

            # Pollution
            with session.get(
                "https://air-quality-api.open-meteo.com/v1/air-quality",
                params={
                    "latitude": lat, "longitude": lon,
                    "hourly": "us_aqi", "timezone": tz
                }, timeout=5
            ) as _r:
                p = _r.json()

            now = datetime.now()
            hour_now = now.hour

            sunrise_dt = datetime.strptime(
                w["daily"]["sunrise"][0], "%Y-%m-%dT%H:%M")
            sunset_dt = datetime.strptime(
                w["daily"]["sunset"][0], "%Y-%m-%dT%H:%M")
            sunrise = sunrise_dt.hour
            sunset = sunset_dt.hour

            is_night = (hour_now < sunrise or hour_now > sunset) and \
                night_icons

            # Process Today data
            today_data = {
                "icon": self.lookup(
                    w['hourly']['weathercode'][hour_now], 0, is_night),
                "description": self.lookup(
                    w['hourly']['weathercode'][hour_now], 1),
                "temperature": round(w['hourly']['temperature_2m'][hour_now]),
                "feels_like": round(
                    w['hourly']['apparent_temperature'][hour_now]),
                "humidity": w['hourly']['relativehumidity_2m'][hour_now],
                "wind": round(w['hourly']['windspeed_10m'][hour_now]),
                "quality": self.aqi_to_desc(p['hourly']['us_aqi'][hour_now]),
                "sunrise": sunrise_dt.strftime("%l %p").strip(),
                "sunset": sunset_dt.strftime("%l %p").strip()
            }
            today_data["sun_icon"] = "" if sunset > hour_now > sunrise \
                else ""
            today_data["sun_time"] = today_data["sunset"] \
                if sunset > hour_now > sunrise else today_data["sunrise"]

            # Process Hourly data
            hourly_info = []
            for h in range(1, hours_to_show + 1):
                target_time = now + timedelta(hours=h)
                idx = hour_now + h
                h_idx = target_time.hour
                h_night = (h_idx < sunrise or h_idx > sunset) and night_icons
                hourly_info.append({
                    "icon": self.lookup(
                        w['hourly']['weathercode'][idx], 0, h_night),
                    "description": self.lookup(
                        w['hourly']['weathercode'][idx], 1),
                    "humidity": w['hourly']['relativehumidity_2m'][idx],
                    "time": target_time.strftime("%l%P").strip(),
                    "temperature": round(w['hourly']['temperature_2m'][idx])
                })

            # Process Daily data
            daily_info = []
            for d in range(0, 5):
                target_day = now + timedelta(days=d)
                daily_info.append({
                    "time": target_day.strftime('%A'),
                    "high": round(w['daily']['temperature_2m_max'][d]),
                    "low": round(w['daily']['temperature_2m_min'][d]),
                    "wind": round(w['daily']['wind_speed_10m_max'][d]),
                    "description": self.lookup(
                        w['daily']['weathercode'][d], 1),
                    "icon": self.lookup(w['daily']['weathercode'][d], 0)
                })

            return {
                "City": city,
                "Today": {"info": [today_data]},
                "Hourly": {
                    "info": hourly_info,
                    "temperatures": [
                        round(w['hourly']['temperature_2m'][now.hour + h])
                        for h in range(hours_to_show + 1)],
                    "humidities": [
                        round(
                            w['hourly']['relativehumidity_2m'][now.hour + h])
                        for h in range(hours_to_show + 1)],
                    "hours": hours_to_show,
                    "min": self.config.get('min'),
                    "max": self.config.get('max')
                },
                "Daily": {"info": daily_info},
                "icon": today_data['icon'],
                "text": f"{today_data['temperature']}°F"
            }
        except Exception as e:
            c.print_debug(f"Weather fetch failed: {e}", color='red')
            return {}

    def build_popover(self, widget_obj, data):
        """ Original Weather widget formatting """
        widget_obj.popover_widgets = {'today': {}, 'hourly': [], 'daily': []}

        widget = c.box('v', spacing=20)

        today = data['Today']['info'][0]
        today_box = c.box('h', spacing=10)

        today_left = c.box('v')
        city_lbl = c.label(data['City'], style="heading")
        widget.append(city_lbl)
        widget_obj.popover_widgets['city'] = city_lbl

        temp = c.label(
            f"{today['temperature']}° {today['icon']}", 'today-weather')
        today_left.append(temp)
        widget_obj.popover_widgets['today']['temp'] = temp

        extra = c.box('h', spacing=10)

        hum_lbl = c.label(f" {today['humidity']}%")
        extra.append(hum_lbl)
        widget_obj.popover_widgets['today']['hum'] = hum_lbl

        wind_lbl = c.label(f" {today['wind']}mph")
        extra.append(wind_lbl)
        widget_obj.popover_widgets['today']['wind'] = wind_lbl

        today_left.append(extra)

        today_right = c.box('v')

        desc_lbl = c.label(today['description'], he=True, ha="end")
        today_right.append(desc_lbl)
        widget_obj.popover_widgets['today']['desc'] = desc_lbl

        feels_lbl = c.label(
            f"Feels like {today['feels_like']}°", he=True, ha="end")
        today_right.append(feels_lbl)
        widget_obj.popover_widgets['today']['feels'] = feels_lbl

        aqi_lbl = c.label(f"{today['quality']} air quality", he=True, ha="end")
        today_right.append(aqi_lbl)
        widget_obj.popover_widgets['today']['aqi'] = aqi_lbl

        today_box.append(today_left)

        sun_box = c.box('v')
        sun_lbl = c.label(f'{today["sun_icon"]} {today["sun_time"]}')
        sun_box.append(sun_lbl)
        widget_obj.popover_widgets['today']['sun'] = sun_lbl

        today_box.append(sun_box)

        today_box.append(today_right)
        widget.append(today_box)

        hourly_container = c.box('v', spacing=10)
        hourly_container.append(
            c.label('Hourly forecast', he=True, ha="start"))

        # Add temperature graph
        if 'temperatures' in data['Hourly']:
            graph_box = c.box('v', style='box')
            graph_box.set_overflow(Gtk.Overflow.HIDDEN)

            # Calculate time markers for sunrise and sunset
            now = datetime.now()
            current_hour = now.hour
            hours_to_show = data['Hourly'].get('hours', 24)

            time_markers_data = []

            # Get sunrise and sunset times from today's data
            sunrise_time = today['sunrise']  # Format: "6:30 AM"
            sunset_time = today['sunset']    # Format: "7:45 PM"

            def time_to_hours(time_str):
                """Convert time string to hours since midnight"""
                try:
                    time_part, period = time_str.strip().split()
                    hour_min = time_part.split(':')
                    hour = int(hour_min[0])
                    minute = int(hour_min[1]) if len(hour_min) > 1 else 0

                    if period.upper() == 'PM' and hour != 12:
                        hour += 12
                    elif period.upper() == 'AM' and hour == 12:
                        hour = 0

                    return hour + minute / 60
                except (ValueError, IndexError):
                    return None

            sunrise_hours = time_to_hours(sunrise_time)
            sunset_hours = time_to_hours(sunset_time)

            # Calculate sunrise position within forecast window
            if sunrise_hours is not None:
                sunrise_offset = (sunrise_hours - current_hour) % 24
                if 0 < sunrise_offset <= hours_to_show:
                    time_markers_data.append(
                        (sunrise_offset, "Sunrise", sunrise_hours))

            # Calculate sunset position within forecast window
            if sunset_hours is not None:
                sunset_offset = (sunset_hours - current_hour) % 24
                if 0 < sunset_offset <= hours_to_show:
                    time_markers_data.append(
                        (sunset_offset, "Sunset", sunset_hours))

            # Sort by absolute time
            time_markers_data.sort(key=lambda x: x[2])

            # Separate into parallel arrays
            time_markers = [marker[0] for marker in time_markers_data]
            time_labels = [marker[1] for marker in time_markers_data]

            hover_labels = [
                f"{t}° {l}\n{hu}% humidity" for t, hu, l in zip(
                    data['Hourly']['temperatures'],
                    data['Hourly']['humidities'],
                    ["Now"] + [h['time'] for h in data['Hourly']['info']]
                )
            ]

            graph = c.Graph(
                data['Hourly']['temperatures'],
                height=80,
                min_config=data['Hourly'].get('min'),
                max_config=data['Hourly'].get('max'),
                time_markers=time_markers,
                time_labels=time_labels,
                hover_labels=hover_labels,
                smooth=True,
                secondary_data=data['Hourly']['humidities']
            )
            graph_box.append(graph)
            hourly_container.append(graph_box)
            widget_obj.popover_widgets['graph'] = graph

            # Time legend for forecast
            time_box = c.box('h')
            time_box.append(c.label('Now', style='gray', ha='start', he=True))
            hours_lbl = c.label(
                f"+{data['Hourly'].get('hours', 5)}h", style='gray', ha='end')
            time_box.append(hours_lbl)
            hourly_container.append(time_box)

        hourly_box = c.box('h')
        hour_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        for hour in data['Hourly']['info']:
            hour_box = c.box('v', style='inner-box')
            hour_group.add_widget(hour_box)

            h_widgets = {}
            t_lbl = c.label(f"{hour['temperature']}°")
            hour_box.append(t_lbl)
            h_widgets['temp'] = t_lbl

            h_lbl = c.label(f"{hour['humidity']}%")
            hour_box.append(h_lbl)
            h_widgets['hum'] = h_lbl

            icon = c.label(hour['icon'], style='icon-small')
            hour_box.append(icon)
            h_widgets['icon'] = icon
            h_widgets['description'] = hour['description']
            c.set_hover_popover(
                icon, lambda w=h_widgets: w['description'])

            time_lbl = c.label(hour['time'])
            hour_box.append(time_lbl)
            h_widgets['time'] = time_lbl

            hourly_box.append(hour_box)
            if hour != data['Hourly']['info'][-1]:
                hourly_box.append(c.sep('v'))

            widget_obj.popover_widgets['hourly'].append(h_widgets)

        hourly_scroll_wrapper = c.HScrollGradientBox(
            hourly_box, max_width=400)
        c.add_style(hourly_scroll_wrapper, 'box')

        # Convert vertical scroll to horizontal scroll
        scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)

        def on_scroll(_, _dx, dy):
            hourly_scroll_wrapper.scroll_by(dy * 50)
            return True

        scroll_controller.connect("scroll", on_scroll)
        hourly_scroll_wrapper._scroll.add_controller(scroll_controller)
        hourly_container.append(hourly_scroll_wrapper)
        widget.append(hourly_container)

        daily_container = c.box('v', spacing=10)
        daily_container.append(c.label(
            'Daily forecast', style='title', ha='start'))
        daily_box = c.box('v', style='box')
        day_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        icon_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        wind_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)
        hl_group = Gtk.SizeGroup.new(Gtk.SizeGroupMode.HORIZONTAL)

        for day in data['Daily']['info']:
            day_box = c.box('h', spacing=10)
            day_box.get_style_context().add_class('inner-box')

            d_widgets = {}

            # 1. Day
            time_lbl = c.label(day['time'], ha='start')
            time_lbl.set_xalign(0.0)
            day_group.add_widget(time_lbl)
            day_box.append(time_lbl)
            d_widgets['time'] = time_lbl

            # 2. Icon
            icon = c.label(day['icon'], ha='center', he=True)
            icon_group.add_widget(icon)
            day_box.append(icon)
            d_widgets['icon'] = icon
            d_widgets['description'] = day['description']
            c.set_hover_popover(
                icon, lambda w=d_widgets: w['description'])

            # 3. Wind
            wind_lbl = c.label(
                f" {day.get('wind', 0)}mph", style="gray", ha='center', he=True)
            wind_group.add_widget(wind_lbl)
            day_box.append(wind_lbl)
            d_widgets['wind'] = wind_lbl

            # 4. HL
            hl_lbl = c.label(f"{day['high']}° / {day['low']}°", ha='end')
            hl_lbl.set_xalign(1.0)
            hl_group.add_widget(hl_lbl)
            day_box.append(hl_lbl)
            d_widgets['hl'] = hl_lbl

            daily_box.append(day_box)
            if day != data['Daily']['info'][-1]:
                daily_box.append(c.sep('h'))

            widget_obj.popover_widgets['daily'].append(d_widgets)

        daily_container.append(daily_box)
        widget.append(daily_container)
        return widget

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)

        widget_ref = weakref.ref(m)

        def update_callback(data):
            widget = widget_ref()
            if widget is not None:
                self.update_ui(widget, data)

        sub_id = c.state_manager.subscribe(self.name, update_callback)
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            widget.set_visible(False)
            return
        widget.set_icon(data.get('icon', ''))
        widget.set_label(data.get('text', ''))
        widget.set_visible(True)
        if data.get('stale'):
            c.add_style(widget, 'stale')

        # Fingerprint with lightweight scalars to avoid storing a full
        # copy of the weather payload (hourly/daily arrays) on the widget.
        today_info = data.get('Today', {}).get('info', [{}])[0]
        hourly = data.get('Hourly', {})
        fingerprint = (
            data.get('City'),
            today_info.get('temperature'),
            today_info.get('description'),
            len(hourly.get('info', [])),
            hourly.get('temperatures', [None])[-1]
        )
        if (widget.get_popover() and
                getattr(widget, '_popover_fingerprint', None) == fingerprint):
            return

        widget._popover_fingerprint = fingerprint

        needs_rebuild = False
        if not widget.get_popover() or not hasattr(widget, 'popover_widgets'):
            needs_rebuild = True
        elif len(widget.popover_widgets['hourly']) !=\
                len(data['Hourly']['info']):
            needs_rebuild = True
        elif len(widget.popover_widgets['daily']) !=\
                len(data['Daily']['info']):
            needs_rebuild = True

        if needs_rebuild:
            widget.set_widget(self.build_popover(widget, data))
        else:
            # Update Today
            today = data['Today']['info'][0]
            w = widget.popover_widgets
            w['city'].set_text(data['City'])
            w['today']['temp'].set_text(
                f"{today['temperature']}° {today['icon']}")
            w['today']['hum'].set_text(f" {today['humidity']}%")
            w['today']['wind'].set_text(f" {today['wind']}mph")
            w['today']['desc'].set_text(today['description'])
            w['today']['feels'].set_text(f"Feels like {today['feels_like']}°")
            w['today']['aqi'].set_text(f"{today['quality']} air quality")
            w['today']['sun'].set_text(
                f'{today["sun_icon"]} {today["sun_time"]}')

            # Update Hourly
            for i, h_widgets in enumerate(w['hourly']):
                if i < len(data['Hourly']['info']):
                    h_data = data['Hourly']['info'][i]
                    h_widgets['temp'].set_text(f"{h_data['temperature']}°")
                    h_widgets['hum'].set_text(f"{h_data['humidity']}%")
                    h_widgets['icon'].set_text(h_data['icon'])
                    h_widgets['description'] = h_data['description']
                    h_widgets['time'].set_text(h_data['time'])

            # Update Daily
            for i, d_widgets in enumerate(w['daily']):
                if i < len(data['Daily']['info']):
                    d_data = data['Daily']['info'][i]
                    d_widgets['time'].set_text(d_data['time'])
                    d_widgets['hl'].set_text(
                        f"{d_data['high']}° / {d_data['low']}°")
                    if 'wind' in d_widgets:
                        d_widgets['wind'].set_text(
                            f" {d_data.get('wind', 0)}mph")
                    d_widgets['icon'].set_text(d_data['icon'])
                    d_widgets['description'] = d_data['description']

            # Update Graph
            if 'graph' in w:
                # Recalculate markers (logic duplicated from build_popover)
                now = datetime.now()
                current_hour = now.hour
                hours_to_show = data['Hourly'].get('hours', 24)
                time_markers_data = []
                sunrise_time = today['sunrise']
                sunset_time = today['sunset']

                def time_to_hours(time_str):
                    try:
                        time_part, period = time_str.strip().split()
                        hour_min = time_part.split(':')
                        hour = int(hour_min[0])
                        minute = int(hour_min[1]) if len(hour_min) > 1 else 0
                        if period.upper() == 'PM' and hour != 12:
                            hour += 12
                        elif period.upper() == 'AM' and hour == 12:
                            hour = 0
                        return hour + minute / 60
                    except (ValueError, IndexError):
                        return None

                sunrise_hours = time_to_hours(sunrise_time)
                sunset_hours = time_to_hours(sunset_time)
                if sunrise_hours is not None:
                    sunrise_offset = (sunrise_hours - current_hour) % 24
                    if 0 < sunrise_offset <= hours_to_show:
                        time_markers_data.append(
                            (sunrise_offset, "Sunrise", sunrise_hours))
                if sunset_hours is not None:
                    sunset_offset = (sunset_hours - current_hour) % 24
                    if 0 < sunset_offset <= hours_to_show:
                        time_markers_data.append(
                            (sunset_offset, "Sunset", sunset_hours))

                time_markers_data.sort(key=lambda x: x[2])

                w['graph'].update_data(
                    data['Hourly']['temperatures'], None)
                w['graph'].secondary_data = data['Hourly']['humidities']
                w['graph'].time_markers = [m[0] for m in time_markers_data]
                w['graph'].time_labels = [m[1] for m in time_markers_data]
                w['graph'].hover_labels = [
                    f"{t}° {l}\n{hu}% humidity" for t, hu, l in zip(
                        data['Hourly']['temperatures'],
                        data['Hourly']['humidities'],
                        ["Now"] + [h['time'] for h in data['Hourly']['info']]
                    )
                ]


module_map = {
    'weather': Weather
}
