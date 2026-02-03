#!/usr/bin/python3 -u
"""
Description: Settings window - runs as separate GTK application
Author: thnikk
"""
import sys
import os
import copy

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Gdk, Gio, Adw

import config as Config
from settings.schema import GLOBAL_SCHEMA

SETTINGS_CSS = """
.module-chip {
    padding: 6px 12px;
    border-radius: 8px;
    min-height: 24px;
    font-size: 16px;
    background: alpha(@theme_fg_color, 0.08);
    border: 1px solid alpha(@theme_fg_color, 0.15);
}

.module-chip:hover {
    background: alpha(@theme_fg_color, 0.12);
}

.module-chip button {
    min-width: 16px;
    min-height: 16px;
    padding: 0;
    margin-left: 6px;
}

.section-frame {
    min-height: 48px;
}

.section-frame.drop-target {
    background: alpha(@theme_selected_bg_color, 0.15);
}

.drop-indicator {
    background: @theme_selected_bg_color;
    border-radius: 2px;
    min-width: 3px;
    min-height: 32px;
    margin-left: 3px;
    margin-right: 3px;
}

.drop-indicator-overlay {
    background: @theme_selected_bg_color;
    border-radius: 2px;
    min-width: 4px;
}

.drag-indicator {
    border: 2px dashed alpha(@accent_color, 0.5);
    border-radius: 14px;
    padding: 4px;
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

button.restart-btn {
    background: #4a9d5f;
    color: white;
}

button.restart-btn:hover {
    background: #5cb370;
}
"""
from settings.tabs.general import GeneralTab
from settings.tabs.modules import ModulesTab
from settings.tabs.appearance import AppearanceTab


