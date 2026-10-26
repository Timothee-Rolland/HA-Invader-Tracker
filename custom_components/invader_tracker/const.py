"""Constants for Invader Tracker integration."""

from typing import Final

DOMAIN: Final = "invader_tracker"

# Configuration keys
CONF_UID: Final = "uid"
CONF_CITIES: Final = "cities"
CONF_UPDATE_INTERVAL: Final = "update_interval"  # minutes, applies to all data sources
CONF_NEWS_DAYS: Final = "news_days"
CONF_NEW_CITY_DAYS: Final = "new_city_days"
CONF_TRACK_FOLLOWED: Final = "track_followed"
CONF_AWAZLEON_API_KEY: Final = "awazleon_api_key"

# Kept for migration of existing entries
CONF_SCRAPE_INTERVAL: Final = "scrape_interval"
CONF_API_INTERVAL: Final = "api_interval"

# Defaults
DEFAULT_UPDATE_INTERVAL_MINUTES: Final = 240  # 4 hours
MIN_UPDATE_INTERVAL_MINUTES: Final = 15
DEFAULT_TRACK_FOLLOWED: Final = True
DEFAULT_NEWS_DAYS: Final = 30
DEFAULT_NEW_CITY_DAYS: Final = 7

# Legacy defaults (used only for migration)
DEFAULT_SCRAPE_INTERVAL_HOURS: Final = 24
DEFAULT_API_INTERVAL_HOURS: Final = 1

# API URLs
FLASH_INVADER_BASE_URL: Final = "https://api.space-invaders.com"
FLASH_INVADER_ENDPOINT: Final = "/flashinvaders_v3_pas_trop_predictif/api/gallery"
FLASH_INVADER_ACCOUNT_ENDPOINT: Final = "/flashinvaders_v3_pas_trop_predictif/api/account"
FLASH_INVADER_HIGHSCORE_ENDPOINT: Final = "/flashinvaders_v3_pas_trop_predictif/app_web/account/highscore"
INVADER_SPOTTER_BASE_URL: Final = "https://www.invader-spotter.art"
AWAZLEON_BASE_URL: Final = "https://www.awazleon.space"

# Storage
STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = f"{DOMAIN}_state"

# Coordinator names
COORDINATOR_SPOTTER: Final = "invader_spotter"
COORDINATOR_FLASH: Final = "flash_invader"
COORDINATOR_PROFILE: Final = "flash_invader_profile"

# Entity naming
SENSOR_TOTAL: Final = "total"
SENSOR_FLASHED: Final = "flashed"
SENSOR_UNFLASHED: Final = "unflashed"
SENSOR_UNFLASHED_GONE: Final = "unflashed_gone"
SENSOR_NEW: Final = "new"
SENSOR_TO_FLASH: Final = "to_flash"
BINARY_SENSOR_HAS_NEW: Final = "has_new"

# Rate limiting
CITY_REQUEST_DELAY: Final = 2.0  # seconds between city requests

# Retry settings
SCRAPE_MAX_RETRIES: Final = 3
SCRAPE_RETRY_BACKOFF: Final = 2.0  # seconds, doubled on each retry
