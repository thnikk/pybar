#!/usr/bin/python3 -u
"""
Description: OpenCode Go subscription usage module
Author: thnikk
"""
import json
import os
from datetime import datetime, timezone
import requests
import common as c
import gi
gi.require_version('Gtk', '4.0')  # noqa


USAGE_URL = 'https://opencode.ai/zen/go/v1/usage'

WINDOWS = ('rolling', 'weekly', 'monthly')
WINDOW_LABELS = {
    'rolling': '5-Hour',
    'weekly': 'Weekly',
    'monthly': 'Monthly',
}

# Severity colors (rgb tuples) and CSS classes matching style.css
SEVERITY_COLORS = {
    'green': (0.639, 0.741, 0.549),   # #a3be8c
    'orange': (0.816, 0.530, 0.439),  # #d08770
    'red': (0.749, 0.380, 0.384),     # #bf616a
}
SEVERITY_CLASS = {
    'green': 'green-fg',
    'orange': 'orange-fg',
    'red': 'red-fg',
}


def opencode_auth_path():
    """Path to OpenCode's own auth.json (honors XDG_DATA_HOME)."""
    data_home = os.environ.get('XDG_DATA_HOME') or '~/.local/share'
    return os.path.expanduser(os.path.join(data_home, 'opencode', 'auth.json'))