class SettingsWindow(Adw.ApplicationWindow):
    """Main settings window with libadwaita"""

    def __init__(self, app, config, config_path):
        super().__init__(application=app, title='Pybar Settings')
        self.set_default_size(800, 600)
        self.config = copy.deepcopy(config)
        self.original_config = copy.deepcopy(config)
        self.config_path = config_path
        self._loading = False

        self._load_css()

        header = Adw.HeaderBar()

        inspector_btn = Gtk.Button()
        inspector_icon = Gtk.Image.new_from_icon_name(
            'emblem-system-symbolic'
        )
        inspector_btn.set_child(inspector_icon)
        inspector_btn.add_css_class('flat')
        inspector_btn.set_tooltip_text('Open GTK Inspector')
        inspector_btn.connect('clicked', self._open_inspector)
        header.pack_start(inspector_btn)

        self.restart_btn = Gtk.Button(label='Restart')
        restart_icon = Gtk.Image.new_from_icon_name(
            'view-refresh-symbolic'
        )
        self.restart_btn.set_child(restart_icon)
        self.restart_btn.add_css_class('restart-btn')
        self.restart_btn.set_tooltip_text('Reload pybar')
        self.restart_btn.connect('clicked', self._on_restart)
        header.pack_end(self.restart_btn)

        self.save_btn = Gtk.Button(label='Save')
        self.save_btn.add_css_class('suggested-action')
        self.save_btn.connect('clicked', self._on_save)
        self.save_btn.set_sensitive(False)
        header.pack_end(self.save_btn)

        self.restore_btn = Gtk.Button()
        restore_icon = Gtk.Image.new_from_icon_name('edit-undo-symbolic')
        self.restore_btn.set_child(restore_icon)
        self.restore_btn.set_tooltip_text('Restore original settings')
        self.restore_btn.connect('clicked', self._on_restore)
        self.restore_btn.set_sensitive(False)
        header.pack_end(self.restore_btn)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)

        view_stack = Adw.ViewStack()
        view_stack.connect('notify::visible-child', self._on_tab_changed)

        general_page = Gtk.ScrolledWindow()
        general_page.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        general_page.set_focusable(True)

        general_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        general_box.set_margin_top(24)
        general_box.set_margin_bottom(24)
        general_box.set_margin_start(24)
        general_box.set_margin_end(24)
        self.general_tab = GeneralTab(self.config, self._on_change)
        general_box.append(self.general_tab)
        general_page.set_child(general_box)
        view_stack.add_titled_with_icon(
            general_page, 'general', 'General',
            'preferences-system-symbolic'
        )

        modules_page = Gtk.ScrolledWindow()
        modules_page.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        modules_page.set_focusable(True)

        modules_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        # modules_box.set_margin_top(24)
        # modules_box.set_margin_bottom(24)
        # modules_box.set_margin_start(24)
        # modules_box.set_margin_end(24)
        self.modules_tab = ModulesTab(self.config, self._on_change)
        modules_box.append(self.modules_tab)
        modules_page.set_child(modules_box)
        view_stack.add_titled_with_icon(
            modules_page, 'modules', 'Modules',
            'application-x-addon-symbolic'
        )

        appearance_page = Gtk.ScrolledWindow()
        appearance_page.set_policy(
            Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC
        )
        appearance_page.set_focusable(True)

        appearance_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        appearance_box.set_margin_top(24)
        appearance_box.set_margin_bottom(24)
        appearance_box.set_margin_start(24)
        appearance_box.set_margin_end(24)
        self.appearance_tab = AppearanceTab(self.config, self._on_change)
        appearance_box.append(self.appearance_tab)
        appearance_page.set_child(appearance_box)
        view_stack.add_titled_with_icon(
            appearance_page, 'appearance', 'Appearance',
            'preferences-color-symbolic'
        )

        view_switcher = Adw.ViewSwitcher()
        view_switcher.set_stack(view_stack)
        view_switcher.set_policy(Adw.ViewSwitcherPolicy.WIDE)
        header.set_title_widget(view_switcher)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(view_stack)

        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

        self.connect('close-request', self._on_close_request)

    def _on_tab_changed(self, stack, pspec):
        """Ensure the tab itself gets focus instead of an entry field"""
        child = stack.get_visible_child()
        if child:
            child.grab_focus()

    def _on_change(self, key, value, module_name=None):
        """Handle setting change from any tab"""
        if self._loading:
            return

        if key == '__layout__':
            for section, modules in value.items():
                orig_modules = self.original_config.get(section)
                if modules == orig_modules:
                    if section in self.original_config:
                        self.config[section] = modules
                    else:
                        self.config.pop(section, None)
                else:
                    self.config[section] = modules
        elif module_name:
            if 'modules' not in self.config:
                self.config['modules'] = {}
            if module_name not in self.config['modules']:
                self.config['modules'][module_name] = {}

            # Check against original module config
            orig_modules = self.original_config.get('modules', {})
            orig_module_conf = orig_modules.get(module_name, {})
            
            if value == orig_module_conf.get(key):
                if key in orig_module_conf:
                    self.config['modules'][module_name][key] = value
                else:
                    self.config['modules'][module_name].pop(key, None)
            else:
                if value is None:
                    self.config['modules'][module_name].pop(key, None)
                else:
                    self.config['modules'][module_name][key] = value

            # Cleanup module entry if it matches original state or is empty
            if not self.config['modules'][module_name]:
                if module_name not in orig_modules:
                    del self.config['modules'][module_name]
        else:
            # Global setting
            schema_field = GLOBAL_SCHEMA.get(key, {})
            default = schema_field.get('default')
            orig_val = self.original_config.get(key, default)
            
            # Ensure we compare as strings if they look like strings
            val_comp = str(value) if value is not None else None
            orig_comp = str(orig_val) if orig_val is not None else None
            
            if val_comp == orig_comp:
                if key in self.original_config:
                    self.config[key] = value
                else:
                    self.config.pop(key, None)
            else:
                if value is None:
                    self.config.pop(key, None)
                else:
                    self.config[key] = value

        # Final cleanup for empty 'modules' dict
        if 'modules' in self.config:
            # Ensure any completely unused modules are removed
            used_modules = set()
            for s in ['modules-left', 'modules-center', 'modules-right']:
                used_modules.update(self.config.get(s, []))

            for m in list(self.config['modules'].keys()):
                if m not in used_modules:
                    orig_modules = self.original_config.get('modules', {})
                    if m not in orig_modules:
                        del self.config['modules'][m]

            # If modules dict is now empty and wasn't there originally, remove it
            if not self.config['modules'] and 'modules' not in self.original_config:
                del self.config['modules']

        self._update_button_sensitivity()

    def _update_button_sensitivity(self):
        """Update sensitivity of Save and Restore buttons"""
        # Create clean copies for comparison (ignore None and ensure same types)
        def clean(d):
            if not isinstance(d, dict): return d
            return {k: clean(v) for k, v in d.items() if v is not None}
            
        changed = clean(self.config) != clean(self.original_config)
        self.save_btn.set_sensitive(changed)
        self.restore_btn.set_sensitive(changed)

    def _open_inspector(self, _):
        """Open GTK inspector for debugging"""
        self.set_interactive_debugging(True)

    def _on_save(self, _):
        """Save configuration to disk"""
        try:
            self._loading = True
            Config.save(self.config_path, self.config)
            self.original_config = copy.deepcopy(self.config)
            self._update_button_sensitivity()
            self._show_toast('Saved - restart pybar to apply changes')
        except Exception as e:
            self._show_toast(f'Save failed: {e}')
        finally:
            self._loading = False

    def _on_restore(self, _):
        """Restore configuration from original state"""
        try:
            self._loading = True
            self.config = copy.deepcopy(self.original_config)
            self.general_tab.refresh(self.config)
            self.modules_tab.refresh(self.config)
            self.appearance_tab.refresh(self.config)
            self._update_button_sensitivity()
            self._show_toast('Settings restored')
        finally:
            self._loading = False

    def _on_restart(self, _):
        """Signal pybar to reload configuration"""
        import os
        # Create a reload signal file that the bar will watch
        reload_file = os.path.expanduser('~/.cache/pybar/.reload')
        try:
            os.makedirs(os.path.dirname(reload_file), exist_ok=True)
            with open(reload_file, 'w') as f:
                f.write(str(os.getpid()))
            self._show_toast('Pybar will reload configuration...')
        except Exception as e:
            self._show_toast(f'Failed to signal reload: {e}')

    def _show_toast(self, message):
        """Show a toast notification"""
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def _on_close_request(self, _):
        """Handle window close request"""
        if self.save_btn.get_sensitive():
            dialog = Adw.MessageDialog.new(self)
            dialog.set_heading("Unsaved Changes")
            dialog.set_body(
                "You have unsaved changes. "
                "Do you want to save before closing?"
            )
            dialog.add_response("cancel", "Cancel")
            dialog.add_response("discard", "Discard")
            dialog.add_response("save", "Save")
            dialog.set_response_appearance(
                "discard", Adw.ResponseAppearance.DESTRUCTIVE
            )
            dialog.set_response_appearance(
                "save", Adw.ResponseAppearance.SUGGESTED
            )
            dialog.set_default_response("save")
            dialog.set_close_response("cancel")

            def on_response(dlg, response):
                if response == "save":
                    self._on_save(None)
                    self.destroy()
                elif response == "discard":
                    self.destroy()

            dialog.connect('response', on_response)
            dialog.present()
            return True
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
