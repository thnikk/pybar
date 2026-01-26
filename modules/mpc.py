#!/usr/bin/python3 -u
"""
Description: MPC module refactored for unified state with album art
Author: thnikk
"""
import common as c
import os
import hashlib
from subprocess import run, DEVNULL, Popen
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf  # noqa

CACHE_DIR = os.path.expanduser('~/.cache/pybar')
ART_PATH = os.path.join(CACHE_DIR, 'mpc_art.jpg')


def get_mpc_status():
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

            # Use a unique filename for the art to avoid GTK caching issues
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
        return None


def run_worker(name, config):
    """ Background worker for mpc """
    def update():
        data = get_mpc_status()
        if data:
            c.state_manager.update(name, data)

    update()
    while True:
        try:
            # mpc idle waits for player events
            # Also poll periodically for seekbar updates if playing
            run(['mpc', 'idle', 'player'],
                stdout=DEVNULL, stderr=DEVNULL, timeout=5)
            update()
        except Exception:
            # Timeout or error, just update and loop
            update()


def create_widget(bar, config):
    module = c.Module()
    module.set_position(bar.position)
    # Ensure text label is configured for truncation
    if module.text:
        module.text.set_max_width_chars(20)
        module.text.set_ellipsize(Pango.EllipsizeMode.END)
    module.set_visible(False)
    return module


def update_ui(module, data):
    if not data:
        module.set_visible(False)
        return

    status = data.get('status', 'stopped')
    if status == 'playing':
        module.set_icon('')
    elif status == 'paused':
        module.set_icon('')
    else:
        module.set_icon('')

    song = data.get('song', 'Stopped')
    module.set_label(song)
    module.set_visible(True)

    # Update popover content
    if not hasattr(module, 'popover_built'):
        module.set_widget(build_popover(module, data))
        module.popover_built = True
    else:
        try:
            update_popover(module, data)
        except Exception as e:
            c.print_debug(f"Failed to update mpc popover: {e}", color='red')


def update_popover(module, data):
    """ Update existing popover widgets """
    # Update Art
    art_path = data.get('art')
    last_art = getattr(module, 'last_art_path', None)

    if hasattr(module, 'pop_art') and art_path != last_art:
        module.last_art_path = art_path
        if art_path and os.path.exists(art_path):
            try:
                art_size = 300
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    art_path, art_size, art_size, True)
                texture = Gdk.Texture.new_for_pixbuf(pixbuf)
                module.pop_art.set_from_paintable(texture)
                module.pop_art.set_visible(True)
                if hasattr(module, 'pop_art_placeholder'):
                    module.pop_art_placeholder.set_visible(False)
            except Exception:
                pass
        else:
            module.pop_art.set_visible(False)
            if hasattr(module, 'pop_art_placeholder'):
                module.pop_art_placeholder.set_visible(True)

    # Update labels
    song = data.get('song', 'Unknown Song')
    artist = data.get('artist', '')

    if hasattr(module, 'pop_song') and module.pop_song.get_text() != song:
        module.pop_song.set_text(song)
    if hasattr(module, 'pop_artist'):
        if module.pop_artist.get_text() != artist:
            module.pop_artist.set_text(artist)
        module.pop_artist.set_visible(bool(artist))

    # Update seekbar
    if hasattr(module, 'pop_seekbar'):
        # Block signals to avoid feedback loop while updating value
        module.pop_seekbar.handler_block(module.pop_seekbar_handler)
        module.pop_seekbar.set_value(data.get('percent', 0))
        module.pop_seekbar.handler_unblock(module.pop_seekbar_handler)

    # Update play/pause button
    if hasattr(module, 'pop_play_btn'):
        label = '' if data.get('status') == 'playing' else ''
        if module.pop_play_btn.get_label() != label:
            module.pop_play_btn.set_label(label)


def build_popover(module, data):
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
    module.pop_art = Gtk.Image()
    module.pop_art.set_pixel_size(art_size)

    # Placeholder
    module.pop_art_placeholder = c.label(
        '', style='large-text', va='center', ha='center', he=True)
    module.pop_art_placeholder.set_size_request(art_size, art_size)

    art_container.append(module.pop_art)
    art_container.append(module.pop_art_placeholder)
    main_box.append(art_container)

    # Initial art load
    if art_path and os.path.exists(art_path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                art_path, art_size, art_size, True)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            module.pop_art.set_from_paintable(texture)
            module.pop_art_placeholder.set_visible(False)
        except Exception:
            module.pop_art.set_visible(False)
    else:
        module.pop_art.set_visible(False)

    # Track info
    info_box = c.box('v', spacing=5)
    module.pop_song = c.label(
        data.get('song', 'Unknown Song'), style='heading', length=20)
    module.pop_artist = c.label(data.get('artist', ''), style='title', wrap=20)
    module.pop_artist.set_visible(bool(data.get('artist')))

    info_box.append(module.pop_song)
    info_box.append(module.pop_artist)
    main_box.append(info_box)

    # Seekbar
    module.pop_seekbar = c.slider(data.get('percent', 0), scrollable=False)
    module.pop_seekbar_handler = module.pop_seekbar.connect(
        'value-changed', lambda s: run(
            ['mpc', 'seek', f"{int(s.get_value())}%"]))
    main_box.append(module.pop_seekbar)

    # Controls
    ctrl_box = c.box('h', style='mpc-controls')
    ctrl_box.set_halign(Gtk.Align.CENTER)

    def mpc_cmd(btn, cmd):
        Popen(['mpc', cmd])

    prev_btn = c.button('')
    prev_btn.set_valign(Gtk.Align.FILL)
    prev_btn.connect('clicked', mpc_cmd, 'prev')

    module.pop_play_btn = c.button(
        '' if data.get('status') == 'playing' else '')
    module.pop_play_btn.set_valign(Gtk.Align.FILL)
    module.pop_play_btn.connect('clicked', mpc_cmd, 'toggle')

    next_btn = c.button('')
    next_btn.set_valign(Gtk.Align.FILL)
    next_btn.connect('clicked', mpc_cmd, 'next')

    s1 = c.sep('v')
    s1.set_valign(Gtk.Align.FILL)
    s2 = c.sep('v')
    s2.set_valign(Gtk.Align.FILL)

    ctrl_box.append(prev_btn)
    ctrl_box.append(s1)
    ctrl_box.append(module.pop_play_btn)
    ctrl_box.append(s2)
    ctrl_box.append(next_btn)

    main_box.append(ctrl_box)

    return main_box
