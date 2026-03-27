#!/usr/bin/python3 -u
"""
Description: Credentials loading and saving for integrations.
    Stored separately from config.json with 600 permissions.
Author: thnikk
"""
import os
import json


CREDENTIALS_FILENAME = 'credentials.json'


def _credentials_path(config_path):
    """Derive credentials file path from config directory path."""
    return os.path.join(
        os.path.expanduser(config_path), CREDENTIALS_FILENAME
    )


def load(config_path):
    """Load credentials from file. Returns empty dict if not found."""
    path = _credentials_path(config_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"[credentials] Failed to load: {e}")
        return {}


def get_hass(config_path, module_config):
    """
    Return (server, bearer_token) for a hass module.
    Module config values take priority over credentials.json,
    allowing per-instance overrides while keeping the common
    case (shared server) out of config.json.
    """
    creds = load(config_path)
    hass = creds.get('hass', {})
    server = module_config.get('server') or hass.get('server', '')
    token = (
        module_config.get('bearer_token') or hass.get('bearer_token', '')
    )
    return server, token


def save(config_path, credentials):
    """
    Save credentials to file with 600 permissions.
    Creates the file owner-read-only from the start.
    """
    path = _credentials_path(config_path)
    dir_path = os.path.dirname(path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)

    # Write via low-level open so we can set mode atomically.
    # O_CREAT | O_WRONLY | O_TRUNC with mode 0o600 creates the
    # file readable only by the owner if it doesn't yet exist.
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(credentials, f, indent=4)
            f.write('\n')
    except Exception:
        # fd is closed by fdopen even on exception, re-raise
        raise

    # Enforce permissions on existing files that were created
    # before this version of the save function.
    current = os.stat(path).st_mode & 0o777
    if current != 0o600:
        os.chmod(path, 0o600)
