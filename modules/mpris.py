#!/usr/bin/python3 -u
"""
Description: MPRIS module for unified state with album art
Author: thnikk
"""
import common as c
import os
import hashlib
import requests
import time
from dasbus.connection import SessionMessageBus
from dasbus.client.observer import DBusObserver
from dasbus.client.proxy import disconnect_proxy
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf, GLib  # noqa

CACHE_DIR = os.path.expanduser('~/.cache/pybar')


def unwrap(val):
    if hasattr(val, 'unpack'):
        val = val.unpack()
    if hasattr(val, 'value'):
        val = val.value

    if isinstance(val, dict):
        return {k: unwrap(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [unwrap(v) for v in val]
    return val


def format_time(microseconds):
    """ Format microseconds to MM:SS or HH:MM:SS """
    seconds = int(microseconds / 1000000)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class MPRIS(c.BaseModule):
    SCHEMA = {
        'players': {
            'type': 'list',
            'default': [],
            'label': 'Players',
            'description': 'List of player names to show.'
                           'Empty for any player.'
        },
        'art_size': {
            'type': 'integer',
            'default': 300,
            'label': 'Album Art Size',
            'description': 'Size of album art in popover (pixels)',
            'min': 100,
            'max': 500
        },
        'show_title': {
            'type': 'boolean',
            'default': True,
            'label': 'Show Title',
            'description': 'Show song title in the bar'
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        # Handle both string (single player) and list (multiple players)
        players = config.get('players', config.get('player', []))
        if isinstance(players, str):
            players = [players]
        self.target_players = [p.lower() for p in players]
        self.bus = SessionMessageBus()
        self.active_player_bus_name = None
        self.active_player_proxy = None
        self.active_player_props_proxy = None
        self.player_observer = None
        self.last_used_player = None
        self.art_size = config.get('art_size', 300)
        self.show_title = config.get('show_title', True)

    def find_player(self):
        """ Find a player matching the config """
        try:
            names = self.bus.proxy.ListNames()
            mpris_players = [n for n in names if n.startswith(
                'org.mpris.MediaPlayer2.')]

            if not mpris_players:
                return None

            if self.target_players:
                # Check each target in order of priority
                for target in self.target_players:
                    for p in mpris_players:
                        if target in p.lower():
                            return p
                return None

            # No targets specified: use last used player or first available
            # First, check if any player is playing
            for p in mpris_players:
                try:
                    proxy = self.bus.get_proxy(p, '/org/mpris/MediaPlayer2')
                    status = unwrap(proxy.PlaybackStatus)
                    if status == 'Playing':
                        self.last_used_player = p
                        return p
                except Exception:
                    continue

            # If none are playing, use last used player if it's still alive
            if self.last_used_player in mpris_players:
                return self.last_used_player

            # Otherwise pick the first one
            self.last_used_player = mpris_players[0]
            return mpris_players[0]
        except Exception as e:
            c.print_debug(f"MPRIS find_player error: {e}", color='red')
            return None

    def setup_player(self, bus_name):
        """ Setup proxies and signals for a player """
        if self.active_player_proxy:
            disconnect_proxy(self.active_player_proxy)
        if self.active_player_props_proxy:
            disconnect_proxy(self.active_player_props_proxy)

        self.active_player_bus_name = bus_name
        if not bus_name:
            self.active_player_proxy = None
            self.active_player_props_proxy = None
            return

        try:
            self.active_player_proxy = self.bus.get_proxy(
                bus_name, '/org/mpris/MediaPlayer2')
            self.active_player_props_proxy = self.bus.get_proxy(
                bus_name, '/org/mpris/MediaPlayer2',
                interface_name='org.freedesktop.DBus.Properties'
            )

            # Connect to PropertiesChanged signal
            self.active_player_props_proxy.PropertiesChanged.connect(
                self.on_properties_changed)

            c.print_debug(f"MPRIS: Connected to {bus_name}", color='green')
        except Exception as e:
            c.print_debug(f"MPRIS setup_player error: {e}", color='red')
            self.active_player_proxy = None
            self.active_player_props_proxy = None

    def on_properties_changed(
            self, interface, changed_props, invalidated_props):
        """ Handle MPRIS property changes """
        if interface == 'org.mpris.MediaPlayer2.Player':
            self.update_state()

    def update_state(self):
        """ Fetch current state and update state manager """
        data = self.get_mpris_status()
        if data:
            c.state_manager.update(self.name, data)
        else:
            c.state_manager.update(self.name, {})

    def get_mpris_status(self):
        if not self.active_player_proxy:
            return None

        try:
            status = unwrap(self.active_player_proxy.PlaybackStatus)
            if not status:
                return None
            status = str(status).lower()

            metadata = unwrap(self.active_player_proxy.Metadata)
            if not isinstance(metadata, dict):
                metadata = {}

            title = str(metadata.get('xesam:title', 'Unknown Song'))
            artists = metadata.get('xesam:artist', [])
            artist = ""
            if isinstance(artists, list) and artists:
                artist = str(artists[0])
            elif isinstance(artists, str):
                artist = artists

            art_url = metadata.get('mpris:artUrl', '')
            if art_url:
                art_url = str(art_url)
            art_path = self.get_art_path(art_url)

            length = metadata.get('mpris:length', 0)
            if not isinstance(length, (int, float)):
                length = 0

            position = 0
            try:
                position = unwrap(self.active_player_proxy.Position)
                if not isinstance(position, (int, float)):
                    position = 0
            except Exception:
                pass

            percent = 0
            if length > 0:
                percent = int((position / length) * 100)

            volume = 0
            try:
                volume = int(unwrap(self.active_player_proxy.Volume) * 100)
            except Exception:
                pass

            return {
                "status": status,
                "song": title,
                "artist": artist,
                "art": art_path,
                "percent": percent,
                "volume": volume,
                "position_str": format_time(position),
                "length_str": format_time(length),
                "text": title,
                "player": self.active_player_bus_name
            }
        except Exception as e:
            c.print_debug(f"MPRIS get_status error: {e}", color='red')
            # Player might have disappeared
            self.active_player_bus_name = None
            self.active_player_proxy = None
            return None

    def get_art_path(self, art_url):
        if not art_url:
            return None

        if art_url.startswith('file://'):
            return art_url[7:]

        if art_url.startswith('http'):
            if not os.path.exists(CACHE_DIR):
                os.makedirs(CACHE_DIR, exist_ok=True)

            art_filename = \
                f"mpris_{hashlib.md5(art_url.encode()).hexdigest()}.jpg"
            art_path = os.path.join(CACHE_DIR, art_filename)

            if not os.path.exists(art_path):
                try:
                    # Clear old mpris art files
                    for f in os.listdir(CACHE_DIR):
                        if f.startswith('mpris_') and f.endswith('.jpg'):
                            os.remove(os.path.join(CACHE_DIR, f))

                    response = requests.get(art_url, timeout=5)
                    if response.status_code == 200:
                        with open(art_path, 'wb') as f:
                            f.write(response.content)
                    else:
                        return None
                except Exception:
                    return None
            return art_path

        return None

    def fetch_data(self):
        return self.get_mpris_status()

    def run_worker(self):
        """ Background worker for mpris """
        def on_name_owner_changed(name, old_owner, new_owner):
            if name.startswith('org.mpris.MediaPlayer2.'):
                # Re-evaluate best player when player names change
                player = self.find_player()
                if player != self.active_player_bus_name:
                    self.setup_player(player)
                    self.update_state()

        try:
            # Listen for players appearing/disappearing
            dbus_proxy = self.bus.get_proxy(
                'org.freedesktop.DBus', '/org/freedesktop/DBus')
            dbus_proxy.NameOwnerChanged.connect(on_name_owner_changed)
        except Exception as e:
            c.print_debug(f"MPRIS: Failed to connect to DBus signals: {e}",
                          color='red')

        player = self.find_player()
        self.setup_player(player)
        self.update_state()

        while True:
            try:
                # Periodic check for best player
                best_player = self.find_player()
                if best_player != self.active_player_bus_name:
                    self.setup_player(best_player)
                    self.update_state()

                if self.active_player_proxy:
                    # Periodically check position for seekbar if playing
                    status = unwrap(self.active_player_proxy.PlaybackStatus)
                    if status == 'Playing':
                        self.update_state()
            except Exception:
                pass
            time.sleep(1)

    def update_popover_widgets(self, widget, data):
        """ Update existing popover widgets """
        # Update Art
        art_path = data.get('art')
        last_art = getattr(widget, 'last_art_path', None)

        if hasattr(widget, 'pop_art') and art_path != last_art:
            widget.last_art_path = art_path
            if art_path and os.path.exists(art_path):
                try:
                    art_size = self.art_size
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        art_path, art_size, art_size, True)
                    texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                    widget.pop_art.set_from_paintable(texture)
                    widget.pop_art.set_visible(True)
                    if hasattr(widget, 'pop_art_placeholder'):
                        widget.pop_art_placeholder.set_visible(False)
                except Exception:
                    pass
            else:
                widget.pop_art.set_visible(False)
                if hasattr(widget, 'pop_art_placeholder'):
                    widget.pop_art_placeholder.set_visible(True)

        # Update labels
        player_name = data.get('player', '').strip(
                'org.mpris.MediaPlayer2.').split('.')[0].capitalize()
        if hasattr(widget, 'pop_player_name') and \
                widget.pop_player_name.get_text() != player_name:
            widget.pop_player_name.set_text(player_name)

        song = data.get('song', 'Unknown Song')
        artist = data.get('artist', '')

        if hasattr(widget, 'pop_song') and widget.pop_song.get_text() != song:
            widget.pop_song.set_text(song)
        if hasattr(widget, 'pop_artist'):
            if widget.pop_artist.get_text() != artist:
                widget.pop_artist.set_text(artist)
            widget.pop_artist.set_visible(bool(artist))

        # Update seekbar
        if hasattr(widget, 'pop_seekbar'):
            widget.pop_seekbar.handler_block(widget.pop_seekbar_handler)
            widget.pop_seekbar.set_value(data.get('percent', 0))
            widget.pop_seekbar.handler_unblock(widget.pop_seekbar_handler)

        if hasattr(widget, 'pop_time'):
            pos = data.get('position_str', '00:00')
            length = data.get('length_str', '00:00')
            widget.pop_time.set_text(f"{pos} / {length}")

        # Update volume bar
        if hasattr(widget, 'pop_volume'):
            widget.pop_volume.handler_block(widget.pop_volume_handler)
            widget.pop_volume.set_value(data.get('volume', 0))
            widget.pop_volume.handler_unblock(widget.pop_volume_handler)

        # Update play/pause button
        if hasattr(widget, 'pop_play_btn'):
            label = '' if data.get('status') == 'playing' else ''
            if widget.pop_play_btn.get_label() != label:
                widget.pop_play_btn.set_label(label)

    def build_popover(self, widget, data):
        """ Build mpris popover """
        main_box = c.box('v', spacing=10, style='small-widget')

        # Player Name at the very top
        player_name = data.get('player', '').split('.')[-1].capitalize()
        widget.pop_player_name = c.label(player_name, style='heading')
        main_box.append(widget.pop_player_name)

        art_size = self.art_size
        art_path = data.get('art')

        # Album Art Container
        art_container = c.box('v', style='cover-art')
        art_container.set_size_request(art_size, art_size)
        art_container.set_overflow(Gtk.Overflow.HIDDEN)
        art_container.set_halign(Gtk.Align.CENTER)
        art_container.set_valign(Gtk.Align.CENTER)
        art_container.set_hexpand(False)
        art_container.set_vexpand(False)

        # Art Image
        widget.pop_art = Gtk.Image()
        widget.pop_art.set_pixel_size(art_size)

        # Placeholder
        widget.pop_art_placeholder = c.label(
            '', style='large-text', va='center', ha='center', he=True)
        widget.pop_art_placeholder.set_size_request(art_size, art_size)

        art_container.append(widget.pop_art)
        art_container.append(widget.pop_art_placeholder)
        main_box.append(art_container)

        # Initial art load
        if art_path and os.path.exists(art_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    art_path, art_size, art_size, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                widget.pop_art.set_from_paintable(texture)
                widget.pop_art_placeholder.set_visible(False)
            except Exception:
                widget.pop_art.set_visible(False)
        else:
            widget.pop_art.set_visible(False)

        # Content box for everything under artwork
        content_box = c.box('v', spacing=10, style='music-box')

        # Track info
        widget.pop_song = c.label(
            data.get('song', 'Unknown Song'),
            length=art_size // 15, style='title')
        widget.pop_artist = c.label(
                data.get('artist', ''), style='artist',
                wrap=art_size // 15)
        widget.pop_artist.set_visible(bool(data.get('artist')))

        content_box.append(widget.pop_song)
        content_box.append(widget.pop_artist)

        seek_box = c.box('v')
        # Seekbar
        widget.pop_seekbar = c.slider(data.get('percent', 0), scrollable=False)

        def on_seek(s):
            if self.active_player_proxy:
                try:
                    metadata = unwrap(self.active_player_proxy.Metadata)
                    if not isinstance(metadata, dict):
                        metadata = {}
                    length = metadata.get('mpris:length', 0)
                    if not isinstance(length, (int, float)):
                        length = 0
                    if length > 0:
                        target = int((s.get_value() / 100) * length)
                        track_id = metadata.get('mpris:trackid', '')
                        self.active_player_proxy.SetPosition(track_id, target)
                except Exception as e:
                    c.print_debug(f"MPRIS seek error: {e}")

        widget.pop_seekbar_handler = widget.pop_seekbar.connect(
            'value-changed', on_seek)
        seek_box.append(widget.pop_seekbar)

        # Timestamps
        pos = data.get('position_str', '00:00')
        length = data.get('length_str', '00:00')
        widget.pop_time = c.label(
            f"{pos} / {length}", style='music-time', ha='center', he=True)
        # seek_box.append(widget.pop_time)
        content_box.append(seek_box)

        # Controls and volume inline
        ctrl_box = Gtk.CenterBox()
        ctrl_box.set_hexpand(True)

        def mpris_cmd(_btn, cmd):
            if self.active_player_proxy:
                try:
                    if cmd == 'toggle':
                        self.active_player_proxy.PlayPause()
                    elif cmd == 'prev':
                        self.active_player_proxy.Previous()
                    elif cmd == 'next':
                        self.active_player_proxy.Next()
                except Exception as e:
                    c.print_debug(f"MPRIS cmd error: {e}")

        prev_btn = c.button('', style='music-button')
        prev_btn.set_valign(Gtk.Align.FILL)
        prev_btn.connect('clicked', mpris_cmd, 'prev')

        widget.pop_play_btn = c.button(
            '' if data.get('status') == 'playing' else '',
            style='music-button')
        c.add_style(widget.pop_play_btn, 'play-button')
        widget.pop_play_btn.set_valign(Gtk.Align.FILL)
        widget.pop_play_btn.connect('clicked', mpris_cmd, 'toggle')

        next_btn = c.button('', style='music-button')
        next_btn.set_valign(Gtk.Align.FILL)
        next_btn.connect('clicked', mpris_cmd, 'next')

        # Volume inline
        vol_box = c.box('h', spacing=5)
        vol_box.set_hexpand(True)
        widget.pop_volume = c.slider(
                data.get('volume', 0), scrollable=True, style='music-volume')

        def on_volume(s):
            if self.active_player_proxy:
                try:
                    self.active_player_proxy.Volume = s.get_value() / 100.0
                except Exception as e:
                    c.print_debug(f"MPRIS volume error: {e}")

        widget.pop_volume_handler = widget.pop_volume.connect(
            'value-changed', on_volume)
        widget.pop_volume.set_hexpand(True)
        vol_box.append(widget.pop_volume)

        btn_box = c.box('h')
        btn_box.append(prev_btn)
        btn_box.append(widget.pop_play_btn)
        btn_box.append(next_btn)

        ctrl_box.set_start_widget(widget.pop_time)
        ctrl_box.set_end_widget(vol_box)
        ctrl_box.set_center_widget(btn_box)

        content_box.append(ctrl_box)
        main_box.append(content_box)

        return main_box

    def create_widget(self, bar):
        m = c.Module()
        m.set_position(bar.position)
        if m.text:
            m.text.set_max_width_chars(20)
            m.text.set_ellipsize(Pango.EllipsizeMode.END)
        m.set_visible(False)
        m.popover_built = False

        # Scroll to change volume
        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)

        def on_scroll(_widget, _dx, dy):
            if self.active_player_proxy:
                try:
                    vol = unwrap(self.active_player_proxy.Volume)
                    step = 0.05
                    if dy > 0:
                        new_vol = max(0.0, vol - step)
                    else:
                        new_vol = min(1.0, vol + step)
                    self.active_player_proxy.Volume = new_vol
                    self.update_state()
                except Exception as e:
                    c.print_debug(f"MPRIS volume scroll error: {e}")
            return True

        scroll.connect('scroll', on_scroll)
        m.add_controller(scroll)

        # Right click to toggle play/pause
        click = Gtk.GestureClick()
        click.set_button(3)

        def on_right_click(_gesture, _n_press, _x, _y):
            if self.active_player_proxy:
                try:
                    self.active_player_proxy.PlayPause()
                    self.update_state()
                except Exception as e:
                    c.print_debug(f"MPRIS toggle error: {e}")

        click.connect('released', on_right_click)
        m.add_controller(click)

        sub_id = c.state_manager.subscribe(
            self.name, lambda data: self.update_ui(m, data))
        m._subscriptions.append(sub_id)
        return m

    def update_ui(self, widget, data):
        if not data:
            widget.set_visible(False)
            return

        status = data.get('status', 'stopped')
        if status == 'playing':
            widget.set_icon('')
        elif status == 'paused':
            widget.set_icon('')
        else:
            widget.set_icon('')

        if self.show_title:
            widget.set_label(data.get('song', 'Stopped'))
        else:
            widget.set_label('')
        widget.set_visible(True)

        # Update popover content
        if not widget.popover_built:
            widget.set_widget(self.build_popover(widget, data))
            widget.popover_built = True
        else:
            try:
                self.update_popover_widgets(widget, data)
            except Exception as e:
                c.print_debug(f"Failed to update mpris popover: {e}",
                              color='red')


module_map = {
    'mpris': MPRIS
}
