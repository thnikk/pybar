#!/usr/bin/python3 -u
"""
Description: MPRIS module using Gio.DBusProxy directly (no dasbus)
Author: thnikk
"""
import weakref
import common as c
import os
import hashlib
import math
import random
import cairo
import requests
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import (  # noqa
    Gtk, Gdk, Pango, GdkPixbuf, GLib, Gio
)


class VisualizerBG(Gtk.DrawingArea):
    """ Background gradient for the visualizer """
    def __init__(self, height=56):
        super().__init__()
        self.set_overflow(Gtk.Overflow.HIDDEN)
        c.add_style(self, 'visualizer')
        self.set_content_height(height)
        self.set_hexpand(True)
        self.set_draw_func(self._draw)

    def _draw(self, _area, cr, width, height, *_args):
        bg = cairo.LinearGradient(0, 0, 0, height)
        bg.add_color_stop_rgba(0, 0.0, 0.0, 0.0, 0.0)
        bg.add_color_stop_rgba(1, 0.0, 0.0, 0.0, 0.5)
        cr.set_source(bg)
        cr.rectangle(0, 0, width, height)
        cr.fill()


class Visualizer(Gtk.DrawingArea):
    """ Animated bar visualizer for album art overlay """
    BAR_COUNT = 40
    TICK_MS = 40
    BAR_FILL = 0.5
    SMOOTH = 0.25
    RETARGET_CHANCE = 0.2
    ALPHA_TOP = 0.6
    ALPHA_BOT = 0.6

    def __init__(self, width, height=56):
        super().__init__()
        self.set_content_width(width)
        self.set_content_height(height)
        self.set_hexpand(True)
        c.add_style(self, 'visualizer')
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self._heights = [0.0] * self.BAR_COUNT
        self._targets = [
            random.uniform(0.05, 0.5) for _ in range(self.BAR_COUNT)
        ]
        self._timeout_id = None
        self.set_draw_func(self._draw)

    def start(self):
        """ Begin animation ticks """
        if self._timeout_id is None:
            self._timeout_id = GLib.timeout_add(self.TICK_MS, self._tick)

    def stop(self):
        """ Stop animation tick """
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _tick(self):
        for i in range(self.BAR_COUNT):
            if random.random() < self.RETARGET_CHANCE:
                self._targets[i] = random.uniform(0.05, 1.0)
            self._heights[i] += (
                (self._targets[i] - self._heights[i]) * self.SMOOTH
            )
        self.queue_draw()
        return True

    def _draw(self, _area, cr, width, height, *_args):
        n = self.BAR_COUNT
        slot_w = width / n
        bar_w = slot_w * self.BAR_FILL
        gap_w = slot_w * (1.0 - self.BAR_FILL)
        r = bar_w / 2
        for i, h in enumerate(self._heights):
            bar_h = max(bar_w, h * height * 0.92)
            x = i * slot_w + gap_w / 2
            y = height - bar_h
            grad = cairo.LinearGradient(x, y, x, height)
            grad.add_color_stop_rgba(0, 1.0, 1.0, 1.0, self.ALPHA_TOP)
            grad.add_color_stop_rgba(1, 1.0, 1.0, 1.0, self.ALPHA_BOT)
            cr.set_source(grad)
            cr.new_sub_path()
            cr.arc(x + r, y + r, r, math.pi, 2 * math.pi)
            cr.line_to(x + bar_w, height)
            cr.line_to(x, height)
            cr.close_path()
            cr.fill()


CACHE_DIR = os.path.expanduser('~/.cache/pybar')

PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
PLAYER_PATH = '/org/mpris/MediaPlayer2'
PROPS_IFACE = 'org.freedesktop.DBus.Properties'
DBUS_SERVICE = 'org.freedesktop.DBus'
DBUS_PATH = '/org/freedesktop/DBus'
DBUS_IFACE = 'org.freedesktop.DBus'


