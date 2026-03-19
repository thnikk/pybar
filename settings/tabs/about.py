#!/usr/bin/python3 -u
"""
Description: About tab for settings window
Author: thnikk
"""
import os
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, Gdk  # noqa
import version
import common as c


class AboutTab(Gtk.Box):
    """About tab showing app metadata"""

    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=20
        )
        self.set_focusable(True)
        self.connect('map', lambda _: self.grab_focus())

        # Register assets dir so the icon theme can find pybar-icon.svg
        icon_dir = os.path.dirname(
            c.get_resource_path(
                os.path.join("assets", "pybar-logo-dark.svg"))
        )
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(icon_dir)

        # App icon
        icon = Gtk.Image.new_from_icon_name("pybar-logo-dark")
        icon.set_pixel_size(200)
        icon.set_margin_top(8)
        self.append(icon)

        group = Adw.PreferencesGroup()
        self.append(group)

        # Version row
        ver_row = Adw.ActionRow()
        ver_row.set_title('Version')
        ver_row.set_subtitle(version.get_version())
        group.add(ver_row)

        # Developer row
        dev_row = Adw.ActionRow()
        dev_row.set_title('Developer')
        dev_row.set_subtitle('thnikk')
        group.add(dev_row)

        # License row
        lic_row = Adw.ActionRow()
        lic_row.set_title('License')
        lic_row.set_subtitle('MIT')
        group.add(lic_row)

        links_group = Adw.PreferencesGroup()
        links_group.set_title('Links')
        self.append(links_group)

        # Website row
        web_row = Adw.ActionRow()
        web_row.set_title('Website')
        web_row.set_subtitle('https://github.com/thnikk/pybar')
        web_row.set_activatable(True)
        web_row.connect(
            'activated',
            lambda _: Gio.AppInfo.launch_default_for_uri(
                'https://github.com/thnikk/pybar', None
            )
        )
        web_row.add_suffix(
            Gtk.Image.new_from_icon_name('go-next-symbolic')
        )
        links_group.add(web_row)

        # Issues row
        issue_row = Adw.ActionRow()
        issue_row.set_title('Report an Issue')
        issue_row.set_subtitle(
            'https://github.com/thnikk/pybar/issues'
        )
        issue_row.set_activatable(True)
        issue_row.connect(
            'activated',
            lambda _: Gio.AppInfo.launch_default_for_uri(
                'https://github.com/thnikk/pybar/issues', None
            )
        )
        issue_row.add_suffix(
            Gtk.Image.new_from_icon_name('go-next-symbolic')
        )
        links_group.add(issue_row)
