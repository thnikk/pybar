#!/usr/bin/python3 -u
"""
Description: Integrations tab for settings window.
    Manages calendar sources (ICS URLs and CalDAV accounts)
    for the clock module. ICS sources are saved to config.json;
    CalDAV credentials are saved to credentials.json.
Author: thnikk
"""
import threading
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib  # noqa
import config as Config
import credentials as Creds


def _test_ics(url, callback):
    """
    Fetch an ICS URL in a background thread and report success.
    Calls callback(success, message) on the GLib main loop.
    """
    def run():
        try:
            import requests
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            # Quick sanity check — valid ICS starts with BEGIN:VCALENDAR
            if b'BEGIN:VCALENDAR' not in resp.content[:256]:
                GLib.idle_add(
                    callback, False,
                    'URL did not return a valid ICS calendar'
                )
                return
            GLib.idle_add(callback, True, 'ICS calendar fetched OK')
        except Exception as e:
            GLib.idle_add(callback, False, str(e))
    threading.Thread(target=run, daemon=True).start()


def _test_caldav(url, username, password, callback):
    """
    Test a CalDAV connection in a background thread.
    Calls callback(success, message) on the GLib main loop.
    """
    def run():
        try:
            import caldav
            client = caldav.DAVClient(
                url=url, username=username, password=password
            )
            principal = client.principal()
            count = len(principal.calendars())
            GLib.idle_add(
                callback, True,
                f"Connected — {count} calendar(s) found"
            )
        except Exception as e:
            GLib.idle_add(callback, False, str(e))
    threading.Thread(target=run, daemon=True).start()


def _status_label():
    """Create a status Gtk.Label with standard styling."""
    lbl = Gtk.Label(label='Not tested')
    lbl.set_valign(Gtk.Align.CENTER)
    return lbl


def _set_status(label, success, message):
    """
    Update a status label with colour feedback.
    Returns False for GLib.idle_add compatibility.
    """
    display = message if len(message) <= 60 else message[:57] + '...'
    label.set_text(display)
    label.set_tooltip_text(message)
    for cls in ('success', 'error'):
        label.remove_css_class(cls)
    label.add_css_class('success' if success else 'error')
    return False


class ICSSourceRow(Adw.ExpanderRow):
    """Expander row representing a single ICS URL calendar source."""

    def __init__(self, source, on_remove, on_change):
        super().__init__()
        self._on_change = on_change

        url = source.get('url', '')
        self._update_title(url)

        # --- URL ---
        self._url_row = Adw.EntryRow()
        self._url_row.set_title('ICS URL')
        self._url_row.set_text(url)
        self._url_row.connect('changed', self._on_url_changed)
        self.add_row(self._url_row)

        # --- Status ---
        status_row = Adw.ActionRow()
        status_row.set_title('Status')
        self._status = _status_label()
        status_row.add_suffix(self._status)
        self.add_row(status_row)

        # --- Test button ---
        test_btn = Gtk.Button(label='Test')
        test_btn.add_css_class('flat')
        test_btn.set_valign(Gtk.Align.CENTER)
        test_btn.connect('clicked', self._on_test)
        self.add_suffix(test_btn)

        # --- Remove button ---
        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('list-remove-symbolic')
        remove_btn.add_css_class('flat')
        remove_btn.add_css_class('destructive-action')
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.set_tooltip_text('Remove source')
        remove_btn.connect('clicked', lambda _: on_remove(self))
        self.add_suffix(remove_btn)

    def _update_title(self, url):
        """Set expander title to URL or placeholder."""
        self.set_title(url.strip() or 'New ICS Source')

    def _on_url_changed(self, _row):
        """Update title and notify parent on URL change."""
        self._update_title(self._url_row.get_text())
        self._on_change()

    def _on_test(self, _btn):
        """Fetch the ICS URL and update status."""
        url = self._url_row.get_text().strip()
        if not url:
            _set_status(self._status, False, 'URL is required')
            return
        self._status.set_text('Testing…')
        _test_ics(url, lambda ok, msg: _set_status(
            self._status, ok, msg
        ))

    def get_source(self):
        """Return source dict for this row."""
        return {
            'type': 'ics_url',
            'url': self._url_row.get_text().strip(),
        }


