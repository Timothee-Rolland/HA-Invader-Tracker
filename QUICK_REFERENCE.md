# Quick Reference Guide

A quick lookup for entity names, automation templates, and dashboard cards.

## Entity Name Reference

### City Devices

Replace `{city}` with the lowercase city code (e.g., `paris`, `lyon`, `london`):

```
sensor.city_{city}_total_invaders       # Total invaders in city
sensor.city_{city}_flashed              # Invaders you've flashed
sensor.city_{city}_unflashed_available  # Flashable, not yet flashed
sensor.city_{city}_unflashed_gone       # Destroyed before you could flash
sensor.city_{city}_new_reactivated      # New or reactivated (unflashed)
sensor.city_{city}_invaders_to_flash    # CSV list of IDs to flash
binary_sensor.city_{city}_has_new       # ON when new/reactivated invaders exist
```

### World Device

```
sensor.world_total_invaders       # Total across all tracked cities
sensor.world_flashed              # Total flashed across all cities
sensor.world_unflashed_available  # Total unflashed available
sensor.world_unflashed_gone       # Total missed
sensor.world_new_reactivated      # Total new/reactivated
sensor.world_invaders_to_flash    # All IDs to flash (CSV)
sensor.world_new_city_invaded     # Name of newly invaded city, None otherwise
binary_sensor.world_has_new       # ON when any tracked city has new invaders
```

### Player Profile Device

```
sensor.score                         # Your total score
sensor.rank                          # Your global rank (attr: rank_str)
sensor.invaders_found                # Total invaders you've flashed
sensor.cities_found                  # Cities with at least one flash
sensor.registration_date             # Account creation date
sensor.total_invaders_worldwide      # Total invaders placed worldwide
```

### Followed Player Devices

Replace `{name}` with the player's name (lowercased, spaces → underscores):

```
sensor.{name}_score            # Player's score
sensor.{name}_rank             # Player's rank (attr: rank_str)
sensor.{name}_invaders_found   # Player's total flashed
```

## Sensor Attributes

```yaml
sensor.world_new_reactivated:
  state: 3                        # Total new + reactivated count
  new_count: 2                    # Of which newly added
  reactivated_count: 1            # Of which reactivated

sensor.world_new_city_invaded:
  state: "Bruxelles"              # Most recently detected new city (or None)
  detected_at: "2026-04-15T..."   # ISO datetime of first detection
  also_new: ["Lyon"]              # Other cities detected in same window (if any)

sensor.rank:
  state: 42                       # Numeric rank
  rank_str: "Space Explorer"      # Label from Flash Invader

sensor.city_{city}_total_invaders:
  state: 350                      # Total count
  flashable_count: 280            # Of which flashable (not destroyed/gone)

sensor.city_{city}_unflashed_available:
  state: 9                        # How many are left to flash
  invaders: ["OR_1", "OR_2", …]   # Which ones

sensor.city_{city}_unflashed_gone:
  state: 2                        # How many were destroyed before you flashed them
  invaders: ["OR_11", "OR_12"]    # Which ones
```

List them in a Markdown card:

```yaml
type: markdown
content: >
  {{ state_attr('sensor.city_paris_unflashed_available', 'invaders') | join(', ') }}
```

## Common Automations

### Alert on New Invaders (any city)

```yaml
automation:
  - alias: "New Invaders Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.world_has_new
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "New Space Invaders!"
          message: >
            {{ states('sensor.world_new_reactivated') }} new target(s):
            {{ states('sensor.world_invaders_to_flash') }}
```

### Alert on New City Invaded

```yaml
automation:
  - alias: "New City Invaded"
    trigger:
      - platform: state
        entity_id: sensor.world_new_city_invaded
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.state not in ['unavailable', 'unknown'] and
             trigger.from_state.state != trigger.to_state.state }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Space Invader invades a new city!"
          message: >
            {{ trigger.to_state.state }} first detected on
            {{ state_attr('sensor.world_new_city_invaded', 'detected_at')[:10] }}.
```

### Daily Summary

