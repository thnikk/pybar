#!/usr/bin/python3 -u
"""
Description: Feishin module using the remote WebSocket API
Author: thnikk
"""
import asyncio
import base64
import hashlib
import json
import math
import os
import random
import re
import shutil
import struct
import subprocess
import threading
import time
import weakref
import cairo
import aiohttp
import requests
import common as c
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf, GLib  # noqa


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

    # Number of bars in the visualizer
    BAR_COUNT = 40
    # How often to tick the animation in milliseconds
    TICK_MS = 16
    # Fraction of bar area used per bar (rest is gap)
    BAR_FILL = 0.5
    # Smoothing factor for bar height interpolation
    SMOOTH = 0.25
    # Probability a bar picks a new random target each tick
    RETARGET_CHANCE = 0.2
    # Gradient top/bottom alpha values
    ALPHA_TOP = 0.6
    ALPHA_BOT = 0.6

    def __init__(self, width, height=56, audio_capture=None):
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
        self._audio_capture = audio_capture
        self._timeout_id = None
        self.set_draw_func(self._draw)

    def start(self):
        """ Begin animation ticks """
        if self._timeout_id is None:
            self._timeout_id = GLib.timeout_add(
                self.TICK_MS, self._tick
            )

    def stop(self):
        """ Stop animation tick; bar heights are preserved """
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def _tick(self):
        """ Advance animation one frame """
        real = None
        if self._audio_capture and self._audio_capture.has_data():
            real = self._audio_capture.bars()
        for i in range(self.BAR_COUNT):
            if real is not None and i < len(real):
                self._targets[i] = real[i]
            elif random.random() < self.RETARGET_CHANCE:
                self._targets[i] = random.uniform(0.05, 1.0)
            self._heights[i] += (
                (self._targets[i] - self._heights[i]) * self.SMOOTH
            )
        self.queue_draw()
        return True

    def _draw(self, _area, cr, width, height, *_args):
        """ Draw fully-rounded visualizer bars """
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
            grad.add_color_stop_rgba(
                0, 1.0, 1.0, 1.0, self.ALPHA_TOP
            )
            grad.add_color_stop_rgba(
                1, 1.0, 1.0, 1.0, self.ALPHA_BOT
            )
            cr.set_source(grad)
            cr.new_sub_path()
            cr.arc(x + r, y + r, r, math.pi, 2 * math.pi)
            cr.line_to(x + bar_w, height)
            cr.line_to(x, height)
            cr.close_path()
            cr.fill()


CACHE_DIR = os.path.expanduser('~/.cache/pybar')
RECONNECT_DELAY = 5
ART_TIMEOUT = 10
ART_CACHE_MAX = 10


def format_time(seconds):
    """ Format seconds to MM:SS or HH:MM:SS """
    seconds = int(seconds)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def fft_radix2(real):
    """ In-place iterative radix-2 FFT; returns complex list.

    real must be a power-of-two length list of floats.
    """
    n = len(real)
    # Bit-reversal permutation
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            real[i], real[j] = real[j], real[i]

    data = [complex(x, 0.0) for x in real]
    length = 2
    while length <= n:
        ang = -2.0 * math.pi / length
        wlen = complex(math.cos(ang), math.sin(ang))
        half = length // 2
        for i in range(0, n, length):
            w = 1.0 + 0.0j
            for k in range(i, i + half):
                u = data[k]
                v = data[k + half] * w
                data[k] = u + v
                data[k + half] = u - v
                w *= wlen
        length *= 2
    return data