class CalDAVAccountRow(Adw.ExpanderRow):
    """Expander row representing a single CalDAV account."""

    def __init__(self, account, on_remove, on_change):
        super().__init__()
        self._on_change = on_change

        url = account.get('url', '')
        username = account.get('username', '')
        password = account.get('password', '')
        password_command = account.get('password_command', '')

        self._update_title(username, url)

        # --- URL ---
        self._url_row = Adw.EntryRow()
        self._url_row.set_title('URL')
        self._url_row.set_text(url)
        self._url_row.connect('changed', self._on_field_changed)
        self.add_row(self._url_row)

        # --- Username ---
        self._user_row = Adw.EntryRow()
        self._user_row.set_title('Username')
        self._user_row.set_text(username)
        self._user_row.connect('changed', self._on_field_changed)
        self.add_row(self._user_row)

        # --- Password ---
        self._pass_row = Adw.PasswordEntryRow()
        self._pass_row.set_title('Password')
        self._pass_row.set_text(password)
        self._pass_row.connect('changed', self._on_pass_changed)
        self.add_row(self._pass_row)

        # --- Password Command ---
        self._cmd_row = Adw.EntryRow()
        self._cmd_row.set_title('Password Command')
        self._cmd_row.set_text(password_command)
        self._cmd_row.connect('changed', self._on_cmd_changed)
        self.add_row(self._cmd_row)

        # --- Status ---
        status_row = Adw.ActionRow()
        status_row.set_title('Status')
        self._status = _status_label()
        status_row.add_suffix(self._status)
        self.add_row(status_row)

        # --- Test button ---
        test_btn = Gtk.Button(label='Test')
        test_btn.add_css_class('flat')
        test_btn.set_valign(Gtk.Align.CENTER)
        test_btn.connect('clicked', self._on_test)
        self.add_suffix(test_btn)

        # --- Remove button ---
        remove_btn = Gtk.Button()
        remove_btn.set_icon_name('list-remove-symbolic')
        remove_btn.add_css_class('flat')
        remove_btn.add_css_class('destructive-action')
        remove_btn.set_valign(Gtk.Align.CENTER)
        remove_btn.set_tooltip_text('Remove account')
        remove_btn.connect('clicked', lambda _: on_remove(self))
        self.add_suffix(remove_btn)

    def _update_title(self, username, url):
        """Set expander title to username if present, else URL."""
        title = username.strip() or url.strip() or 'New Account'
        self.set_title(title)

    def _on_field_changed(self, _row):
        """Update title and notify parent on URL/username change."""
        self._update_title(
            self._user_row.get_text(),
            self._url_row.get_text()
        )
        self._on_change()

    def _on_pass_changed(self, _row):
        """Clear password_command when password is typed."""
        if self._pass_row.get_text():
            self._cmd_row.set_text('')
        self._on_change()

    def _on_cmd_changed(self, _row):
        """Clear password when password_command is typed."""
        if self._cmd_row.get_text():
            self._pass_row.set_text('')
        self._on_change()

    def _on_test(self, _btn):
        """Test the CalDAV connection and update status label."""
        url = self._url_row.get_text().strip()
        username = self._user_row.get_text().strip()

        # Resolve password from command or field
        cmd = self._cmd_row.get_text().strip()
        if cmd:
            import subprocess
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True,
                    text=True, timeout=10
                )
                if result.returncode != 0:
                    _set_status(
                        self._status, False,
                        'Password command failed'
                    )
                    return
                password = result.stdout.strip()
            except Exception as e:
                _set_status(
                    self._status, False, f'Command error: {e}'
                )
                return
        else:
            password = self._pass_row.get_text()

        if not url or not username:
            _set_status(
                self._status, False,
                'URL and username are required'
            )
            return
        if not password:
            _set_status(
                self._status, False,
                'Password or password command is required'
            )
            return

        self._status.set_text('Testing…')
        _test_caldav(
            url, username, password,
            lambda ok, msg: _set_status(self._status, ok, msg)
        )

    def get_account(self):
        """Return credentials dict for this account."""
        account = {
            'url': self._url_row.get_text().strip(),
            'username': self._user_row.get_text().strip(),
        }
        cmd = self._cmd_row.get_text().strip()
        pw = self._pass_row.get_text()
        if cmd:
            account['password_command'] = cmd
        elif pw:
            account['password'] = pw
        return account

    def get_source(self):
        """Return config source dict (no credentials)."""
        return {
            'type': 'caldav',
            'url': self._url_row.get_text().strip(),
            'username': self._user_row.get_text().strip(),
        }


