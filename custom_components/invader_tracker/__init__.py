"""The Invader Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api.awazleon import AwazleonClient
from .api.flash_invader import FlashInvaderAPI
from .api.invader_spotter import InvaderSpotterScraper
from .const import (
    CONF_API_INTERVAL,
    CONF_AWAZLEON_API_KEY,
    CONF_CITIES,
    CONF_NEW_CITY_DAYS,
    CONF_NEWS_DAYS,
    CONF_SCRAPE_INTERVAL,
    CONF_TRACK_FOLLOWED,
    CONF_UID,
    CONF_UPDATE_INTERVAL,
    DEFAULT_API_INTERVAL_HOURS,
    DEFAULT_NEW_CITY_DAYS,
    DEFAULT_NEWS_DAYS,
    DEFAULT_SCRAPE_INTERVAL_HOURS,
    DEFAULT_TRACK_FOLLOWED,
    DOMAIN,
)
from .coordinator import FlashInvaderCoordinator, FlashInvaderProfileCoordinator, InvaderSpotterCoordinator
from .processor import DataProcessor
from .store import StateStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Invader Tracker from a config entry."""
    _LOGGER.info("Setting up Invader Tracker integration")

    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)

    # Get configuration - options override data (for editable settings)
    uid = entry.data[CONF_UID]
    cities = entry.options.get(CONF_CITIES) or entry.data.get(CONF_CITIES, {})

    # Unified update interval (minutes). Migrate legacy hour-based keys if needed.
    if CONF_UPDATE_INTERVAL in entry.options or CONF_UPDATE_INTERVAL in entry.data:
        update_interval_minutes = int(entry.options.get(CONF_UPDATE_INTERVAL, entry.data.get(CONF_UPDATE_INTERVAL)))
    else:
        # Migrate: take the smaller of legacy scrape_interval / api_interval (both in hours)
        scrape_h = entry.options.get(
            CONF_SCRAPE_INTERVAL, entry.data.get(CONF_SCRAPE_INTERVAL, DEFAULT_SCRAPE_INTERVAL_HOURS)
        )
        api_h = entry.options.get(CONF_API_INTERVAL, entry.data.get(CONF_API_INTERVAL, DEFAULT_API_INTERVAL_HOURS))
        update_interval_minutes = min(int(scrape_h), int(api_h)) * 60

    news_days = entry.options.get(CONF_NEWS_DAYS, entry.data.get(CONF_NEWS_DAYS, DEFAULT_NEWS_DAYS))
    new_city_days = entry.options.get(CONF_NEW_CITY_DAYS, entry.data.get(CONF_NEW_CITY_DAYS, DEFAULT_NEW_CITY_DAYS))
    track_followed = entry.options.get(CONF_TRACK_FOLLOWED, entry.data.get(CONF_TRACK_FOLLOWED, DEFAULT_TRACK_FOLLOWED))

    # Create API clients
    flash_api = FlashInvaderAPI(session, uid)
    awazleon_api_key = entry.options.get(
        CONF_AWAZLEON_API_KEY,
        entry.data.get(CONF_AWAZLEON_API_KEY, ""),
    )
    awazleon_client = AwazleonClient(session, awazleon_api_key) if awazleon_api_key else None
    if not awazleon_api_key:
        _LOGGER.info("No Awazleon API key configured — Awazleon data source disabled")
    spotter_scraper = InvaderSpotterScraper(session)

    # Create coordinators (all share the same update interval)
    spotter_coordinator = InvaderSpotterCoordinator(
        hass,
        awazleon_client,
        spotter_scraper,
        cities,
        update_interval_minutes,
    )
    flash_coordinator = FlashInvaderCoordinator(
        hass,
        flash_api,
        update_interval_minutes,
    )
    profile_coordinator = FlashInvaderProfileCoordinator(
        hass,
        flash_api,
        update_interval_minutes,
        track_followed=track_followed,
        entry_id=entry.entry_id,
    )

    # Create processor and store
    store = StateStore(hass, entry.entry_id)
    processor = DataProcessor(spotter_coordinator, flash_coordinator, store, news_days, new_city_days)
    processor.set_city_names(cities)

    # Initialize processor (load previous snapshot)
    await processor.async_initialize()

    # Initial data fetch — Awazleon failure is non-fatal (coordinator will retry on schedule)
    _LOGGER.debug("Performing initial data fetch")
    try:
        await spotter_coordinator.async_config_entry_first_refresh()
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Awazleon initial fetch failed, will retry on schedule")
    await flash_coordinator.async_config_entry_first_refresh()
    await profile_coordinator.async_config_entry_first_refresh()

    # Save initial snapshot
    await processor.async_save_snapshot()

    # Set up listener to save snapshot and refresh news after each spotter update
    def _on_spotter_update() -> None:
        """Schedule snapshot save and news refresh when spotter data updates."""
        hass.async_create_task(processor.async_save_snapshot())
        hass.async_create_task(processor.async_refresh_news())

    spotter_coordinator.async_add_listener(_on_spotter_update)

    # Store runtime data
    hass.data[DOMAIN][entry.entry_id] = {
        "spotter_coordinator": spotter_coordinator,
        "flash_coordinator": flash_coordinator,
        "profile_coordinator": profile_coordinator,
        "processor": processor,
        "store": store,
    }

    # Register update listener for options
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("Invader Tracker setup complete: tracking %d cities", len(cities))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Invader Tracker integration")

    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.info("Options updated, reloading Invader Tracker")

    # Get old and new cities to detect removals
    old_cities = entry.data.get(CONF_CITIES, {})
    new_cities = entry.options.get(CONF_CITIES, {})

    # Find removed cities
    removed_cities = set(old_cities.keys()) - set(new_cities.keys())

    # Unload the integration first to remove old entities
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Remove devices for deleted cities
    if removed_cities:
        from homeassistant.helpers.device_registry import async_get as async_get_device_registry

        device_registry = async_get_device_registry(hass)

        for city_code in removed_cities:
            device_id = f"{entry.entry_id}_{city_code}"
            # Find device by identifier
            device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
            if device:
                device_registry.async_remove_device(device.id)
                _LOGGER.debug("Removed device for city: %s", city_code)

    # Update coordinators with new cities
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    spotter_coordinator: InvaderSpotterCoordinator = runtime_data["spotter_coordinator"]
    processor: DataProcessor = runtime_data["processor"]

    spotter_coordinator.update_cities(new_cities)
    processor.set_city_names(new_cities)

    # Reload the integration to set up new entities
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of config entry."""
    _LOGGER.info("Removing Invader Tracker integration")

    # Clean up stored data
    store = StateStore(hass, entry.entry_id)
    await store.async_remove()
