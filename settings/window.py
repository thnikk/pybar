#!/usr/bin/python3 -u
"""
Description: Settings window - runs as separate GTK application
Author: thnikk
"""
import sys
import os

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, Gio, Adw

import config as Config

SETTINGS_CSS = """
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


class SettingsWindow(Adw.PreferencesWindow):
    """Main settings window with libadwaita preferences"""

    def __init__(self, app, config, config_path):
        super().__init__(application=app)
        self.set_title('Pybar Settings')
        self.config = config.copy()
        self.config_path = config_path
        self.pending_changes = {}
        self.module_changes = {}
        self.has_changes = False

        self._load_css()

        general_page = self._create_general_page()
        self.add(general_page)

        modules_page = self._create_modules_page()
        self.add(modules_page)

        appearance_page = self._create_appearance_page()
        self.add(appearance_page)

        self.connect('close-request', self._on_close_request)

    def _create_general_page(self):
        """Create general settings page"""
        page = Adw.PreferencesPage()
        page.set_title('General')
        page.set_icon_name('preferences-system-symbolic')

        self.general_tab = GeneralTab(self.config, self._on_change)
        page.add(self.general_tab)

        return page

    def _create_modules_page(self):
        """Create modules page"""
        page = Adw.PreferencesPage()
        page.set_title('Modules')
        page.set_icon_name('application-x-addon-symbolic')

        self.modules_tab = ModulesTab(self.config, self._on_change)
        page.add(self.modules_tab)

        return page

    def _create_appearance_page(self):
        """Create appearance page"""
        page = Adw.PreferencesPage()
        page.set_title('Appearance')
        page.set_icon_name('preferences-desktop-theme-symbolic')

        self.appearance_tab = AppearanceTab(self.config, self._on_change)
        page.add(self.appearance_tab)

        return page

    def _on_change(self, key, value, module_name=None):
        """Handle setting change from any tab"""
        if key == '__layout__':
            for section, modules in value.items():
                self.pending_changes[section] = modules
        elif module_name:
            if module_name not in self.module_changes:
                self.module_changes[module_name] = {}
            self.module_changes[module_name][key] = value
        else:
            self.pending_changes[key] = value

        self.has_changes = True
        self._save_config()

    def _save_config(self):
        """Save configuration to disk"""
        for key, value in self.pending_changes.items():
            if value is None:
                self.config.pop(key, None)
            else:
                self.config[key] = value

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

        try:
            Config.save(self.config_path, self.config)
            self.pending_changes.clear()
            self.module_changes.clear()
            self.has_changes = False
            self._show_toast('Saved - restart pybar to apply changes')
        except Exception as e:
            self._show_toast(f'Save failed: {e}')

    def _show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.add_toast(toast)

    def _on_close_request(self, _):
        """Handle window close request"""
        return False

    def _load_css(self):
        """Load custom CSS for settings window"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(SETTINGS_CSS.encode())
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


class SettingsApplication(Adw.Application):
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