class AudioCapture:
    """ Capture feishin's audio stream and compute spectrum bars """

    SAMPLE_RATE = 48000
    CHANNELS = 2
    FFT_SIZE = 2048
    BAR_COUNT = 40
    F_MIN = 30.0
    F_MAX = 15000.0
    # AGC: bars stay lively regardless of playback volume
    TARGET_LEVEL = 0.03
    GAIN_MIN = 0.25
    GAIN_MAX = 4.0
    SILENCE_FLOOR = 1e-4

    def __init__(self):
        self._proc = None
        self._thread = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._bars = [0.0] * self.BAR_COUNT
        self._has_data = False
        self._smooth = [0.0] * self.BAR_COUNT
        self._band_edges = self._log_bands()
        self._agc_level = 0.0
        self._agc_gain = 1.0

    @staticmethod
    def _log_bands():
        """ Log-spaced band edges from F_MIN to F_MAX.

        Each band is clamped to at least one FFT bin wide so no band is
        empty (an empty band would never move).
        """
        bin_w = AudioCapture.SAMPLE_RATE / AudioCapture.FFT_SIZE
        steps = AudioCapture.BAR_COUNT + 1
        edges = []
        for i in range(steps):
            t = i / (steps - 1)
            freq = (AudioCapture.F_MIN * (AudioCapture.F_MAX /
                                          AudioCapture.F_MIN) ** t)
            edges.append(freq)
        # Enforce a minimum width of one bin by merging narrow bands
        clamped = [edges[0]]
        for edge in edges[1:]:
            if edge - clamped[-1] < bin_w:
                edge = clamped[-1] + bin_w
            clamped.append(edge)
        clamped[-1] = AudioCapture.F_MAX
        return clamped

    def bars(self):
        """ Thread-safe snapshot of normalized bar heights (0..1) """
        with self._lock:
            return list(self._smooth)

    def has_data(self):
        return self._has_data

    def _find_node(self):
        """ Find feishin's PipeWire node serial via pactl """
        try:
            out = subprocess.run(
                ['pactl', 'list', 'sink-inputs'],
                capture_output=True, text=True, timeout=3
            ).stdout
        except Exception:
            return None
        node = None
        for line in out.splitlines():
            m = re.match(r'\s*Sink Input #(\d+)', line)
            if m:
                node = m.group(1)
            if 'application.process.binary = "feishin"' in line:
                return node
        return None

    def _spawn(self, node):
        """ Spawn the capture subprocess for the given node """
        if shutil.which('pw-record'):
            cmd = [
                'pw-record', '--target', node, '--format', 'f32',
                '--rate', str(self.SAMPLE_RATE),
                '--channels', str(self.CHANNELS),
                '--container', 'raw', '-'
            ]
        elif shutil.which('parec'):
            cmd = [
                'parec', '--device', node, '--format=float32le',
                '--rate', str(self.SAMPLE_RATE),
                '--channels', str(self.CHANNELS)
            ]
        else:
            return None
        try:
            return subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except Exception:
            return None

    def _run(self):
        """ Capture loop: read PCM, FFT, update bars """
        while not self._stop.is_set():
            node = self._find_node()
            if not node:
                time.sleep(2)
                continue
            proc = self._spawn(node)
            if not proc:
                time.sleep(2)
                continue
            self._proc = proc
            self._read_stream(proc)
            self._proc = None
            try:
                proc.terminate()
            except Exception:
                pass

    def _read_stream(self, proc):
        """ Read PCM from proc stdout and compute spectrum """
        samples = []
        chunk_size = 8192
        while not self._stop.is_set():
            raw = proc.stdout.read(chunk_size)
            if not raw:
                break
            n = len(raw) // 4
            if n == 0:
                continue
            vals = struct.unpack(f'<{n}f', raw[:n * 4])
            samples.extend(vals)
            while len(samples) >= self.FFT_SIZE * self.CHANNELS:
                frame = samples[:self.FFT_SIZE * self.CHANNELS]
                del samples[:self.FFT_SIZE]
                self._process_frame(frame)
        self._has_data = False

    def _process_frame(self, frame):
        """ FFT one interleaved stereo frame and update bar heights """
        # Downmix to mono
        mono = [
            (frame[i] + frame[i + 1]) * 0.5
            for i in range(0, len(frame), self.CHANNELS)
        ]
        spectrum = fft_radix2(mono)
        nyquist = self.SAMPLE_RATE / 2
        # Magnitudes for positive frequencies (skip DC)
        n_half = self.FFT_SIZE // 2
        mags = [abs(spectrum[i]) for i in range(1, n_half)]
        bins = [i * self.SAMPLE_RATE / self.FFT_SIZE
                for i in range(1, n_half)]

        heights = [0.0] * self.BAR_COUNT
        norm = 2.0 / self.FFT_SIZE
        # Map -60dB..0dB to 0..1 for good dynamics across volume levels
        dB_floor = -60.0
        raw = [0.0] * self.BAR_COUNT
        level = 0.0
        count = 0
        for band in range(self.BAR_COUNT):
            lo = self._band_edges[band]
            hi = self._band_edges[band + 1]
            total = 0.0
            bin_count = 0
            for i, freq in enumerate(bins):
                if lo <= freq < hi and freq <= nyquist:
                    total += mags[i] * norm
                    bin_count += 1
            if bin_count:
                raw[band] = total / bin_count
                level += raw[band]
                count += 1
        if count:
            level /= count

        # AGC: adapt gain to overall level with fast attack / slow release
        if level > self._agc_level:
            self._agc_level += (level - self._agc_level) * 0.3
        else:
            self._agc_level += (level - self._agc_level) * 0.05

        target = 1.0
        if self._agc_level > self.SILENCE_FLOOR:
            target = self.TARGET_LEVEL / self._agc_level
        target = min(self.GAIN_MAX, max(self.GAIN_MIN, target))
        if target > self._agc_gain:
            self._agc_gain += (target - self._agc_gain) * 0.3
        else:
            self._agc_gain += (target - self._agc_gain) * 0.05

        # Apply gain in the linear domain, then convert to dB
        for i in range(self.BAR_COUNT):
            avg = raw[i] * self._agc_gain
            if avg > 0:
                db = 20.0 * math.log10(max(avg, 1e-8))
                heights[i] = min(1.0, max(0.0,
                                          (db - dB_floor) / -dB_floor))

        with self._lock:
            self._has_data = True
            # Smooth bar heights for a stable display
            for i in range(self.BAR_COUNT):
                self._smooth[i] += (
                    (heights[i] - self._smooth[i]) * 0.6
                )
            self._bars = heights

    def start(self):
        """ Start the capture thread """
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """ Stop the capture thread """
        self._stop.set()
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._proc = None

    def cleanup(self):
        """ Full stop and clear state """
        self.stop()
        with self._lock:
            self._smooth = [0.0] * self.BAR_COUNT
            self._has_data = False


