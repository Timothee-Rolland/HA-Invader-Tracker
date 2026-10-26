"""Data update coordinators for Invader Tracker integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CITY_REQUEST_DELAY, COORDINATOR_FLASH, COORDINATOR_PROFILE, COORDINATOR_SPOTTER
from .exceptions import (
    AuthenticationError,
    InvaderSpotterConnectionError,
    InvaderTrackerConnectionError,
    ParseError,
    RateLimitError,
)
from .models import FlashedInvader, FollowedPlayer, Invader, NewsEvent, PlayerProfile

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .api.awazleon import AwazleonClient
    from .api.flash_invader import FlashInvaderAPI
    from .api.invader_spotter import InvaderSpotterScraper

ProfileData = tuple[PlayerProfile, list[FollowedPlayer]]

_LOGGER = logging.getLogger(__name__)


class InvaderSpotterCoordinator(DataUpdateCoordinator[dict[str, list[Invader]]]):
    """Coordinator for invader data (awazleon) + news (invader-spotter)."""

    def __init__(
        self,
        hass: HomeAssistant,
        awazleon: AwazleonClient | None,
        scraper: InvaderSpotterScraper,
        cities: dict[str, str],
        update_interval_minutes: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            awazleon: Awazleon REST API client, or None if no API key is configured
            scraper: Invader Spotter scraper (news only)
            cities: Dict mapping city codes to names
            update_interval_minutes: Minutes between updates

        """
        super().__init__(
            hass,
            _LOGGER,
            name=COORDINATOR_SPOTTER,
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._awazleon = awazleon
        self._scraper = scraper
        self._cities = cities
        self._update_interval_minutes = update_interval_minutes
        # Cache: city_code -> (timestamp, list[Invader])
        self._city_cache: dict[str, tuple[datetime, list[Invader]]] = {}
        # News events cache: (timestamp, list[NewsEvent])
        self._news_cache: tuple[datetime, list[NewsEvent]] | None = None
        self._news_cache_hours: int = 6  # Cache news for 6 hours
        # All cities known in awazleon (updated each refresh, used for new-city detection)
        self._all_known_cities: dict[str, str] = {}  # code -> name

    @property
    def cities(self) -> dict[str, str]:
        """Get tracked cities."""
        return self._cities

    @property
    def all_known_cities(self) -> dict[str, str]:
        """Get all cities known in awazleon (code -> name)."""
        return self._all_known_cities

    def update_cities(self, cities: dict[str, str]) -> None:
        """Update the list of tracked cities.

        Args:
            cities: New dict mapping city codes to names

        """
        old_cities = set(self._cities.keys())
        new_cities = set(cities.keys())

        # Log changes
        added = new_cities - old_cities
        removed = old_cities - new_cities

        if added:
            _LOGGER.info("New cities added: %s", ", ".join(added))
        if removed:
            _LOGGER.info("Cities removed: %s", ", ".join(removed))
            # Clean up cache for removed cities
            for city_code in removed:
                self._city_cache.pop(city_code, None)

        self._cities = cities

    def _is_cache_valid(self, city_code: str) -> bool:
        """Check if cached data for a city is still valid.

        Args:
            city_code: City code to check

        Returns:
            True if cache is valid and not expired
        """
        if city_code not in self._city_cache:
            return False

        cached_time, _ = self._city_cache[city_code]
        age = datetime.now() - cached_time
        max_age = timedelta(minutes=self._update_interval_minutes)

        return age < max_age

    async def _async_update_data(self) -> dict[str, list[Invader]]:
        """Fetch invader data from awazleon, using cache for unchanged cities."""
        if self._awazleon is None:
            _LOGGER.debug("Awazleon disabled (no API key) — skipping update")
            return self.data or {}

        _LOGGER.debug("Starting awazleon update for %d cities", len(self._cities))

        # Refresh the global city list for new-city detection
        try:
            cities_list = await self._awazleon.get_cities()
            self._all_known_cities = {c.code: c.name for c in cities_list}
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch awazleon city list: %s", err)

        result: dict[str, list[Invader]] = {}
        failures: list[str] = []
        cached_count = 0
        scraped_count = 0

        for city_code, city_name in self._cities.items():
            if self._is_cache_valid(city_code):
                _, cached_invaders = self._city_cache[city_code]
                result[city_code] = cached_invaders
                cached_count += 1
                _LOGGER.debug("Using cached data for %s (%d invaders)", city_code, len(cached_invaders))
                continue

            if scraped_count > 0:
                try:
                    await asyncio.sleep(CITY_REQUEST_DELAY)
                except asyncio.CancelledError:
                    raise

            try:
                invaders = await self._awazleon.get_city_invaders(city_code, city_name)
                result[city_code] = invaders
                self._city_cache[city_code] = (datetime.now(), invaders)
                scraped_count += 1
                _LOGGER.debug(
                    "Fetched %s from awazleon: %d invaders (%d flashable)",
                    city_code,
                    len(invaders),
                    sum(1 for inv in invaders if inv.is_flashable),
                )

            except (InvaderSpotterConnectionError, ParseError) as err:
                _LOGGER.warning("Failed to fetch %s from awazleon: %s", city_code, err)
                failures.append(city_code)

                if city_code in self._city_cache:
                    _, cached_invaders = self._city_cache[city_code]
                    result[city_code] = cached_invaders
                    _LOGGER.info("Using expired cache for %s", city_code)
                elif self.data and city_code in self.data:
                    result[city_code] = self.data[city_code]
                    _LOGGER.info("Using previous data for %s", city_code)

        if len(failures) == len(self._cities) and not result:
            raise UpdateFailed(f"Failed to fetch any cities: {', '.join(failures)}")

        total_invaders = sum(len(inv) for inv in result.values())
        if failures:
            _LOGGER.warning(
                "Awazleon partial update: %d fetched, %d cached, %d failed (%d total invaders)",
                scraped_count,
                cached_count,
                len(failures),
                total_invaders,
            )
        else:
            _LOGGER.info(
                "Awazleon update complete: %d fetched, %d cached (%d total invaders)",
                scraped_count,
                cached_count,
                total_invaders,
            )

        return result

    async def get_news_events(self, days: int = 30) -> list[NewsEvent]:
        """Get news events from invader-spotter.art/news.php.

        Uses caching to avoid hitting the site too frequently.

        Args:
            days: Number of days of news to fetch

        Returns:
            List of NewsEvent objects
        """
        # Check cache
        if self._news_cache is not None:
            cached_time, cached_events = self._news_cache
            age = datetime.now() - cached_time
            if age < timedelta(hours=self._news_cache_hours):
                _LOGGER.debug("Using cached news (%d events)", len(cached_events))
                return cached_events

        try:
            # Get news filtered by our tracked cities
            city_codes = set(self._cities.keys())
            events = await self._scraper.get_news(days=days, city_codes=city_codes)

            # Update cache
            self._news_cache = (datetime.now(), events)
            _LOGGER.info("Fetched %d news events for tracked cities", len(events))

            return events

        except Exception as err:  # noqa: BLE001 - news is best-effort, never break the update
            _LOGGER.warning("Failed to fetch news: %s", err)
            # Return cached events if available
            if self._news_cache is not None:
                _, cached_events = self._news_cache
                return cached_events
            return []

    def get_news_for_city(self, city_code: str, events: list[NewsEvent]) -> list[NewsEvent]:
        """Filter news events for a specific city.

        Args:
            city_code: City code to filter by
            events: List of all news events

        Returns:
            List of NewsEvent for this city
        """
        return [e for e in events if e.city_code == city_code]


class FlashInvaderCoordinator(DataUpdateCoordinator[list[FlashedInvader]]):
    """Coordinator for Flash Invader API data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FlashInvaderAPI,
        update_interval_minutes: int,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            api: Flash Invader API client
            update_interval_minutes: Minutes between updates

        """
        super().__init__(
            hass,
            _LOGGER,
            name=COORDINATOR_FLASH,
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._api = api
        self._flashed_by_city: dict[str, list[FlashedInvader]] = {}

    def get_city_si_count(self, city_code: str) -> int | None:
        """Return total SI count for a city from the Flash Invader API."""
        return self._api.get_city_si_count(city_code)

    def get_flashed_for_city(self, city_code: str) -> list[FlashedInvader]:
        """Get flashed invaders for a specific city.

        Args:
            city_code: City code to filter by

        Returns:
            List of FlashedInvader for the city

        """
        return self._flashed_by_city.get(city_code, [])

    async def _async_update_data(self) -> list[FlashedInvader]:
        """Fetch flashed invaders from API."""
        _LOGGER.debug("Fetching flashed invaders from Flash Invader API")

        try:
            invaders = await self._api.get_flashed_invaders()
            self._update_city_grouping(invaders)

            _LOGGER.info(
                "Fetched %d flashed invaders across %d cities",
                len(invaders),
                len(self._flashed_by_city),
            )
            return invaders

        except AuthenticationError as err:
            # Triggers HA reauth flow - user must reconfigure
            raise ConfigEntryAuthFailed("Flash Invader authentication failed. Please reconfigure.") from err

        except RateLimitError as err:
            _LOGGER.warning("Rate limited, will retry later")
            raise UpdateFailed("Rate limited by Flash Invader API") from err

        except InvaderTrackerConnectionError as err:
            _LOGGER.warning("Connection error: %s", err)
            raise UpdateFailed(f"Connection error: {err}") from err

        except ParseError as err:
            _LOGGER.error("Parse error: %s", err)
            raise UpdateFailed(f"Failed to parse response: {err}") from err

    def _update_city_grouping(self, invaders: list[FlashedInvader]) -> None:
        """Group invaders by city code extracted from ID.

        Args:
            invaders: List of flashed invaders to group

        """
        self._flashed_by_city.clear()

        for inv in invaders:
            # Extract city code from ID (e.g., "PA_346" -> "PA")
            parts = inv.id.rsplit("_", 1)
            city_code = parts[0] if len(parts) == 2 else inv.id[:2]  # Fallback to first 2 chars

            self._flashed_by_city.setdefault(city_code, []).append(inv)


class FlashInvaderProfileCoordinator(DataUpdateCoordinator[ProfileData]):
    """Coordinator for Flash Invader player profile and followed players."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: FlashInvaderAPI,
        update_interval_minutes: int,
        track_followed: bool = True,
        entry_id: str = "",
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=COORDINATOR_PROFILE,
            update_interval=timedelta(minutes=update_interval_minutes),
        )
        self._api = api
        self._track_followed = track_followed
        self._entry_id = entry_id
        self._known_followed_names: set[str] = set()

    @property
    def track_followed(self) -> bool:
        """Return whether followed player tracking is enabled."""
        return self._track_followed

    @property
    def profile(self) -> PlayerProfile | None:
        """Return the player profile."""
        if self.data is None:
            return None
        return self.data[0]

    @property
    def followed_players(self) -> list[FollowedPlayer]:
        """Return the list of followed players."""
        if self.data is None:
            return []
        return self.data[1]

    async def _async_update_data(self) -> ProfileData:
        """Fetch profile and optionally followed players."""
        try:
            if self._track_followed:
                profile, followed = await asyncio.gather(
                    self._api.get_player_profile(),
                    self._api.get_followed_players(),
                )
            else:
                profile = await self._api.get_player_profile()
                followed = []

            # Enrich profile with total worldwide count (populated by FlashInvaderCoordinator)
            profile = PlayerProfile(
                name=profile.name,
                score=profile.score,
                rank=profile.rank,
                rank_str=profile.rank_str,
                si_found=profile.si_found,
                city_found=profile.city_found,
                registration_date=profile.registration_date,
                total_si_count=self._api.total_si_count,
            )

            _LOGGER.debug(
                "Fetched profile for %s (rank %s) and %d followed players",
                profile.name,
                profile.rank_str,
                len(followed),
            )

            # Detect new followed players and trigger a config entry reload
            if self._track_followed:
                current_names = {p.name for p in followed}
                new_players = current_names - self._known_followed_names
                if self._known_followed_names and new_players:
                    _LOGGER.info(
                        "New followed player(s) detected: %s — reloading integration",
                        ", ".join(new_players),
                    )
                    self._known_followed_names = current_names
                    if self._entry_id:
                        self.hass.async_create_task(self.hass.config_entries.async_reload(self._entry_id))
                else:
                    self._known_followed_names = current_names

            return profile, followed

        except AuthenticationError as err:
            raise ConfigEntryAuthFailed("Flash Invader authentication failed. Please reconfigure.") from err

        except (InvaderTrackerConnectionError, ParseError) as err:
            raise UpdateFailed(f"Failed to fetch profile: {err}") from err