class IntegrationsTab(Gtk.Box):
    """
    Integrations settings tab.
    Manages calendar sources for the clock module.
    ICS URLs and CalDAV source entries are saved to config.json.
    CalDAV credentials (passwords) are saved to credentials.json.
    Both save immediately on clicking Save.
    """

    def __init__(self, config_path):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL, spacing=20
        )
        self.set_focusable(True)
        self.connect('map', lambda _: self.grab_focus())

        self._config_path = config_path
        self._ics_rows = []
        self._caldav_rows = []

        # Load existing sources from config
        full_config = Config.load(config_path)
        clock_cfg = full_config.get('modules', {}).get('clock', {})
        existing_sources = clock_cfg.get('sources', [])

        # Load existing CalDAV credentials
        existing_creds = Creds.load(config_path)

        # Index credentials by (url, username) for lookup
        cred_index = {
            (e.get('url', ''), e.get('username', '')): e
            for e in existing_creds.get('caldav', [])
        }

        # --- ICS URLs group ---
        self._ics_group = Adw.PreferencesGroup()
        self._ics_group.set_title('Google Calendar / ICS URLs')
        self._ics_group.set_description(
            'Add a Google Calendar secret ICS address or any public '
            'ICS feed. No login required — the secret is in the URL.'
        )
        self.append(self._ics_group)

        for source in existing_sources:
            if source.get('type') == 'ics_url':
                self._add_ics_row(source)

        add_ics_btn = Gtk.Button(label='Add ICS URL')
        add_ics_btn.set_icon_name('list-add-symbolic')
        add_ics_btn.set_halign(Gtk.Align.START)
        add_ics_btn.connect(
            'clicked', lambda _: self._add_ics_row({})
        )
        self._ics_group.add(add_ics_btn)

        # --- CalDAV group ---
        self._caldav_group = Adw.PreferencesGroup()
        self._caldav_group.set_title('CalDAV Accounts')
        self._caldav_group.set_description(
            'Add an iCloud or other CalDAV account. '
            'Use an app-specific password or a password command '
            'such as "pass show icloud/caldav".'
        )
        self.append(self._caldav_group)

        for source in existing_sources:
            if source.get('type') == 'caldav':
                key = (
                    source.get('url', ''),
                    source.get('username', '')
                )
                # Merge saved credentials back into the row data
                account = dict(source)
                account.update(cred_index.get(key, {}))
                self._add_caldav_row(account)

        add_caldav_btn = Gtk.Button(label='Add CalDAV Account')
        add_caldav_btn.set_icon_name('list-add-symbolic')
        add_caldav_btn.set_halign(Gtk.Align.START)
        add_caldav_btn.connect(
            'clicked', lambda _: self._add_caldav_row({})
        )
        self._caldav_group.add(add_caldav_btn)

        # --- Save button ---
        save_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=8
        )
        save_row.set_halign(Gtk.Align.END)
        save_row.set_margin_top(8)
        self._save_btn = Gtk.Button(label='Save')
        self._save_btn.add_css_class('suggested-action')
        self._save_btn.connect('clicked', self._on_save)
        save_row.append(self._save_btn)
        self.append(save_row)

    def _add_ics_row(self, source):
        """Append an ICSSourceRow for the given source dict."""
        row = ICSSourceRow(
            source,
            on_remove=self._remove_ics_row,
            on_change=lambda: None
        )
        self._ics_rows.append(row)
        self._ics_group.add(row)

    def _remove_ics_row(self, row):
        """Remove an ICS row from the group and tracking list."""
        self._ics_group.remove(row)
        if row in self._ics_rows:
            self._ics_rows.remove(row)

    def _add_caldav_row(self, account):
        """Append a CalDAVAccountRow for the given account dict."""
        row = CalDAVAccountRow(
            account,
            on_remove=self._remove_caldav_row,
            on_change=lambda: None
        )
        self._caldav_rows.append(row)
        self._caldav_group.add(row)

    def _remove_caldav_row(self, row):
        """Remove a CalDAV row from the group and tracking list."""
        self._caldav_group.remove(row)
        if row in self._caldav_rows:
            self._caldav_rows.remove(row)

    def _on_save(self, _btn):
        """
        Save sources to config.json and credentials to
        credentials.json. The JSON source entry is always
        prepended so the clock module reads the local file too.
        """
        try:
            # Build sources list: json always first, then ICS, then
            # CalDAV (url+username only — no passwords in config)
            sources = [{'type': 'json'}]

            for row in self._ics_rows:
                src = row.get_source()
                if src.get('url'):
                    sources.append(src)

            caldav_accounts = []
            for row in self._caldav_rows:
                src = row.get_source()
                if src.get('url') and src.get('username'):
                    sources.append(src)
                    caldav_accounts.append(row.get_account())

            # Write sources into the clock module config
            full_config = Config.load(self._config_path)
            modules = full_config.setdefault('modules', {})
            modules.setdefault('clock', {})['sources'] = sources
            Config.save(self._config_path, full_config)

            # Write CalDAV credentials separately
            Creds.save(
                self._config_path, {'caldav': caldav_accounts}
            )

            self._show_toast('Saved')
        except Exception as e:
            self._show_toast(f'Save failed: {e}')

    def _show_toast(self, message):
        """Show a toast via the nearest ancestor ToastOverlay."""
        widget = self.get_parent()
        while widget:
            if isinstance(widget, Adw.ToastOverlay):
                toast = Adw.Toast.new(message)
                toast.set_timeout(3)
                widget.add_toast(toast)
                return
            widget = widget.get_parent()
        print(f'[integrations] {message}')
