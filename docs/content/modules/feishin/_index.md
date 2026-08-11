---
title: "Feishin"
---

Feishin is a self-hosted music player client for Jellyfin, Navidrome, and
Subsonic servers. This module talks to Feishin's built-in remote control
server over a WebSocket, giving you playback controls plus data that MPRIS
does not expose: play count, shuffle, repeat, and favorite status.

## Setup

In Feishin, enable the remote control server:

1. Open **Settings → Window**
2. Enable **Remote control server**
3. Note the port (default `4333`) and, if set, the username/password

Then add the module to your bar config:

```jsonc
{
    "modules-right": ["feishin"],
    "modules": {
        "feishin": {
            "host": "localhost",
            "port": 4333,
            "show_title": true
        }
    }
}
```

## Configuration

| Key        | Type      | Default     | Description                          |
|------------|-----------|-------------|--------------------------------------|
| `host`     | string    | `localhost` | Host running the Feishin remote server |
| `port`     | integer   | `4333`      | Port of the Feishin remote server     |
| `username` | string    | `''`        | Username for the remote server (if set) |
| `password` | string    | `''`        | Password for the remote server (if set) |
| `show_title` | boolean | `true`      | Show the song title in the bar        |
| `art_size` | integer   | `300`       | Album art size in the popover (pixels) |
| `visualizer` | boolean | `false`     | Show a dummy visualizer over the album art |

## Controls

The popover shows album art, track info, a seek bar, and playback buttons.
Clicking the module opens the popover. The bar widget supports:

- **Scroll wheel** — adjust volume
- **Right click** — toggle play/pause

Additional buttons in the popover:

- **Shuffle** — toggles shuffle, highlighted when active
- **Repeat** — toggles repeat (`off` / `all` / `one`), highlighted when active
- **Favorite** — favorites/unfavorites the current song
- **Plays** — play count of the current song

## Notes

- The module only shows when a song is loaded in Feishin.
- Album art is cached in `~/.cache/pybar`.
- Position updates are pushed by Feishin roughly every 500 ms.
