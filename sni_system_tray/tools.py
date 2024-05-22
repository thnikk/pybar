#!/usr/bin/env python3

import os
import sys
import gi

gi.require_version('GdkPixbuf', '2.0')
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')

from gi.repository import Gtk, Gdk, GdkPixbuf


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def check_key(dictionary, key, default_value):
    """
    Adds a key w/ default value if missing from the dictionary
    """
    if key not in dictionary:
        dictionary[key] = default_value


def create_pixbuf(icon_name, icon_size, icons_path="", fallback=True):
    try:
        # In case a full path was given
        if icon_name.startswith("/"):
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_name, icon_size, icon_size)
        else:
            icon_theme = Gtk.IconTheme.get_default()
            if icons_path:
                search_path = icon_theme.get_search_path()
                search_path.append(icons_path)
                icon_theme.set_search_path(search_path)

            try:
                if icons_path:
                    path = "{}/{}.svg".format(icons_path, icon_name)
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        path, icon_size, icon_size)
                else:
                    raise ValueError("icons_path not supplied.")
            except:
                try:
                    pixbuf = icon_theme.load_icon(
                        icon_name, icon_size,
                        Gtk.IconLookupFlags.FORCE_SIZE)
                except:
                    pixbuf = icon_theme.load_icon(
                        icon_name.lower(), icon_size,
                        Gtk.IconLookupFlags.FORCE_SIZE)
    except Exception as e:
        if fallback:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                os.path.join(
                    get_config_dir(), "icons_light/icon-missing.svg"),
                icon_size, icon_size)
        else:
            raise e
    return pixbuf


def get_config_dir():
    """
    Determine config dir path, create if not found, then create sub-dirs
    :return: config dir path
    """
    xdg_config_home = os.getenv('XDG_CONFIG_HOME')
    config_home = xdg_config_home if xdg_config_home else os.path.join(
        os.getenv("HOME"), ".config")
    config_dir = os.path.join(config_home, "nwg-panel")
    if not os.path.isdir(config_dir):
        print("Creating '{}'".format(config_dir))
        os.makedirs(config_dir, exist_ok=True)

    # Icon folders to store user-defined icon replacements
    folder = os.path.join(config_dir, "icons_light")
    if not os.path.isdir(folder):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "icons_dark")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "icons_color")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    folder = os.path.join(config_dir, "executors")
    if not os.path.isdir(os.path.join(folder)):
        print("Creating '{}'".format(folder))
        os.makedirs(folder, exist_ok=True)

    return config_dir