```yaml
automation:
  - alias: "Daily Invader Report"
    trigger:
      - platform: time
        at: "20:00:00"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Daily Invader Summary"
          message: >
            Score: {{ states('sensor.score') }}
            ({{ state_attr('sensor.rank', 'rank_str') }}, rank #{{ states('sensor.rank') }})
            To flash: {{ states('sensor.world_unflashed_available') }} worldwide
            Flashed: {{ states('sensor.world_flashed') }} worldwide
```

### Milestone Alert

```yaml
automation:
  - alias: "Flash Milestone"
    trigger:
      - platform: numeric_state
        entity_id: sensor.invaders_found
        above: 100
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "Achievement!"
          message: "You've flashed {{ states('sensor.invaders_found') }} invaders worldwide!"
```

## Template Examples

### Completion Percentage for a City

```jinja2
{% set total = states('sensor.city_paris_total_invaders') | int(0) %}
{% set flashed = states('sensor.city_paris_flashed') | int(0) %}
{% if total > 0 %}
  Paris: {{ (flashed / total * 100) | round(1) }}% complete
{% endif %}
```

### World Completion

```jinja2
{% set total = states('sensor.world_total_invaders') | int(0) %}
{% set flashed = states('sensor.world_flashed') | int(0) %}
{{ (flashed / total * 100) | round(1) if total > 0 else 0 }}% worldwide
```

## Dashboard Card Examples

### World Overview Card

```yaml
type: entities
title: "World Stats"
entities:
  - entity: sensor.world_total_invaders
    name: Total Invaders
  - entity: sensor.world_flashed
    name: Flashed
  - entity: sensor.world_unflashed_available
    name: To Flash
  - entity: sensor.world_new_reactivated
    name: New & Reactivated
  - entity: binary_sensor.world_has_new
    name: Action Required
  - entity: sensor.world_new_city_invaded
    name: New City
```

### City Progress Card

```yaml
type: entities
title: "Paris"
entities:
  - entity: sensor.city_paris_total_invaders
    name: Total
  - entity: sensor.city_paris_flashed
    name: Flashed
  - entity: sensor.city_paris_unflashed_available
    name: Available
  - entity: sensor.city_paris_unflashed_gone
    name: Missed
  - entity: binary_sensor.city_paris_has_new
    name: New?
```

### Profile Card

```yaml
type: entities
title: "My Profile"
entities:
  - entity: sensor.score
    name: Score
  - entity: sensor.rank
    name: Rank
  - entity: sensor.invaders_found
    name: Invaders Found
  - entity: sensor.cities_found
    name: Cities
  - entity: sensor.total_invaders_worldwide
    name: Worldwide Total
```

## Configuration Tips

### Choosing Your Update Interval

The same interval applies to all data sources (awazleon, Flash API, news).

| Profile | Interval |
|---------|----------|
| Active hunter | 30 min – 1 hour |
| Weekly check | 6 – 12 hours |
| Passive tracking | Daily or weekly |
| Minimum allowed | 15 minutes |

### New City Detection

`sensor.world_new_city_invaded` shows a city name for the configured window (default 1 week) after it first appears in awazleon. After the window expires, it returns to `None`. Adjust the window in integration options under **New city detection window**.

## Debugging

### Force Refresh

**Developer Tools → Services → `homeassistant.update_entity`**

### Enable Debug Logging

```yaml
logger:
  logs:
    custom_components.invader_tracker: debug
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Sensors show "unavailable" | Check logs for connection errors |
| No city invader data | Awazleon may be disabled — add API key in options (request at awazleon.space or Space Invaders Discord) |
| No new invader alert | Verify `binary_sensor.world_has_new` exists |
| New city sensor always None | First run populates baseline — new cities detected on next refresh |
| Updates not happening | Check update interval in options |

## Useful Links

- **GitHub:** https://github.com/Trolent/HA-Invader-Tracker
- **Issues:** https://github.com/Trolent/HA-Invader-Tracker/issues
- **awazleon.space:** https://www.awazleon.space/
- **invader-spotter.art:** https://www.invader-spotter.art/
- **Space Invader:** https://www.space-invaders.com/
