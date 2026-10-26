# Invader Tracker for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/Trolent/HA-Invader-Tracker.svg)](https://github.com/Trolent/HA-Invader-Tracker/releases)
[![License](https://img.shields.io/github/license/Trolent/HA-Invader-Tracker.svg)](LICENSE)
[![Code Quality](https://img.shields.io/badge/code%20quality-clean-brightgreen.svg)](https://github.com/Trolent/HA-Invader-Tracker)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/trolent)

Track [Space Invader](https://www.space-invaders.com/) street art mosaics in Home Assistant. This integration combines data from:

- **[awazleon.space](https://www.awazleon.space/)** — REST API with full invader data per city (status, points, install date). **Requires an API key** — request one at [www.awazleon.space](https://www.awazleon.space/) or via the Space Invaders Discord. Optional: leaving it blank disables this source gracefully.
- **[invader-spotter.art](https://www.invader-spotter.art/)** — News feed for new and reactivated invaders
- **Flash Invader API** — Your personal collection via your account UID

## Overview

Invader Tracker is a comprehensive Home Assistant integration that helps you track, manage, and hunt Space Invader street art mosaics across multiple cities. It automatically monitors new additions, tracks destroyed invaders, detects new cities being invaded worldwide, and keeps you updated on your collection progress.

## Features

**Core Features:**
- **Multi-city tracking** — Monitor invaders across any number of cities
- **Collection management** — Track which invaders you've flashed vs remaining targets
- **Smart notifications** — Get alerted to new invaders and reactivated targets
- **Missed opportunities** — Keep tabs on destroyed invaders you couldn't reach
- **Player profile device** — Your score, rank, cities found, and invaders found in one place
- **Followed players** — Track the players you follow directly in Home Assistant
- **World aggregate device** — Stats summed across all tracked cities + worldwide sensor
- **New city detection** — Sensor that lights up when Space Invader invades a new city

**Technical Features:**
- Single REST call per city (no HTML scraping for invader data)
- News-based new/reactivated detection via invader-spotter.art
- Unified configurable refresh interval (15 min → monthly)
- Smart per-city cache to minimize API calls
- Automatic reload when a new followed player is detected
- Persistent state store across restarts

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click on **Integrations**
3. Click the three dots in the top right corner
4. Select **Custom repositories**
5. Add `https://github.com/Trolent/HA-Invader-Tracker` with category **Integration**
6. Click **Install**
7. Restart Home Assistant

### Manual Installation

1. Download the latest release from [GitHub Releases](https://github.com/Trolent/HA-Invader-Tracker/releases)
2. Extract and copy `custom_components/invader_tracker` to your `config/custom_components/` directory
3. Restart Home Assistant

## Quick Start

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration** and search for "Invader Tracker"
3. Enter your Flash Invader UID
4. Enter your **Awazleon API key** (optional — leave blank to disable Awazleon data). Request a key at [www.awazleon.space](https://www.awazleon.space/) or via the Space Invaders Discord.
5. Select cities to track
6. Choose your update interval

### Finding Your Flash Invader UID

Your UID is a unique identifier (UUID v4 format) for your Flash Invader account. To locate it:

**Method 1: Network Inspection**
1. Set up a network proxy tool (like mitmproxy, Charles Proxy, or Fiddler)
2. Configure your phone to use the proxy
3. Open the Flash Invader app and refresh your gallery
4. Look for API requests to `api.space-invaders.com`
5. Find the `uid` query parameter in the request URL
6. Format: `XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`

**Method 2: App Debugging**
1. Enable developer mode on your phone
2. Use Android Studio (Android) or Xcode (iOS) debugging tools
3. Monitor network traffic during app usage

> **Security Note:** Keep your UID private — it grants access to your Flash Invader account data. Never share it publicly.

## Entities & Sensors

### Player Profile Device

Created automatically as soon as a UID is configured. Named **"User - {your pseudo}"**.

| Entity | Type | Description | Attributes |
|--------|------|-------------|------------|
| `sensor.score` | Sensor | Your total score | — |
| `sensor.rank` | Sensor | Your global rank | `rank_str` |
| `sensor.invaders_found` | Sensor | Total invaders flashed (all cities) | — |
| `sensor.cities_found` | Sensor | Number of cities with at least one flash | — |
| `sensor.registration_date` | Sensor | Account registration date | — |
| `sensor.total_invaders_worldwide` | Sensor | Total invaders placed worldwide by Space Invader | — |

<img src="docs/images/main-user-entities.png" width="320" alt="Main user entities">

### Followed Player Devices

One device per followed player, named **"User - {name}"**. Can be disabled in integration options.

| Entity | Type | Description | Attributes |
|--------|------|-------------|------------|
| `sensor.score` | Sensor | Player's total score | — |
| `sensor.rank` | Sensor | Player's global rank | `rank_str` |
| `sensor.invaders_found` | Sensor | Player's total invaders flashed | — |

<img src="docs/images/followed-user-entities.png" width="320" alt="Followed user entities">

### City Devices

For each tracked city, a dedicated device is created with:

| Entity | Type | Description | Attributes |
|--------|------|-------------|------------|
| `sensor.total_invaders` | Sensor | Total invaders in the city | `flashable_count` |
| `sensor.flashed` | Sensor | Invaders you've flashed | — |
| `sensor.unflashed_available` | Sensor | Flashable invaders not yet done | `invaders` (list of IDs) |
| `sensor.unflashed_gone` | Sensor | Destroyed invaders you missed | `invaders` (list of IDs) |

> The `invaders` list is capped at 500 IDs, with `invaders_truncated: true` added when it is — past ~16 KB of attributes Home Assistant's recorder stores none of them at all.

| `sensor.new_reactivated` | Sensor | New + reactivated unflashed invaders | `new_count`, `reactivated_count` |
| `sensor.invaders_to_flash` | Sensor | CSV list of IDs to flash | — |
| `binary_sensor.has_new` | Binary Sensor | ON when new/reactivated invaders exist | — |

<img src="docs/images/city-entities.png" width="320" alt="City entities">

### World Device

Aggregates stats across all tracked cities. Named **"World"**.

| Entity | Type | Description | Attributes |
|--------|------|-------------|------------|
| `sensor.total_invaders` | Sensor | Total across all tracked cities | `flashable_count` |
| `sensor.flashed` | Sensor | Total flashed across all cities | — |
| `sensor.unflashed_available` | Sensor | Total unflashed available across all cities | — |
| `sensor.unflashed_gone` | Sensor | Total missed across all cities | — |
| `sensor.new_reactivated` | Sensor | Total new/reactivated across all cities | `new_count`, `reactivated_count` |
| `sensor.invaders_to_flash` | Sensor | All IDs to flash across all cities | — |
| `sensor.new_city_invaded` | Sensor | Name of a newly invaded city (within the configured window), `None` otherwise | `detected_at`, `also_new` |
| `binary_sensor.has_new` | Binary Sensor | ON when any tracked city has new invaders | — |

## Configuration Options

Accessible via **Settings → Devices & Services → Invader Tracker → Configure**.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| **Cities** | Multi-select | — | Cities to track (required) |
| **Awazleon API Key** | Text | — | API key for awazleon.space. Leave blank to disable Awazleon data. Request at [www.awazleon.space](https://www.awazleon.space/) or via the Space Invaders Discord. |
| **Update interval** | Dropdown + custom | 4 hours | Refresh interval for all data sources (awazleon, Flash API, news). Predefined values: 15 min, 30 min, 1h, 2h, 4h, 6h, 12h, daily, weekly, monthly. Or enter a custom value in minutes (min. 15). |
| **News Days** | Dropdown | 30 days | How many days of news history to consider for new/reactivated detection |
| **New city detection window** | Dropdown | 1 week | How long `New City Invaded` stays active after a new city is first detected |
| **Track followed players** | Toggle | Enabled | Create devices for players you follow. Disable to skip the extra API call. |

### Recommended Settings

| Profile | Update interval | News Days |
|---------|----------------|-----------|
| Active hunter (daily) | 1–2 hours | 30 days |
| Weekly hunter | 12–24 hours | 30–60 days |
| Low bandwidth | Daily or weekly | 14 days |

## Automations

### Notify on New Invaders (any city)

```yaml
automation:
  - alias: "Alert: New Invaders Detected"
    trigger:
      - platform: state
        entity_id: binary_sensor.world_has_new
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "New Space Invaders!"
          message: >
            {{ states('sensor.world_new_reactivated') }} new target(s) to flash.
            {{ states('sensor.world_invaders_to_flash') }}
```

### Alert on New City Invaded

```yaml
automation:
  - alias: "Alert: New City Invaded"
    trigger:
      - platform: state
        entity_id: sensor.world_new_city_invaded
        not_to:
          - "unavailable"
          - "unknown"
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state not in ['unavailable', 'unknown', 'None'] }}"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Space Invader has invaded a new city!"
          message: >
            {{ trigger.to_state.state }} was first detected on
            {{ state_attr('sensor.world_new_city_invaded', 'detected_at')[:10] }}.
```

### Daily Summary Report

```yaml
automation:
  - alias: "Invader Tracker: Daily Summary"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Daily Invader Summary"
          message: >
            Score: {{ states('sensor.score') }} (rank {{ state_attr('sensor.rank', 'rank_str') }})
            Paris: {{ states('sensor.paris_unflashed_available') }} to flash
            Total flashed: {{ states('sensor.world_flashed') }}
```

## Troubleshooting

### Integration Shows "Unavailable"

1. Ensure Home Assistant can reach the internet
2. Go to **Settings → System → Logs**, filter by `custom_components.invader_tracker`
3. Check if [awazleon.space](https://www.awazleon.space/) and [invader-spotter.art](https://www.invader-spotter.art/) are accessible

### "Authentication Failed" Error

1. Your UID may have changed — re-obtain it from the Flash Invader app
2. Go to **Settings → Devices & Services → Invader Tracker → three dots → Edit**
3. Update your UID

### Data Not Updating

1. Check the update interval in options — it may be set to a long value
2. Check logs for "Rate limited" or connection errors
3. Force a refresh: **Developer Tools → Services → `homeassistant.update_entity`**

### No Invader Data (Awazleon Disabled)

If city sensors show no invader data, Awazleon may be disabled (no API key configured) or the key may be invalid.

1. Go to **Settings → Devices & Services → Invader Tracker → Configure**
2. Enter or update your Awazleon API key
3. Request a key at [www.awazleon.space](https://www.awazleon.space/) or via the **Space Invaders Discord**

### "No Cities Found" During Setup

1. Verify your Awazleon API key is valid — without it the city list cannot be fetched
2. awazleon.space may be temporarily unreachable — try again after a few minutes
3. Check [GitHub Issues](https://github.com/Trolent/HA-Invader-Tracker/issues) for known problems

### Enable Debug Logging

```yaml
logger:
  logs:
    custom_components.invader_tracker: debug
```

Then check **Settings → System → Logs**.

## Project Structure

```
custom_components/invader_tracker/
├── api/
│   ├── awazleon.py          # awazleon.space REST client (invader data)
│   ├── flash_invader.py     # Flash Invader API (gallery, account, highscore)
│   └── invader_spotter.py   # invader-spotter.art scraper (news only)
├── coordinator.py           # Data update coordinators
├── processor.py             # Cross-source data processing
├── models.py                # Data models & enums
├── sensor.py                # City sensor entities
├── sensor_profile.py        # Player profile & followed players sensors
├── sensor_world.py          # World aggregate sensor entities
├── binary_sensor.py         # City binary sensor entities
├── binary_sensor_world.py   # World binary sensor entity
├── config_flow.py           # Configuration UI
├── store.py                 # Persistent state storage
├── exceptions.py            # Custom exceptions
└── const.py                 # Constants
```

## Support & Credits

[![Buy Me A Coffee](https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png)](https://buymeacoffee.com/trolent)

### Acknowledgments

- **Space Invader** — The original street art project
- **[awazleon.space](https://www.awazleon.space/)** — REST API for invader data
- **[invader-spotter.art](https://www.invader-spotter.art/)** — Community database and news source
- **Flash Invader** — Mobile app for tracking personal achievements
- **Home Assistant** — Open-source home automation platform

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is **not affiliated with** Space Invader, Flash Invader, awazleon.space, or invader-spotter.art. Use responsibly and respect the terms of service of all data sources. This tool is provided as-is for personal use only.
