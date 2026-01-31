#!/usr/bin/python3 -u
"""
Description: Settings window - runs as separate GTK application
Author: thnikk
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio  # noqa

import config as Config

SETTINGS_CSS = """
.heading {
    font-weight: bold;
    font-size: 1.1em;
}

.title {
    font-weight: bold;
}

.module-chip {
    padding: 4px 8px;
    border-radius: 6px;
    min-height: 20px;
    background: alpha(@theme_fg_color, 0.08);
    border: 1px solid alpha(@theme_fg_color, 0.15);
}

.module-chip:hover {
    background: alpha(@theme_fg_color, 0.12);
}

.module-chip button {
    min-width: 14px;
    min-height: 14px;
    padding: 0;
    margin-left: 4px;
}

.module-add-btn {
    padding: 4px 10px;
}

.section-frame {
    min-height: 36px;
}

.section-frame.drop-target {
    background: alpha(@theme_selected_bg_color, 0.15);
}

.drop-indicator {
    background: @theme_selected_bg_color;
    border-radius: 2px;
    min-width: 3px;
    min-height: 24px;
    margin-left: 2px;
    margin-right: 2px;
}

.dim-label {
    opacity: 0.6;
}

.section-scroll {
    background: transparent;
}

.section-scroll scrollbar {
    opacity: 0;
}

.section-scroll:hover scrollbar {
    opacity: 1;
}

.error {
    color: @error_color;
}

entry.error {
    border-color: @error_color;
}
"""
from settings.tabs.general import GeneralTab
from settings.tabs.modules import ModulesTab
from settings.tabs.appearance import AppearanceTab


class SettingsWindow(Gtk.ApplicationWindow):
    """Main settings window with tabbed interface"""

    def __init__(self, app, config, config_path):
        super().__init__(application=app, title='Pybar Settings')
        self.set_default_size(750, 600)
        self.config = config.copy()
        self.config_path = config_path
        self.pending_changes = {}
        self.module_changes = {}

        # Load CSS
        self._load_css()

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Gtk.HeaderBar()
        header.set_show_title_buttons(True)
        self.set_titlebar(header)

        # Save button
        self.save_btn = Gtk.Button(label='Save')
        self.save_btn.get_style_context().add_class('suggested-action')
        self.save_btn.connect('clicked', self._on_save)
        self.save_btn.set_sensitive(False)
        header.pack_end(self.save_btn)

        # Reload button
        reload_btn = Gtk.Button()
        reload_btn.set_icon_name('view-refresh-symbolic')
        reload_btn.set_tooltip_text('Reload config from disk')
        reload_btn.connect('clicked', self._on_reload)
        header.pack_start(reload_btn)

        # Notebook (tabbed interface)
        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)

        # Create tabs
        self.general_tab = GeneralTab(self.config, self._on_change)
        self.notebook.append_page(
            self.general_tab, Gtk.Label(label='General'))

        self.modules_tab = ModulesTab(self.config, self._on_change)
        self.notebook.append_page(
            self.modules_tab, Gtk.Label(label='Modules'))

        self.appearance_tab = AppearanceTab(self.config, self._on_change)
        self.notebook.append_page(
            self.appearance_tab, Gtk.Label(label='Appearance'))

        main_box.append(self.notebook)

        # Status bar
        self.status_bar = Gtk.Label(label='')
        self.status_bar.set_halign(Gtk.Align.START)
        self.status_bar.set_margin_start(10)
        self.status_bar.set_margin_end(10)
        self.status_bar.set_margin_top(5)
        self.status_bar.set_margin_bottom(5)
        main_box.append(self.status_bar)

        self.set_child(main_box)

    def _on_change(self, key, value, module_name=None):
        """Handle setting change from any tab"""
        if key == '__layout__':
            # Layout change - value is dict of section -> modules
            for section, modules in value.items():
                self.pending_changes[section] = modules
        elif module_name:
            # Module-specific setting
            if module_name not in self.module_changes:
                self.module_changes[module_name] = {}
            self.module_changes[module_name][key] = value
        else:
            # Global setting
            self.pending_changes[key] = value

        self.save_btn.set_sensitive(True)
        self.status_bar.set_text('Unsaved changes')

    def _on_save(self, _):
        """Save configuration to disk"""
        # Apply pending changes to config
        for key, value in self.pending_changes.items():
            if value is None:
                self.config.pop(key, None)
            else:
                self.config[key] = value

        # Apply module changes
        if 'modules' not in self.config:
            self.config['modules'] = {}
        for module_name, changes in self.module_changes.items():
            if module_name not in self.config['modules']:
                self.config['modules'][module_name] = {}
            for key, value in changes.items():
                if value is None:
                    self.config['modules'][module_name].pop(key, None)
                else:
                    self.config['modules'][module_name][key] = value

        # Save to disk
        try:
            Config.save(self.config_path, self.config)
            self.pending_changes.clear()
            self.module_changes.clear()
            self.save_btn.set_sensitive(False)
            self.status_bar.set_text('Saved successfully - restart pybar to apply')

        except Exception as e:
            self.status_bar.set_text(f'Save failed: {e}')

    def _on_reload(self, _):
        """Reload config from disk"""
        try:
            self.config = Config.load(self.config_path)
            self.pending_changes.clear()
            self.module_changes.clear()
            self.save_btn.set_sensitive(False)
            self.status_bar.set_text('Reloaded from disk')
            # Rebuild tabs
            self._rebuild_tabs()
        except Exception as e:
            self.status_bar.set_text(f'Reload failed: {e}')

    def _rebuild_tabs(self):
        """Rebuild all tabs with fresh config"""
        # Remove old tabs
        while self.notebook.get_n_pages() > 0:
            self.notebook.remove_page(0)

        # Recreate tabs
        self.general_tab = GeneralTab(self.config, self._on_change)
        self.notebook.append_page(
            self.general_tab, Gtk.Label(label='General'))

        self.modules_tab = ModulesTab(self.config, self._on_change)
        self.notebook.append_page(
            self.modules_tab, Gtk.Label(label='Modules'))

        self.appearance_tab = AppearanceTab(self.config, self._on_change)
        self.notebook.append_page(
            self.appearance_tab, Gtk.Label(label='Appearance'))

    def _load_css(self):
        """Load custom CSS for settings window"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(SETTINGS_CSS.encode())
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class SettingsApplication(Gtk.Application):
    """Separate GTK application for settings window"""

    def __init__(self, config_path):
        super().__init__(
            application_id='org.thnikk.pybar.settings',
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self.config_path = config_path

    def do_activate(self):
        config = Config.load(self.config_path)
        win = SettingsWindow(self, config, self.config_path)
        win.present()


def main():
    if len(sys.argv) < 2:
        print("Usage: window.py <config_path>")
        sys.exit(1)

    config_path = sys.argv[1]
    app = SettingsApplication(config_path)
    app.run([])


if __name__ == '__main__':
    main()
