#!/usr/bin/python3 -u
"""
Description: MPC module refactored for unified state with album art
Author: thnikk
"""
import common as c
import os
import hashlib
from subprocess import run, DEVNULL, Popen
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf  # noqa

CACHE_DIR = os.path.expanduser('~/.cache/pybar')


class MPC(c.BaseModule):
    SCHEMA = {
        'art_size': {
            'type': 'integer',
            'default': 300,
            'label': 'Album Art Size',
            'description': 'Size of album art in popover (pixels)',
            'min': 100,
            'max': 500
        }
    }

    def get_mpc_status(self):
        try:
            # Get status and current song info
            output = run(
                ['mpc', 'status', '-f', '%artist%@@@%title%@@@%file%'],
                capture_output=True, check=True
            ).stdout.decode('utf-8').splitlines()

            if len(output) < 2:
                return {
                    "status": "stopped", "song": "Stopped",
                    "artist": "", "file": "", "art": None}

            info_line = output[0]
            status_line = output[1]

            parts = info_line.split('@@@')
            artist = parts[0] if len(parts) > 0 else ""
            song = parts[1] if len(parts) > 1 else ""
            file_path = parts[2] if len(parts) > 2 else ""

            if not song and file_path:
                song = os.path.basename(file_path)
            if not song:
                song = "Stopped" if "stopped" in status_line else "Unknown"

            status = status_line.split(']')[0].lstrip('[')

            # Extract percentage for seekbar
            percent = 0
            if '(' in status_line and '%)' in status_line:
                try:
                    percent = int(status_line.split('(')[1].split('%')[0])
                except ValueError:
                    pass

            # Try to extract album art
            art_path = None
            if file_path:
                if not os.path.exists(CACHE_DIR):
                    os.makedirs(CACHE_DIR, exist_ok=True)

                art_filename = \
                    f"mpc_{hashlib.md5(file_path.encode()).hexdigest()}.jpg"
                art_path = os.path.join(CACHE_DIR, art_filename)

                if not os.path.exists(art_path):
                    try:
                        # Clear old art files to save space
                        for f in os.listdir(CACHE_DIR):
                            if f.startswith('mpc_') and f.endswith('.jpg'):
                                os.remove(os.path.join(CACHE_DIR, f))

                        res = run(['mpc', 'readpicture', file_path],
                                  capture_output=True)
                        if res.returncode == 0 and res.stdout:
                            with open(art_path, 'wb') as f:
                                f.write(res.stdout)
                        else:
                            art_path = None
                    except Exception:
                        art_path = None

            return {
                "status": status,
                "song": song,
                "artist": artist,
                "file": file_path,
                "art": art_path,
                "percent": percent,
                "text": song
            }
        except Exception as e:
            c.print_debug(f"MPC status error: {e}", color='red')
            return {}

    def fetch_data(self):
        return self.get_mpc_status()

    def run_worker(self):
        """ Background worker for mpc """
        def update():
            data = self.fetch_data()
            if data:
                c.state_manager.update(self.name, data)

        update()
        while True:
            try:
                # mpc idle waits for player events
                run(['mpc', 'idle', 'player'],
                    stdout=DEVNULL, stderr=DEVNULL, timeout=5)
                update()
            except Exception:
                update()

    def update_popover_widgets(self, widget, data):
        """ Update existing popover widgets """
        # Update Art
        art_path = data.get('art')
        last_art = getattr(widget, 'last_art_path', None)

        if hasattr(widget, 'pop_art') and art_path != last_art:
            widget.last_art_path = art_path
            if art_path and os.path.exists(art_path):
                try:
                    art_size = 300
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
            # Block signals to avoid feedback loop
            widget.pop_seekbar.handler_block(widget.pop_seekbar_handler)
            widget.pop_seekbar.set_value(data.get('percent', 0))
            widget.pop_seekbar.handler_unblock(widget.pop_seekbar_handler)

        # Update play/pause button
        if hasattr(widget, 'pop_play_btn'):
            label = '' if data.get('status') == 'playing' else ''
            if widget.pop_play_btn.get_label() != label:
                widget.pop_play_btn.set_label(label)

    def build_popover(self, widget, data):
        """ Build mpc popover """
        main_box = c.box('v', spacing=20, style='small-widget')

        art_size = 300
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
            data.get('song', 'Unknown Song'), length=20, style='title')
        widget.pop_artist = c.label(
                data.get('artist', ''), style='artist', wrap=20)
        widget.pop_artist.set_visible(bool(data.get('artist')))

        content_box.append(widget.pop_song)
        content_box.append(widget.pop_artist)

        # Seekbar
        widget.pop_seekbar = c.slider(data.get('percent', 0), scrollable=False)
        widget.pop_seekbar_handler = widget.pop_seekbar.connect(
            'value-changed', lambda s: run(
                ['mpc', 'seek', f"{int(s.get_value())}%"]))
        content_box.append(widget.pop_seekbar)

        # Controls
        ctrl_box = c.box('h')
        ctrl_box.set_halign(Gtk.Align.CENTER)

        def mpc_cmd(_btn, cmd):
            Popen(['mpc', cmd], stdout=DEVNULL, stderr=DEVNULL)

        prev_btn = c.button('', style='music-button')
        prev_btn.set_valign(Gtk.Align.FILL)
        prev_btn.connect('clicked', mpc_cmd, 'prev')

        widget.pop_play_btn = c.button(
            '' if data.get('status') == 'playing' else '',
            style='music-button')
        c.add_style(widget.pop_play_btn, 'play-button')
        widget.pop_play_btn.set_valign(Gtk.Align.FILL)
        widget.pop_play_btn.connect('clicked', mpc_cmd, 'toggle')

        next_btn = c.button('', style='music-button')
        next_btn.set_valign(Gtk.Align.FILL)
        next_btn.connect('clicked', mpc_cmd, 'next')

        ctrl_box.append(prev_btn)
        ctrl_box.append(widget.pop_play_btn)
        ctrl_box.append(next_btn)

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

        widget.set_label(data.get('song', 'Stopped'))
        widget.set_visible(True)

        # Update popover content
        if not widget.popover_built:
            widget.set_widget(self.build_popover(widget, data))
            widget.popover_built = True
        else:
            try:
                self.update_popover_widgets(widget, data)
            except Exception as e:
                c.print_debug(f"Failed to update mpc popover: {e}", color='red')


module_map = {
    'mpc': MPC
}