class Feishin(c.BaseModule):
    SCHEMA = {
        'host': {
            'type': 'string',
            'default': 'localhost',
            'label': 'Host',
            'description': 'Host running the Feishin remote server'
        },
        'port': {
            'type': 'integer',
            'default': 4333,
            'label': 'Port',
            'description': 'Port of the Feishin remote server',
            'min': 1,
            'max': 65535
        },
        'username': {
            'type': 'string',
            'default': '',
            'label': 'Username',
            'description': 'Username for the remote server (if set)'
        },
        'password': {
            'type': 'string',
            'default': '',
            'label': 'Password',
            'description': 'Password for the remote server (if set)'
        },
        'show_title': {
            'type': 'boolean',
            'default': True,
            'label': 'Show Title',
            'description': 'Show song title in the bar'
        },
        'art_size': {
            'type': 'integer',
            'default': 300,
            'label': 'Album Art Size',
            'description': 'Size of album art in popover (pixels)',
            'min': 100,
            'max': 500
        },
        'visualizer': {
            'type': 'boolean',
            'default': False,
            'label': 'Visualizer',
            'description': 'Show visualizer over album art'
        },
        'visualizer_height': {
            'type': 'integer',
            'default': 20,
            'label': 'Visualizer Height',
            'description': 'Visualizer height as a percentage of '
                           'album art height',
            'min': 5,
            'max': 100
        }
    }

    def __init__(self, name, config):
        super().__init__(name, config)
        self.host = config.get('host', 'localhost')
        self.port = int(config.get('port', 4333))
        self.username = config.get('username', '')
        self.password = config.get('password', '')
        self.art_size = config.get('art_size', 300)
        self.show_title = config.get('show_title', True)
        self.show_visualizer = config.get('visualizer', False)
        self.visualizer_height = config.get('visualizer_height', 20)
        self.visualizer_height = max(5, min(100, self.visualizer_height))
        self.state = {}
        self._loop = None
        self._ws = None
        self._art_path = None
        self._art_lock = threading.Lock()
        self._audio_capture = AudioCapture()
        self._popover_visible = False

    def ws_url(self):
        """ WebSocket URL for the remote server """
        return f"ws://{self.host}:{self.port}/"

    def send_event(self, event):
        """ Send an event to the server from any thread """
        ws = self._ws
        loop = self._loop
        if not ws or not loop:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                ws.send_str(json.dumps(event)), loop
            )
        except Exception as e:
            c.print_debug(f"Feishin send error: {e}", color='red')

    def toggle_play(self):
        """ Toggle play/pause """
        self.send_event({'event': 'pause' if self.state.get('status')
                         == 'playing' else 'play'})

    def next_track(self):
        """ Play next track """
        self.send_event({'event': 'next'})

    def prev_track(self):
        """ Play previous track """
        self.send_event({'event': 'previous'})

    def toggle_shuffle(self):
        """ Toggle shuffle """
        self.send_event({'event': 'shuffle'})

    def toggle_repeat(self):
        """ Toggle repeat """
        self.send_event({'event': 'repeat'})

    def toggle_favorite(self):
        """ Toggle favorite on current song """
        song = self.state.get('song')
        if not song:
            return
        self.send_event({
            'event': 'favorite',
            'favorite': not song.get('userFavorite', False),
            'id': song.get('id')
        })

    def set_position(self, seconds):
        """ Seek to position in seconds """
        self.send_event({'event': 'position', 'position': int(seconds)})

    def set_volume(self, volume):
        """ Set volume 0-100 """
        self.send_event({'event': 'volume', 'volume': int(volume)})

    def handle_message(self, message):
        """ Handle a message from the server """
        event = message.get('event')
        data = message.get('data')
        song_changed = False
        if event == 'state':
            old_id = self.state.get('song', {}).get('id')
            self.state = data or {}
            new_id = self.state.get('song', {}).get('id')
            song_changed = old_id != new_id
        elif event == 'song':
            old_id = self.state.get('song', {}).get('id')
            self.state['song'] = data
            new_id = data.get('id') if data else None
            song_changed = old_id != new_id
        elif event == 'playback':
            self.state['status'] = data
        elif event == 'position':
            self.state['position'] = data
        elif event == 'volume':
            self.state['volume'] = data
        elif event == 'repeat':
            self.state['repeat'] = data
        elif event == 'shuffle':
            self.state['shuffle'] = data
        elif event == 'favorite':
            song = self.state.get('song')
            if song and song.get('id') == data.get('id'):
                song['userFavorite'] = data.get('favorite')
        elif event == 'rating':
            song = self.state.get('song')
            if song and song.get('id') == data.get('id'):
                song['userRating'] = data.get('rating')
        elif event in ('proxy', 'error'):
            return False
        else:
            return False

        if song_changed:
            self._art_path = None
        self.update_state()
        return song_changed

    def get_status(self):
        """ Build state dict for the bar/popover """
        state = self.state
        song = state.get('song')
        if not song:
            return None

        title = str(song.get('name', 'Unknown Song'))
        artist = str(song.get('artistName', ''))
        album = song.get('album') or ''

        art_path = self._art_path

        length = song.get('duration', 0)
        if not isinstance(length, (int, float)):
            length = 0

        position = state.get('position', 0)
        if not isinstance(position, (int, float)):
            position = 0

        percent = 0
        if length > 0:
            percent = int((position / (length / 1000)) * 100)
            percent = max(0, min(100, percent))

        return {
            "status": state.get('status', 'stopped'),
            "song": title,
            "artist": artist,
            "album": album,
            "art": art_path,
            "percent": percent,
            "volume": state.get('volume', 0),
            "position_str": format_time(position),
            "length_str": format_time(length / 1000),
            "text": title,
            "player": "feishin",
            "player_name": "Feishin",
            "play_count": song.get('playCount', 0),
            "user_favorite": song.get('userFavorite', False),
            "repeat": state.get('repeat', 'none'),
            "shuffle": state.get('shuffle', False),
        }

    def update_state(self):
        """ Push current state to state manager """
        data = self.get_status()
        c.state_manager.update(self.name, data or {})

    def _art_urls_for_song(self):
        """ Candidate art URLs for the current song, best first.

        Feishin's song-change events sometimes point imageUrl at the song
        id, which 404s for tracks that share album art. The actual image
        resource lives at imageId (Jellyfin), so build a fallback URL from
        it as well.
        """
        song = self.state.get('song')
        if not song:
            return []
        image_url = song.get('imageUrl', '')
        if image_url:
            image_url = re.sub(r'&(size|width|height)=\d+', '', image_url)
        urls = [image_url] if image_url else []

        song_id = song.get('id')
        image_id = song.get('imageId')
        if image_url and song_id and image_id and image_id != song_id:
            alt = image_url.replace(
                f'/Items/{song_id}/', f'/Items/{image_id}/')
            if alt != image_url:
                urls.append(alt)
        return urls

    def download_art(self, art_url):
        """ Download and cache album art; return local path.

        Runs off the event loop in a worker thread. Writes are atomic
        and bounded by ART_CACHE_MAX.
        """
        if not art_url:
            return None

        with self._art_lock:
            if not os.path.exists(CACHE_DIR):
                try:
                    os.makedirs(CACHE_DIR, exist_ok=True)
                except Exception:
                    return None

            art_filename = \
                f"feishin_{hashlib.md5(art_url.encode()).hexdigest()}.jpg"
            art_path = os.path.join(CACHE_DIR, art_filename)

            if os.path.exists(art_path):
                return art_path

            tmp_path = art_path + '.tmp'
            try:
                response = requests.get(art_url, timeout=ART_TIMEOUT)
                if response.status_code == 200:
                    with open(tmp_path, 'wb') as f:
                        f.write(response.content)
                    os.replace(tmp_path, art_path)
                    self._prune_art_cache()
                    return art_path
            except Exception:
                return None
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        return None

    def _prune_art_cache(self):
        """ Keep only the newest ART_CACHE_MAX art files """
        try:
            files = [
                os.path.join(CACHE_DIR, f)
                for f in os.listdir(CACHE_DIR)
                if f.startswith('feishin_') and f.endswith('.jpg')
            ]
            files.sort(key=os.path.getmtime, reverse=True)
            for f in files[ART_CACHE_MAX:]:
                try:
                    os.remove(f)
                except Exception:
                    pass
        except Exception:
            pass

    async def _fetch_art(self):
        """ Download art for the current song off the event loop """
        art_urls = self._art_urls_for_song()
        if not art_urls:
            return
        art_path = None
        for art_url in art_urls:
            # Stop if the song changed while downloading
            if self._art_urls_for_song()[:1] != art_urls[:1]:
                return
            art_path = await asyncio.to_thread(self.download_art, art_url)
            if art_path:
                break
        # Only apply if the song hasn't changed while downloading
        if self._art_urls_for_song() != art_urls:
            return
        self._art_path = art_path
        self.update_state()

    async def client_loop(self):
        """ Connect and read messages until disconnected """
        auth_header = None
        if self.username or self.password:
            token = base64.b64encode(
                f"{self.username}:{self.password}".encode()
            ).decode()
            auth_header = f"Basic {token}"

        self._loop = asyncio.get_running_loop()
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(self.ws_url()) as ws:
                self._ws = ws
                c.print_debug(
                    f"Feishin: Connected to {self.ws_url()}", color='green')
                if auth_header:
                    await ws.send_str(json.dumps({
                        'event': 'authenticate',
                        'header': auth_header
                    }))

                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        try:
                            song_changed = self.handle_message(
                                json.loads(msg.data))
                            if song_changed:
                                asyncio.ensure_future(self._fetch_art())
                        except Exception as e:
                            c.print_debug(
                                f"Feishin message error: {e}", color='red')
                    elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR):
                        break

    def run_worker(self):
        """ Background worker for feishin """
        import module as m
        stop_event = m._worker_stop_flags.get(self.name)

        while True:
            if stop_event and stop_event.is_set():
                break
            try:
                asyncio.run(self.client_loop())
            except asyncio.CancelledError:
                break
            except Exception as e:
                c.print_debug(f"Feishin connection error: {e}", color='red')
            self._ws = None
            self.state = {}
            c.state_manager.update(self.name, {})
            if stop_event and stop_event.is_set():
                break
            time_wait = stop_event.wait(RECONNECT_DELAY) \
                if stop_event else None
            if stop_event and time_wait:
                break

    def cleanup(self):
        """ Close the websocket and stop the visualizer capture """
        ws = self._ws
        self._ws = None
        if ws:
            try:
                loop = self._loop
                if loop:
                    asyncio.run_coroutine_threadsafe(
                        ws.close(), loop
                    )
            except Exception:
                pass
        self._audio_capture.cleanup()

    def fetch_data(self):
        """ Polling fallback; feishin is push-based """
        return None

    def _set_active(self, button, active, active_class):
        """ Add or remove the active style on a toggle button """
        if active:
            c.add_style(button, active_class)
        else:
            button.get_style_context().remove_class(active_class)

    def _update_visualizer(self, widget, is_playing):
        """ Start/stop the visualizer based on popover + playback state """
        if not self.show_visualizer:
            return
        active = is_playing and self._popover_visible
        if active:
            widget.pop_visualizer.start()
            self._audio_capture.start()
        else:
            widget.pop_visualizer.stop()
            self._audio_capture.stop()

    def _track_popover_visibility(self, widget):
        """ Watch the popover so the capture only runs while visible """
        popover = widget.get_popover()
        if popover is None:
            return

        def on_show(_popover):
            self._popover_visible = True
            if hasattr(widget, 'pop_visualizer'):
                is_playing = self.state.get('status') == 'playing'
                self._update_visualizer(widget, is_playing)

        def on_hide(_popover):
            self._popover_visible = False
            if hasattr(widget, 'pop_visualizer'):
                self._update_visualizer(widget, False)

        popover.connect('show', on_show)
        popover.connect('hide', on_hide)

    def update_popover_widgets(self, widget, data):
        """ Update existing popover widgets """
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

        song = data.get('song', 'Unknown Song')
        artist = data.get('artist', '')

        if hasattr(widget, 'pop_song') and widget.pop_song.get_text() != song:
            widget.pop_song.set_text(song)
        if hasattr(widget, 'pop_artist'):
            if widget.pop_artist.get_text() != artist:
                widget.pop_artist.set_text(artist)
            widget.pop_artist.set_visible(bool(artist))

        if hasattr(widget, 'pop_playcount'):
            widget.pop_playcount.set_text(
                f"Plays: {data.get('play_count', 0)}")

        if hasattr(widget, 'pop_seekbar'):
            widget.pop_seekbar.handler_block(widget.pop_seekbar_handler)
            widget.pop_seekbar.set_value(data.get('percent', 0))
            widget.pop_seekbar.handler_unblock(widget.pop_seekbar_handler)

        if hasattr(widget, 'pop_time'):
            pos = data.get('position_str', '00:00')
            length = data.get('length_str', '00:00')
            widget.pop_time.set_text(f"{pos} / {length}")

        if hasattr(widget, 'pop_volume'):
            widget.pop_volume.handler_block(widget.pop_volume_handler)
            widget.pop_volume.set_value(data.get('volume', 0))
            widget.pop_volume.handler_unblock(widget.pop_volume_handler)

        if hasattr(widget, 'pop_play_btn'):
            label = '' if data.get('status') == 'playing' else ''
            if widget.pop_play_btn.get_label() != label:
                widget.pop_play_btn.set_label(label)

        if hasattr(widget, 'pop_shuffle_btn'):
            self._set_active(
                widget.pop_shuffle_btn, data.get('shuffle', False),
                'active-shuffle')

        if hasattr(widget, 'pop_repeat_btn'):
            repeat = data.get('repeat', 'none')
            self._set_active(
                widget.pop_repeat_btn, repeat != 'none', 'active-repeat')
            if hasattr(widget, 'pop_repeat_badge'):
                widget.pop_repeat_badge.set_visible(repeat == 'one')

        if hasattr(widget, 'pop_fav_btn'):
            fav = data.get('user_favorite', False)
            widget.pop_fav_btn.set_label('' if fav else '')
            self._set_active(widget.pop_fav_btn, fav, 'active-fav')

        if hasattr(widget, 'pop_vis_revealer') and \
                hasattr(widget, 'pop_visualizer'):
            is_playing = data.get('status') == 'playing'
            widget.pop_vis_revealer.set_reveal_child(is_playing)
            if hasattr(widget, 'pop_vis_bg_revealer'):
                widget.pop_vis_bg_revealer.set_reveal_child(is_playing)
            self._update_visualizer(widget, is_playing)

    def _make_hover_slider(self, slider_widget):
        """Wrap slider in a box; reveal handle on box hover."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.set_hexpand(True)
        box.append(slider_widget)
        motion = Gtk.EventControllerMotion.new()
        motion.connect(
            'enter',
            lambda *_: slider_widget.add_css_class('slider-hovered')
        )
        motion.connect(
            'leave',
            lambda *_: slider_widget.remove_css_class('slider-hovered')
        )
        box.add_controller(motion)
        return box

    def build_popover(self, widget, data):
        """ Build feishin popover """
        main_box = c.box('v', spacing=10, style='small-widget')

        widget.pop_player_name = c.label('Feishin', style='heading')
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
            '', style='large-text', va='center', ha='center', he=True)
        widget.pop_art_placeholder.set_size_request(art_size, art_size)

        art_container.append(widget.pop_art)
        art_container.append(widget.pop_art_placeholder)

        art_overlay = Gtk.Overlay()
        art_overlay.set_halign(Gtk.Align.CENTER)
        art_overlay.set_child(art_container)

        if self.show_visualizer:
            viz_height = int(art_size * (self.visualizer_height / 100))
            widget.pop_vis_bg = VisualizerBG(height=viz_height)
            widget.pop_vis_bg_revealer = Gtk.Revealer()
            widget.pop_vis_bg_revealer.set_transition_type(
                Gtk.RevealerTransitionType.CROSSFADE
            )
            widget.pop_vis_bg_revealer.set_transition_duration(500)
            widget.pop_vis_bg_revealer.set_child(widget.pop_vis_bg)
            widget.pop_vis_bg_revealer.set_valign(Gtk.Align.END)
            widget.pop_vis_bg_revealer.set_halign(Gtk.Align.FILL)
            art_overlay.add_overlay(widget.pop_vis_bg_revealer)

            widget.pop_visualizer = Visualizer(
                art_size, height=viz_height,
                audio_capture=self._audio_capture)
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
        widget.pop_playcount = c.label(
            f"Plays: {data.get('play_count', 0)}", style='play-count')

        content_box.append(widget.pop_song)
        content_box.append(widget.pop_artist)

        seek_box = c.box('v')
        widget.pop_seekbar = c.slider(data.get('percent', 0), scrollable=False)
        widget.pop_seekbar.get_style_context().add_class('mpris-slider')
        widget.pop_seekbar.set_hexpand(True)

        def on_seek(s):
            song = self.state.get('song')
            length = song.get('duration', 0) if song else 0
            if length > 0:
                target = int((s.get_value() / 100) * (length / 1000))
                self.set_position(target)

        widget.pop_seekbar_handler = widget.pop_seekbar.connect(
            'value-changed', on_seek)
        seek_box.append(self._make_hover_slider(widget.pop_seekbar))

        pos = data.get('position_str', '00:00')
        length = data.get('length_str', '00:00')
        widget.pop_time = c.label(
            f"{pos} / {length}", style='music-time', ha='center', he=True)
        content_box.append(seek_box)

        ctrl_box = Gtk.CenterBox()
        ctrl_box.set_hexpand(True)

        prev_btn = c.button('', style='music-button')
        prev_btn.set_valign(Gtk.Align.FILL)
        prev_btn.connect('clicked', lambda *_a: self.prev_track())

        widget.pop_play_btn = c.button(
            '' if data.get('status') == 'playing' else '',
            style='music-button')
        c.add_style(widget.pop_play_btn, 'play-button')
        widget.pop_play_btn.set_valign(Gtk.Align.FILL)
        widget.pop_play_btn.connect('clicked', lambda *_a: self.toggle_play())

        next_btn = c.button('', style='music-button')
        next_btn.set_valign(Gtk.Align.FILL)
        next_btn.connect('clicked', lambda *_a: self.next_track())

        vol_box = c.box('h', spacing=5)
        vol_box.set_hexpand(True)
        widget.pop_volume = c.slider(
                data.get('volume', 0), scrollable=True,
                style='music-volume')
        widget.pop_volume.get_style_context().add_class('mpris-slider')

        def on_volume(s):
            self.set_volume(int(s.get_value()))

        widget.pop_volume_handler = widget.pop_volume.connect(
            'value-changed', on_volume)
        widget.pop_volume.set_hexpand(True)
        vol_box.append(self._make_hover_slider(widget.pop_volume))

        btn_box = c.box('h')
        btn_box.append(prev_btn)
        btn_box.append(widget.pop_play_btn)
        btn_box.append(next_btn)

        ctrl_box.set_start_widget(widget.pop_time)
        ctrl_box.set_end_widget(vol_box)
        ctrl_box.set_center_widget(btn_box)

        content_box.append(ctrl_box)

        # Toggle row: play count left, icons centered
        toggle_box = Gtk.CenterBox()
        toggle_box.set_hexpand(True)

        widget.pop_playcount.set_halign(Gtk.Align.START)
        toggle_box.set_start_widget(widget.pop_playcount)

        toggle_icons = c.box('h', spacing=5)
        toggle_icons.set_halign(Gtk.Align.CENTER)

        widget.pop_shuffle_btn = c.button('', style='toggle-button')
        widget.pop_shuffle_btn.set_tooltip_text('Shuffle')
        widget.pop_shuffle_btn.connect(
            'clicked', lambda *_a: self.toggle_shuffle())

        widget.pop_repeat_btn = c.button('\uf363', style='toggle-button')
        widget.pop_repeat_btn.set_tooltip_text('Repeat')
        widget.pop_repeat_btn.connect(
            'clicked', lambda *_a: self.toggle_repeat())

        repeat_overlay = Gtk.Overlay()
        repeat_overlay.set_child(widget.pop_repeat_btn)
        widget.pop_repeat_badge = c.label(
            '1', style='repeat-badge', ha='end', va='end')
        widget.pop_repeat_badge.set_halign(Gtk.Align.END)
        widget.pop_repeat_badge.set_valign(Gtk.Align.START)
        widget.pop_repeat_badge.set_visible(False)
        repeat_overlay.add_overlay(widget.pop_repeat_badge)

        widget.pop_fav_btn = c.button('', style='toggle-button')
        widget.pop_fav_btn.set_tooltip_text('Favorite')
        widget.pop_fav_btn.connect(
            'clicked', lambda *_a: self.toggle_favorite())

        toggle_icons.append(widget.pop_shuffle_btn)
        toggle_icons.append(repeat_overlay)
        toggle_icons.append(widget.pop_fav_btn)

        toggle_box.set_center_widget(toggle_icons)

        content_box.append(toggle_box)
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
            volume = self.state.get('volume', 0)
            step = 5
            if dy > 0:
                new_vol = max(0, volume - step)
            else:
                new_vol = min(100, volume + step)
            self.set_volume(new_vol)
            return True

        scroll.connect('scroll', on_scroll)
        m.add_controller(scroll)

        click = Gtk.GestureClick()
        click.set_button(3)

        def on_right_click(_gesture, _n_press, _x, _y):
            self.toggle_play()

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

        if not widget.popover_built:
            widget.set_widget(self.build_popover(widget, data))
            widget.popover_built = True
            self._track_popover_visibility(widget)
        else:
            try:
                self.update_popover_widgets(widget, data)
            except Exception as e:
                c.print_debug(f"Failed to update feishin popover: {e}",
                              color='red')


module_map = {
    'feishin': Feishin
}