def _unpack(variant):
    """ Recursively unpack a GLib.Variant to a Python object """
    if variant is None:
        return None
    return variant.unpack()


def format_time(microseconds):
    """ Format microseconds to MM:SS or HH:MM:SS """
    seconds = int(microseconds / 1000000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class MPRIS(c.BaseModule):
    SCHEMA = {
        'players': {
            'type': 'list',
            'default': [],
            'label': 'Players',
            'description': (
                'List of player names to show. Empty for any player.')
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
        },
        'visualizer': {
            'type': 'boolean',
            'default': False,
            'label': 'Visualizer',
            'description': 'Show dummy visualizer over album art'
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        players = config.get('players', config.get('player', []))
        if isinstance(players, str):
            players = [players]
        self.target_players = [p.lower() for p in players]
        self.art_size = config.get('art_size', 300)
        self.show_title = config.get('show_title', True)
        self.show_visualizer = config.get('visualizer', True)

        # Gio DBus state
        self._bus = None
        self._player_proxy = None
        self._active_bus_name = None
        self._last_used_player = None
        self._name_owner_sub = None

    def _get_bus(self):
        """ Get or create the session bus connection """
        if self._bus is None:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        return self._bus

    def _list_names(self):
        """ List all DBus service names on the session bus """
        try:
            result = self._get_bus().call_sync(
                DBUS_SERVICE, DBUS_PATH, DBUS_IFACE, 'ListNames',
                None, GLib.VariantType.new('(as)'),
                Gio.DBusCallFlags.NONE, -1, None
            )
            return result[0]
        except Exception as e:
            c.print_debug(f"MPRIS ListNames error: {e}", color='red')
            return []

    def find_player(self):
        """ Find a matching MPRIS player bus name """
        names = self._list_names()
        players = [n for n in names if n.startswith(
            'org.mpris.MediaPlayer2.')]
        if not players:
            return None

        if self.target_players:
            for target in self.target_players:
                for p in players:
                    if target in p.lower():
                        return p
            return None

        # Prefer a playing player
        for p in players:
            try:
                proxy = Gio.DBusProxy.new_sync(
                    self._get_bus(), Gio.DBusProxyFlags.NONE, None,
                    p, PLAYER_PATH, PLAYER_IFACE, None
                )
                status = _unpack(proxy.get_cached_property('PlaybackStatus'))
                if status == 'Playing':
                    self._last_used_player = p
                    return p
            except Exception:
                continue

        if self._last_used_player in players:
            return self._last_used_player
        self._last_used_player = players[0]
        return players[0]

    def setup_player(self, bus_name):
        """ Create a Gio.DBusProxy for the given player bus name """
        self._player_proxy = None
        self._active_bus_name = bus_name
        if not bus_name:
            return
        try:
            self._player_proxy = Gio.DBusProxy.new_sync(
                self._get_bus(), Gio.DBusProxyFlags.NONE, None,
                bus_name, PLAYER_PATH, PLAYER_IFACE, None
            )
            # g-properties-changed fires when the player changes metadata
            self._player_proxy.connect(
                'g-properties-changed', self._on_properties_changed)
            c.print_debug(
                f"MPRIS: Connected to {bus_name}", color='green')
        except Exception as e:
            c.print_debug(
                f"MPRIS setup_player error: {e}", color='red')
            self._player_proxy = None

    def _on_properties_changed(self, _proxy, _changed, _invalidated):
        self.update_state()

    def _on_name_owner_changed(
            self, _conn, _sender, _path, _iface, _signal, params, _data):
        """ Handle DBus name owner changes to detect player start/stop """
        name, _old, _new = params
        if name.startswith('org.mpris.MediaPlayer2.'):
            best = self.find_player()
            if best != self._active_bus_name:
                self.setup_player(best)
                self.update_state()

    def update_state(self):
        """ Fetch current state and push to state manager """
        data = self.get_mpris_status()
        c.state_manager.update(self.name, data if data else {})

    def get_mpris_status(self):
        """ Read current MPRIS properties from the active player proxy """
        if not self._player_proxy:
            return None
        try:
            status = _unpack(
                self._player_proxy.get_cached_property('PlaybackStatus'))
            if not status:
                return None
            status = str(status).lower()

            metadata = _unpack(
                self._player_proxy.get_cached_property('Metadata')) or {}

            title = str(metadata.get('xesam:title', 'Unknown Song'))
            artists = metadata.get('xesam:artist', [])
            if isinstance(artists, list) and artists:
                artist = str(artists[0])
            elif isinstance(artists, str):
                artist = artists
            else:
                artist = ''

            art_url = str(metadata.get('mpris:artUrl', '') or '')
            art_path = self.get_art_path(art_url)

            length = metadata.get('mpris:length', 0) or 0
            position = 0
            try:
                pos_result = self._get_bus().call_sync(
                    self._active_bus_name,
                    '/org/mpris/MediaPlayer2',
                    'org.freedesktop.DBus.Properties',
                    'Get',
                    GLib.Variant('(ss)', (PLAYER_IFACE, 'Position')),
                    GLib.VariantType.new('(v)'),
                    Gio.DBusCallFlags.NONE, -1, None
                )
                if pos_result:
                    position = pos_result[0] or 0
            except Exception:
                pass

            percent = int((position / length) * 100) if length > 0 else 0

            volume = 0
            try:
                vol_result = self._get_bus().call_sync(
                    self._active_bus_name,
                    '/org/mpris/MediaPlayer2',
                    'org.freedesktop.DBus.Properties',
                    'Get',
                    GLib.Variant('(ss)', (PLAYER_IFACE, 'Volume')),
                    GLib.VariantType.new('(v)'),
                    Gio.DBusCallFlags.NONE, -1, None
                )
                if vol_result and vol_result[0] is not None:
                    volume = int(vol_result[0] * 100)
            except Exception:
                pass

            player_identity = None
            try:
                # Identity is on the root MediaPlayer2 interface
                root_proxy = Gio.DBusProxy.new_sync(
                    self._get_bus(), Gio.DBusProxyFlags.NONE, None,
                    self._active_bus_name, PLAYER_PATH,
                    'org.mpris.MediaPlayer2', None
                )
                id_var = root_proxy.get_cached_property('Identity')
                if id_var:
                    player_identity = id_var.unpack()
            except Exception:
                pass

            if not player_identity:
                player_identity = (
                    self._active_bus_name.split('.')[-1].capitalize())

            return {
                'status': status,
                'song': title,
                'artist': artist,
                'art': art_path,
                'percent': percent,
                'volume': volume,
                'position_str': format_time(position),
                'length_str': format_time(length),
                'text': title,
                'player': self._active_bus_name,
                'player_name': str(player_identity)
            }
        except Exception as e:
            c.print_debug(f"MPRIS get_status error: {e}", color='red')
            self._active_bus_name = None
            self._player_proxy = None
            return None

    def get_art_path(self, art_url):
        """ Resolve art URL to a local file path, downloading if needed """
        if not art_url:
            return None
        if art_url.startswith('file://'):
            return art_url[7:]
        if art_url.startswith('http'):
            os.makedirs(CACHE_DIR, exist_ok=True)
            art_filename = (
                f"mpris_{hashlib.md5(art_url.encode()).hexdigest()}.jpg")
            art_path = os.path.join(CACHE_DIR, art_filename)
            if not os.path.exists(art_path):
                try:
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

    def _call_player(self, method, params=None):
        """ Call a method on the active player """
        if not self._player_proxy:
            return
        try:
            self._player_proxy.call_sync(
                method, params, Gio.DBusCallFlags.NONE, -1, None)
        except Exception as e:
            c.print_debug(f"MPRIS call {method} error: {e}")

    def run_worker(self):
        """ Background worker for MPRIS """
        bus = self._get_bus()

        # Subscribe to NameOwnerChanged so we detect players starting/stopping
        self._name_owner_sub = bus.signal_subscribe(
            DBUS_SERVICE, DBUS_IFACE, 'NameOwnerChanged', DBUS_PATH,
            None, Gio.DBusSignalFlags.NONE,
            self._on_name_owner_changed, None
        )

        player = self.find_player()
        self.setup_player(player)
        self.update_state()

        while True:
            try:
                best = self.find_player()
                if best != self._active_bus_name:
                    self.setup_player(best)
                    self.update_state()
                elif self._player_proxy:
                    status = _unpack(
                        self._player_proxy.get_cached_property(
                            'PlaybackStatus'))
                    if status == 'Playing':
                        self.update_state()
            except Exception:
                pass
            time.sleep(1)

    # ------------------------------------------------------------------ #
    # Widget / UI — identical to original, just wiring player calls
    # ------------------------------------------------------------------ #

    def update_popover_widgets(self, widget, data):
        """ Update existing popover widgets in-place """
        art_path = data.get('art')
        if hasattr(widget, 'pop_art') and art_path != getattr(
                widget, 'last_art_path', None):
            widget.last_art_path = art_path
            if art_path and os.path.exists(art_path):
                try:
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                        art_path, self.art_size, self.art_size, True)
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

        player_name = data.get('player_name', 'Unknown')
        if hasattr(widget, 'pop_player_name') and (
                widget.pop_player_name.get_text() != player_name):
            widget.pop_player_name.set_text(player_name)

        song = data.get('song', 'Unknown Song')
        artist = data.get('artist', '')
        if hasattr(widget, 'pop_song') and widget.pop_song.get_text() != song:
            widget.pop_song.set_text(song)
        if hasattr(widget, 'pop_artist'):
            if widget.pop_artist.get_text() != artist:
                widget.pop_artist.set_text(artist)
            widget.pop_artist.set_visible(bool(artist))

        if hasattr(widget, 'pop_seekbar'):
            widget.pop_seekbar.handler_block(widget.pop_seekbar_handler)
            widget.pop_seekbar.set_value(data.get('percent', 0))
            widget.pop_seekbar.handler_unblock(widget.pop_seekbar_handler)

        if hasattr(widget, 'pop_time'):
            widget.pop_time.set_text(
                f"{data.get('position_str', '00:00')} / "
                f"{data.get('length_str', '00:00')}"
            )

        if hasattr(widget, 'pop_volume'):
            widget.pop_volume.handler_block(widget.pop_volume_handler)
            widget.pop_volume.set_value(data.get('volume', 0))
            widget.pop_volume.handler_unblock(widget.pop_volume_handler)

        if hasattr(widget, 'pop_play_btn'):
            label = '' if data.get('status') == 'playing' else ''
            if widget.pop_play_btn.get_label() != label:
                widget.pop_play_btn.set_label(label)

        if hasattr(widget, 'pop_vis_revealer') and hasattr(
                widget, 'pop_visualizer'):
            is_playing = data.get('status') == 'playing'
            widget.pop_vis_revealer.set_reveal_child(is_playing)
            if hasattr(widget, 'pop_vis_bg_revealer'):
                widget.pop_vis_bg_revealer.set_reveal_child(is_playing)
            if is_playing:
                widget.pop_visualizer.start()
            else:
                widget.pop_visualizer.stop()

    def build_popover(self, widget, data):
        """ Build the MPRIS popover widget """
        main_box = c.box('v', spacing=10, style='small-widget')

        player_name = data.get('player_name', 'Unknown')
        widget.pop_player_name = c.label(player_name, style='heading')
        main_box.append(widget.pop_player_name)

        art_size = self.art_size
        art_path = data.get('art')

        art_container = c.box('v', style='cover-art')
        art_container.set_size_request(art_size, art_size)
        art_container.set_overflow(Gtk.Overflow.HIDDEN)
        art_container.set_halign(Gtk.Align.CENTER)
        art_container.set_valign(Gtk.Align.CENTER)
        art_container.set_hexpand(False)
        art_container.set_vexpand(False)

        widget.pop_art = Gtk.Image()
        widget.pop_art.set_pixel_size(art_size)
        widget.pop_art_placeholder = c.label(
            '', style='large-text', va='center', ha='center', he=True)
        widget.pop_art_placeholder.set_size_request(art_size, art_size)
        art_container.append(widget.pop_art)
        art_container.append(widget.pop_art_placeholder)

        art_overlay = Gtk.Overlay()
        art_overlay.set_halign(Gtk.Align.CENTER)
        art_overlay.set_child(art_container)

        if self.show_visualizer:
            widget.pop_vis_bg = VisualizerBG()
            widget.pop_vis_bg_revealer = Gtk.Revealer()
            widget.pop_vis_bg_revealer.set_transition_type(
                Gtk.RevealerTransitionType.CROSSFADE)
            widget.pop_vis_bg_revealer.set_transition_duration(500)
            widget.pop_vis_bg_revealer.set_child(widget.pop_vis_bg)
            widget.pop_vis_bg_revealer.set_valign(Gtk.Align.END)
            widget.pop_vis_bg_revealer.set_halign(Gtk.Align.FILL)
            art_overlay.add_overlay(widget.pop_vis_bg_revealer)

            widget.pop_visualizer = Visualizer(art_size)
            widget.pop_visualizer.set_valign(Gtk.Align.END)
            widget.pop_visualizer.set_halign(Gtk.Align.FILL)
            widget.pop_vis_revealer = Gtk.Revealer()
            widget.pop_vis_revealer.set_transition_duration(300)
            widget.pop_vis_revealer.set_child(widget.pop_visualizer)
            widget.pop_vis_revealer.set_valign(Gtk.Align.END)
            widget.pop_vis_revealer.set_halign(Gtk.Align.FILL)
            art_overlay.add_overlay(widget.pop_vis_revealer)

            is_playing = data.get('status') == 'playing'
            widget.pop_vis_revealer.set_reveal_child(is_playing)
            widget.pop_vis_bg_revealer.set_reveal_child(is_playing)
            if is_playing:
                widget.pop_visualizer.start()

        main_box.append(art_overlay)

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

        content_box = c.box('v', spacing=10, style='music-box')

        widget.pop_song = c.label(
            data.get('song', 'Unknown Song'),
            length=art_size // 15, style='title')
        widget.pop_artist = c.label(
            data.get('artist', ''), style='artist',
            length=art_size // 15)
        widget.pop_artist.set_visible(bool(data.get('artist')))
        content_box.append(widget.pop_song)
        content_box.append(widget.pop_artist)

        seek_box = c.box('v')
        widget.pop_seekbar = c.slider(
            data.get('percent', 0), scrollable=False)

        def on_seek(s):
            if not self._player_proxy:
                return
            try:
                meta = _unpack(
                    self._player_proxy.get_cached_property('Metadata')) or {}
                length = meta.get('mpris:length', 0) or 0
                if length > 0:
                    target = int((s.get_value() / 100) * length)
                    track_id = meta.get('mpris:trackid', '')
                    self._player_proxy.call_sync(
                        'SetPosition',
                        GLib.Variant('(ox)', (track_id, target)),
                        Gio.DBusCallFlags.NONE, -1, None
                    )
            except Exception as e:
                c.print_debug(f"MPRIS seek error: {e}")

        widget.pop_seekbar_handler = widget.pop_seekbar.connect(
            'value-changed', on_seek)
        seek_box.append(widget.pop_seekbar)

        pos = data.get('position_str', '00:00')
        length = data.get('length_str', '00:00')
        widget.pop_time = c.label(
            f"{pos} / {length}", style='music-time', ha='center', he=True)
        content_box.append(seek_box)

        ctrl_box = Gtk.CenterBox()
        ctrl_box.set_hexpand(True)

        def mpris_cmd(_btn, cmd):
            if not self._player_proxy:
                return
            try:
                self._player_proxy.call_sync(
                    {'toggle': 'PlayPause',
                     'prev': 'Previous',
                     'next': 'Next'}[cmd],
                    None, Gio.DBusCallFlags.NONE, -1, None
                )
            except Exception as e:
                c.print_debug(f"MPRIS cmd error: {e}")

        prev_btn = c.button('', style='music-button')
        prev_btn.set_valign(Gtk.Align.FILL)
        prev_btn.connect('clicked', mpris_cmd, 'prev')

        widget.pop_play_btn = c.button(
            '' if data.get('status') == 'playing' else '',
            style='music-button')
        c.add_style(widget.pop_play_btn, 'play-button')
        widget.pop_play_btn.set_valign(Gtk.Align.FILL)
        widget.pop_play_btn.connect('clicked', mpris_cmd, 'toggle')

        next_btn = c.button('', style='music-button')
        next_btn.set_valign(Gtk.Align.FILL)
        next_btn.connect('clicked', mpris_cmd, 'next')

        vol_box = c.box('h', spacing=5)
        vol_box.set_hexpand(True)
        widget.pop_volume = c.slider(
            data.get('volume', 0), scrollable=True, style='music-volume')

        def on_volume(s):
            if not self._player_proxy:
                return
            try:
                self._player_proxy.call_sync(
                    'org.freedesktop.DBus.Properties.Set',
                    GLib.Variant(
                        '(ssv)',
                        (PLAYER_IFACE, 'Volume',
                         GLib.Variant('d', s.get_value() / 100.0))
                    ),
                    Gio.DBusCallFlags.NONE, -1, None
                )
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

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.VERTICAL)

        def on_scroll(_widget, _dx, dy):
            if not self._player_proxy:
                return True
            try:
                vol_var = self._player_proxy.get_cached_property('Volume')
                vol = vol_var.unpack() if vol_var else 0.5
                new_vol = max(0.0, vol - 0.05) if dy > 0 else min(
                    1.0, vol + 0.05)
                self._player_proxy.call_sync(
                    'org.freedesktop.DBus.Properties.Set',
                    GLib.Variant(
                        '(ssv)',
                        (PLAYER_IFACE, 'Volume',
                         GLib.Variant('d', new_vol))
                    ),
                    Gio.DBusCallFlags.NONE, -1, None
                )
                self.update_state()
            except Exception as e:
                c.print_debug(f"MPRIS volume scroll error: {e}")
            return True

        scroll.connect('scroll', on_scroll)
        m.add_controller(scroll)

        click = Gtk.GestureClick()
        click.set_button(3)

        def on_right_click(_gesture, _n_press, _x, _y):
            if not self._player_proxy:
                return
            try:
                self._player_proxy.call_sync(
                    'PlayPause', None,
                    Gio.DBusCallFlags.NONE, -1, None)
                self.update_state()
            except Exception as e:
                c.print_debug(f"MPRIS toggle error: {e}")

        click.connect('released', on_right_click)
        m.add_controller(click)

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

        status = data.get('status', 'stopped')
        icon = {'playing': '', 'paused': ''}.get(status, '')
        widget.set_icon(icon)

        if self.show_title:
            widget.set_label(data.get('song', 'Stopped'))
        else:
            widget.set_label('')
        widget.set_visible(True)

        if not widget.popover_built:
            widget.set_widget(self.build_popover(widget, data))
            widget.popover_built = True
        else:
            try:
                self.update_popover_widgets(widget, data)
            except Exception as e:
                c.print_debug(
                    f"Failed to update mpris popover: {e}", color='red')


module_map = {
    'mpris': MPRIS
}
