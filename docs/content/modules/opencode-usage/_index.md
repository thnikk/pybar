---
title: "OpenCode Usage"
---

Shows your [OpenCode Go](https://opencode.ai/v2/docs/console/go/) subscription
usage in the bar. Data comes from OpenCode's usage API
(`GET https://opencode.ai/zen/go/v1/usage`), which tracks the 5-hour rolling,
weekly, and monthly windows.

## Setup

If you use OpenCode Go in OpenCode, there's nothing to configure: the module
picks up the key OpenCode already has in `auth.json`. Just add it to your bar
config:

```jsonc
{
    "modules-right": ["opencode-usage"],
    "modules": {
        "opencode-usage": {
            "type": "opencode_usage"
        }
    }
}
```

### API key

The module looks for a key in this order, using the first one it finds:

1. `api_key` in the module config
2. The `OPENCODE_API_KEY` environment variable
3. `opencode` / `opencode_go` in pybar's `credentials.json`
   (`{ "api_key": "..." }`)
4. The key OpenCode keeps in `~/.local/share/opencode/auth.json`
   (`opencode-go`, falling back to `opencode`; honors `XDG_DATA_HOME`)

## Configuration

| Key             | Type     | Default    | Description                                        |
|-----------------|----------|------------|----------------------------------------------------|
| `interval`      | integer  | `300`      | Seconds between usage checks                       |
| `api_key`       | string   | `''`       | OpenCode Go API key (leave empty to auto-detect)   |
| `display`       | choice   | `monthly`  | Window shown in the bar: `monthly`, `weekly`, `rolling`, or `worst` |
| `show_remaining`| boolean  | `false`    | Show remaining percent instead of used percent     |
| `format`        | string   | `'{}%'`    | Bar label format, with `{}` as the percent         |
| `icon`          | string   | `'\uf121'` | Icon shown before the text (empty string to hide)  |
| `warn`          | integer  | `80`       | Percent at which the widget turns orange           |
| `critical`      | integer  | `95`       | Percent at which the widget turns red              |

## Notes

- Clicking the module opens a popover with a bar for each window and its reset
  time underneath.
- The widget turns orange at the `warn` threshold and red at `critical`.
- Go-only: a key without a Go subscription gets a `403` and the module stays
  hidden. Zen balance isn't covered since there's no official API for it.
- If the key is missing or the request fails, the module hides instead of
  showing stale data.