class OpenCodeUsage(c.BaseModule):
    DEFAULT_INTERVAL = 300
    EMPTY_IS_ERROR = False

    SCHEMA = {
        'interval': {
            'type': 'integer',
            'default': 300,
            'label': 'Update Interval',
            'description': 'Seconds between usage checks',
            'min': 60,
            'max': 3600
        },
        'api_key': {
            'type': 'string',
            'default': '',
            'label': 'API Key',
            'description': (
                'OpenCode Go API key. Leave empty to use the key '
                'stored by OpenCode itself (auth.json), the '
                'OPENCODE_API_KEY env var, or pybar credentials.'
            )
        },
        'display': {
            'type': 'choice',
            'default': 'monthly',
            'label': 'Window',
            'description': 'Usage window shown in the bar',
            'choices': ['monthly', 'weekly', 'rolling', 'worst']
        },
        'show_remaining': {
            'type': 'boolean',
            'default': False,
            'label': 'Show Remaining',
            'description': (
                'Show remaining percent instead of used percent'
            )
        },
        'format': {
            'type': 'string',
            'default': '{}%',
            'label': 'Format',
            'description': 'Bar label format, with {} as the percent'
        },
        'icon': {
            'type': 'string',
            'default': '\uf121',
            'label': 'Icon',
            'description': (
                'Icon shown before the text (set to empty string '
                'to hide)'
            )
        },
        'warn': {
            'type': 'integer',
            'default': 80,
            'label': 'Warn Threshold',
            'description': 'Percent at which the widget turns orange',
            'min': 0,
            'max': 100
        },
        'critical': {
            'type': 'integer',
            'default': 95,
            'label': 'Critical Threshold',
            'description': 'Percent at which the widget turns red',
            'min': 0,
            'max': 100
        }
    }

    @staticmethod
    def _key_from_pybar_credentials():
        """Look for an api key in pybar's credentials.json."""
        try:
            config_path = c.state_manager.get('config_path')
            if not config_path:
                return None
            import credentials as creds_mod
            creds = creds_mod.load(config_path)
        except Exception as e:
            c.print_debug(
                f'OpenCode usage: failed to load pybar '
                f'credentials: {e}', color='yellow')
            return None
        for name in ('opencode', 'opencode_go'):
            entry = creds.get(name)
            if isinstance(entry, str):
                return entry.strip()
            if isinstance(entry, dict):
                for key_name in ('api_key', 'key'):
                    if entry.get(key_name):
                        return str(entry[key_name]).strip()
        return None

    @staticmethod
    def _key_from_opencode_auth():
        """Read the key OpenCode itself uses from its auth.json."""
        path = opencode_auth_path()
        try:
            with open(path, 'r') as f:
                auth = json.load(f)
        except Exception:
            return None
        for name in ('opencode-go', 'opencode'):
            entry = auth.get(name) or {}
            if isinstance(entry, dict) and entry.get('key'):
                return str(entry['key']).strip()
        return None

    def _find_key(self):
        """Resolve the API key, config override first."""
        key = (self.config.get('api_key') or '').strip()
        if key:
            return key
        key = (os.environ.get('OPENCODE_API_KEY') or '').strip()
        if key:
            return key
        key = self._key_from_pybar_credentials()
        if key:
            return key
        return self._key_from_opencode_auth()

    def _get_session(self):
        """Reuse a single session to avoid accumulating connections."""
        if not hasattr(self, '_session') or self._session is None:
            self._session = requests.Session()
        return self._session

    def _icon(self):
        """Resolve the bar icon from config (defaults to the linux glyph)."""
        icon = self.config.get('icon')
        return '\uf121' if icon is None else icon

    def fetch_data(self):
        """Fetch OpenCode Go usage windows."""
        key = self._find_key()
        if not key:
            c.print_debug(
                'OpenCode usage: no API key found (config, '
                'OPENCODE_API_KEY, credentials.json, auth.json)',
                color='yellow')
            return {}

        try:
            session = self._get_session()
            with session.get(
                USAGE_URL,
                headers={
                    'Authorization': f'Bearer {key}',
                    'Accept': 'application/json'
                },
                timeout=5
            ) as resp:
                if resp.status_code == 200:
                    usage = (resp.json() or {}).get('usage') or {}
                elif resp.status_code == 401:
                    c.print_debug(
                        'OpenCode usage: invalid API key (401)',
                        color='yellow')
                    return {}
                elif resp.status_code == 403:
                    c.print_debug(
                        'OpenCode usage: key has no Go '
                        'subscription (403)', color='yellow')
                    return {}
                else:
                    c.print_debug(
                        f'OpenCode usage: HTTP {resp.status_code}',
                        color='red')
                    return {}
        except Exception as e:
            c.print_debug(
                f'OpenCode usage fetch failed: {e}', color='red')
            return {}

        windows = {}
        for name in WINDOWS:
            w = usage.get(name) or {}
            try:
                percent = max(0, min(100, int(w.get('percent', 0) or 0)))
            except (TypeError, ValueError):
                percent = 0
            windows[name] = {
                'percent': percent,
                'status': w.get('status') or 'ok',
                'resets_at': w.get('resetsAt') or ''
            }

        selected = self.config.get('display', 'monthly')
        if selected == 'worst':
            percent = max(w['percent'] for w in windows.values())
        else:
            percent = windows.get(selected, {}).get('percent', 0)
        if self.config.get('show_remaining', False):
            percent = max(0, 100 - percent)

        icon = self._icon()
        fmt = self.config.get('format') or '{}%'
        try:
            text = fmt.format(percent)
        except Exception:
            text = f'{percent}%'

        return {
            'windows': windows,
            'worst': max(w['percent'] for w in windows.values()),
            'selected': selected,
            'percent': percent,
            'icon': icon,
            'text': text
        }

    def _severity(self, percent):
        """Return the severity key for a used percent."""
        if percent >= self.config.get('critical', 95):
            return 'red'
        if percent >= self.config.get('warn', 80):
            return 'orange'
        return 'green'

    def _resets_in(self, resets_at):
        """Human friendly countdown to a usage window reset."""
        if not resets_at:
            return ''
        try:
            dt = datetime.fromisoformat(
                str(resets_at).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return ''
        delta = dt - datetime.now(timezone.utc)
        total_min = int(delta.total_seconds() // 60)
        if total_min <= 0:
            return 'resets soon'
        days, rem = divmod(total_min, 1440)
        hours, mins = divmod(rem, 60)
        if days:
            return f'resets in {days}d {hours}h'
        if hours:
            return f'resets in {hours}h {mins}m'
        return f'resets in {mins}m'

    def build_popover(self, widget, data):
        """Build popover with a bar per usage window."""
        main_box = c.box('v', spacing=14, style='small-widget')
        main_box.append(c.label('OpenCode Go', style='heading'))

        body = c.box('v', spacing=10)

        selected = data.get('selected', 'monthly')
        summary = f'Bar shows {selected} usage'
        body.append(c.label(summary, style='gray', ha='start'))

        for name in WINDOWS:
            win = data['windows'].get(name, {})
            percent = win.get('percent', 0)
            status = win.get('status', 'ok')
            severity = self._severity(percent)

            row = c.box('v', spacing=4)

            head = c.box('h', spacing=10)
            head.append(
                c.label(WINDOW_LABELS[name], style='title',
                        he=True, ha='start'))
            text = f'{percent}%'
            if status != 'ok':
                text += ' (limited)'
                severity = 'red'
            head.append(
                c.label(text, style=SEVERITY_CLASS[severity],
                        he=True, ha='end'))
            row.append(head)

            bar = c.PillBar(height=10, radius=5)
            bar.set_hexpand(True)
            bar.update([{
                'percent': percent,
                'color': SEVERITY_COLORS[severity],
                'tooltip': f'{percent}% used'
            }])
            row.append(bar)

            reset = self._resets_in(win.get('resets_at'))
            if reset:
                row.append(c.label(reset, style='gray', ha='start'))

            body.append(row)
            if name != WINDOWS[-1]:
                body.append(c.sep('h'))

        main_box.append(body)
        return main_box

    def update_ui(self, widget, data):
        if not data:
            widget.set_visible(False)
            return
        widget.set_icon(self._icon())
        widget.set_label(data.get('text', ''))
        widget.set_visible(bool(data.get('text')))
        widget.reset_style()
        if data.get('stale'):
            c.add_style(widget, 'stale')
        else:
            severity = self._severity(data.get('percent', 0))
            c.add_style(widget, SEVERITY_CLASS[severity])

        # Rebuild the popover only when the underlying data changes
        fingerprint = (
            data.get('selected'),
            data.get('worst'),
            tuple(
                (w.get('percent'), w.get('status'), w.get('resets_at'))
                for w in data['windows'].values()
            )
        )
        if fingerprint == getattr(widget, '_opencode_fingerprint', None) \
                and widget.get_popover() is not None:
            return
        widget._opencode_fingerprint = fingerprint
        widget.set_widget(self.build_popover(widget, data))


module_map = {
    'opencode_usage': OpenCodeUsage
}

alias_map = {
    'opencode': OpenCodeUsage,
    'opencode_go': OpenCodeUsage,
    'opencode-usage': OpenCodeUsage,
    'opencode-go': OpenCodeUsage,
}