#!/usr/bin/python3 -u
"""
Description: MPC module refactored for unified state with album art
Author: thnikk
"""
import os
import hashlib
from subprocess import run, DEVNULL, Popen
import time
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, Pango, GdkPixbuf  # noqa
import common as c

CACHE_DIR = os.path.expanduser('~/.cache/pybar')
ART_PATH = os.path.join(CACHE_DIR, 'mpc_art.jpg')

def get_mpc_status():
    try:
        # Get status and current song info
        output = run(['mpc', 'status', '-f', '%artist%@@@%title%@@@%file%'], 
                     capture_output=True, check=True).stdout.decode('utf-8').splitlines()
        
        if len(output) < 2:
            return {"status": "stopped", "song": "Stopped", "artist": "", "file": "", "art": None}
            
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
            art_filename = f"mpc_{hashlib.md5(file_path.encode()).hexdigest()}.jpg"
            art_path = os.path.join(CACHE_DIR, art_filename)
            
            if not os.path.exists(art_path):
                try:
                    # Clear old art files to save space
                    for f in os.listdir(CACHE_DIR):
                        if f.startswith('mpc_') and f.endswith('.jpg'):
                            os.remove(os.path.join(CACHE_DIR, f))
                            
                    res = run(['mpc', 'readpicture', file_path], capture_output=True)
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
            res = run(['mpc', 'idle', 'player'], stdout=DEVNULL, stderr=DEVNULL, timeout=5)
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
    
    # Check if we need to rebuild the popover
    current_song = getattr(module, 'current_song', None)
    current_status = getattr(module, 'current_status', None)
    
    # If the popover is active (open), we DON'T want to call set_widget
    # because that would replace the popover while the user is using it.
    # We only rebuild it if it's NOT active and something changed.
    # HOWEVER, if the song changed, we MUST rebuild it or it shows old info.
    if not module.get_active() or song != current_song:
        if song != current_song or status != current_status:
            try:
                popover_content = build_popover(module, data)
                module.set_widget(popover_content)
                module.current_song = song
                module.current_status = status
            except Exception as e:
                c.print_debug(f"MPC popover build failed: {e}", color='red')

def build_popover(module, data):
    """ Build mpc popover """
    main_box = c.box('v', spacing=20, style='small-widget')
    
    # Album Art - Reduced size
    art_size = 300
    art_path = data.get('art')
    if art_path and os.path.exists(art_path):
        # Use a box to contain the image and handle rounding/clipping
        art_container = c.box('v', style='cover-art')
        art_container.set_size_request(art_size, art_size)
        art_container.set_overflow(Gtk.Overflow.HIDDEN)
        art_container.set_halign(Gtk.Align.CENTER)
        art_container.set_valign(Gtk.Align.CENTER)
        art_container.set_hexpand(False)
        art_container.set_vexpand(False)
        
        try:
            # Use GdkPixbuf and Gdk.Texture for absolute size control in GTK4
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(art_path, art_size, art_size, True)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            art = Gtk.Image.new_from_paintable(texture)
            art.set_pixel_size(art_size)
            art.set_hexpand(False)
            art.set_vexpand(False)
            art.set_halign(Gtk.Align.CENTER)
            art.set_valign(Gtk.Align.CENTER)
            
            art_container.append(art)
            main_box.append(art_container)
        except Exception as e:
            c.print_debug(f"Failed to load art image with Gtk.Image: {e}", color='yellow')
    else:
        placeholder = c.box('v', style='cover-art box')
        placeholder.set_size_request(art_size, art_size)
        placeholder.set_hexpand(False)
        placeholder.set_vexpand(False)
        placeholder.append(c.label('', style='large-text', va='center', ha='center', he=True))
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.set_valign(Gtk.Align.CENTER)
        main_box.append(placeholder)


    # Track info
    info_box = c.box('v', spacing=5)
    info_box.append(c.label(data.get('song', 'Unknown Song'), style='heading', length=20))
    if data.get('artist'):
        info_box.append(c.label(data['artist'], style='title', wrap=20))
    main_box.append(info_box)

    # Seekbar
    seekbar = c.slider(data.get('percent', 0), scrollable=False)
    seekbar.connect('value-changed', lambda s: run(['mpc', 'seek', f"{int(s.get_value())}%"]))
    main_box.append(seekbar)

    # Controls
    ctrl_box = c.box('h', style='mpc-controls')
    ctrl_box.set_halign(Gtk.Align.CENTER)
    
    def mpc_cmd(btn, cmd):
        Popen(['mpc', cmd])

    prev_btn = c.button('')
    prev_btn.set_valign(Gtk.Align.FILL)
    prev_btn.connect('clicked', mpc_cmd, 'prev')
    
    play_btn = c.button('' if data.get('status') == 'playing' else '')
    play_btn.set_valign(Gtk.Align.FILL)
    play_btn.connect('clicked', mpc_cmd, 'toggle')
    
    next_btn = c.button('')
    next_btn.set_valign(Gtk.Align.FILL)
    next_btn.connect('clicked', mpc_cmd, 'next')
    
    s1 = c.sep('v')
    s1.set_valign(Gtk.Align.FILL)
    s2 = c.sep('v')
    s2.set_valign(Gtk.Align.FILL)
    
    ctrl_box.append(prev_btn)
    ctrl_box.append(s1)
    ctrl_box.append(play_btn)
    ctrl_box.append(s2)
    ctrl_box.append(next_btn)
        
    main_box.append(ctrl_box)
    
    return main_box
