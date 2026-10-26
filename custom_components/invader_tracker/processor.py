"""Data processor for Invader Tracker integration."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .models import (
    ChangeSet,
    City,
    CityStats,
    Invader,
    NewsEvent,
    NewsEventType,
    StateSnapshot,
)

if TYPE_CHECKING:
    from .coordinator import FlashInvaderCoordinator, InvaderSpotterCoordinator
    from .store import StateStore

_LOGGER = logging.getLogger(__name__)


class DataProcessor:
    """Process and cross-reference invader data."""

    def __init__(
        self,
        spotter_coordinator: InvaderSpotterCoordinator,
        flash_coordinator: FlashInvaderCoordinator,
        store: StateStore,
        news_days: int = 30,
        new_city_days: int = 7,
    ) -> None:
        """Initialize the processor.

        Args:
            spotter_coordinator: Coordinator for invader-spotter data
            flash_coordinator: Coordinator for Flash Invader API data
            store: State storage for snapshots
            news_days: Number of days to consider for new/reactivated detection

        """
        self._spotter = spotter_coordinator
        self._flash = flash_coordinator
        self._store = store
        self._previous_snapshot: StateSnapshot | None = None
        self._city_names: dict[str, str] = {}
        # Cached news events (refreshed by coordinator)
        self._news_events: list[NewsEvent] = []
        self._news_days: int = news_days
        self._new_city_days: int = new_city_days

    async def async_initialize(self) -> None:
        """Load previous snapshot from storage and fetch news."""
        self._previous_snapshot = await self._store.async_load_snapshot()
        if self._previous_snapshot:
            _LOGGER.info(
                "Loaded previous snapshot from %s",
                self._previous_snapshot.timestamp.isoformat(),
            )

        # Fetch initial news events
        await self.async_refresh_news()

    def set_city_names(self, city_names: dict[str, str]) -> None:
        """Set city code to name mapping.

        Args:
            city_names: Dict mapping city codes to names

        """
        self._city_names = city_names

    async def async_refresh_news(self) -> None:
        """Refresh news events from invader-spotter."""
        self._news_events = await self._spotter.get_news_events(days=self._news_days)
        _LOGGER.debug("Refreshed news: %d events", len(self._news_events))

    def get_flashed_for_city(self, city_code: str) -> list:
        """Return flashed invaders for a city (from Flash Invader API only)."""
        return self._flash.get_flashed_for_city(city_code)

    def compute_city_stats(self, city_code: str) -> CityStats:
        """Compute full statistics for a city.

        Uses official news.php data for new/reactivated detection.

        Args:
            city_code: City code to compute stats for

        Returns:
            CityStats with all computed values

        """
        # Get all invaders from spotter coordinator
        all_invaders = self._get_invaders_for_city(city_code)

        # Get flashed invaders from flash coordinator
        flashed = self._flash.get_flashed_for_city(city_code)

        # Get news events for this city
        city_news = self._spotter.get_news_for_city(city_code, self._news_events)

        # Extract new and reactivated invaders from news
        new_invaders = self._get_invaders_from_news(all_invaders, city_news, NewsEventType.ADDED)
        reactivated_invaders = self._get_invaders_from_news(
            all_invaders, city_news, NewsEventType.REACTIVATED, NewsEventType.RESTORED
        )

        # Build city object
        city = City(
            code=city_code,
            name=self._city_names.get(city_code, city_code),
            total_invaders=len(all_invaders),
        )

        return CityStats(
            city=city,
            all_invaders=all_invaders,
            flashed_invaders=flashed,
            new_invaders=new_invaders,
            reactivated_invaders=reactivated_invaders,
            news_events=city_news,
        )

    def _get_invaders_from_news(
        self,
        all_invaders: list[Invader],
        news_events: list[NewsEvent],
        *event_types: NewsEventType,
    ) -> list[Invader]:
        """Get invaders matching news events of specific types.

        Args:
            all_invaders: List of all invaders in city
            news_events: News events for the city
            event_types: Event types to filter by

        Returns:
            List of Invader objects that had matching news events

        """
        # Get IDs from news events of the specified types
        news_ids = {event.invader_id for event in news_events if event.event_type in event_types}

        # Find matching invaders
        invader_map = {inv.id: inv for inv in all_invaders}
        return [invader_map[inv_id] for inv_id in news_ids if inv_id in invader_map]

    def _get_invaders_for_city(self, city_code: str) -> list[Invader]:
        """Get invaders for a city from spotter coordinator."""
        if self._spotter.data is None:
            return []
        return self._spotter.data.get(city_code, [])

    def detect_changes(self, city_code: str, recently_added_days: int = 30) -> ChangeSet:
        """Detect new/reactivated invaders since last snapshot.

        Args:
            city_code: City code to check
            recently_added_days: Consider invaders "new" if first seen within N days

        Returns:
            ChangeSet with detected changes

        """
        if not self._previous_snapshot:
            return ChangeSet()

        current_invaders = self._get_invaders_for_city(city_code)
        if not current_invaders:
            return ChangeSet()

        # Get recently added invaders (first seen within N days)
        new_invaders = self._previous_snapshot.get_recently_added(current_invaders, days=recently_added_days)

        # Get reactivated invaders (status changed from non-flashable to flashable)
        reactivated = self._previous_snapshot.get_reactivated(current_invaders)

        if new_invaders or reactivated:
            _LOGGER.info(
                "Changes for %s: %d recently added (<%d days), %d reactivated",
                city_code,
                len(new_invaders),
                recently_added_days,
                len(reactivated),
            )

        return ChangeSet(
            new_invaders=new_invaders,
            reactivated_invaders=reactivated,
        )

    async def async_save_snapshot(self) -> None:
        """Save current state as snapshot for future comparison.

        This preserves first_seen dates and tracks status changes.
        """
        if self._spotter.data is None:
            _LOGGER.debug("No spotter data to save")
            return

        now = datetime.now()

        # Build current IDs and statuses
        current_ids_by_city = {city: {inv.id for inv in invaders} for city, invaders in self._spotter.data.items()}
        current_status = {inv.id: inv.status for invaders in self._spotter.data.values() for inv in invaders}

        # Preserve first_seen dates from previous snapshot, add new ones
        first_seen = {}
        if self._previous_snapshot:
            first_seen = dict(self._previous_snapshot.first_seen_date)

        # Add first_seen for newly discovered invaders
        for invaders in self._spotter.data.values():
            for inv in invaders:
                if inv.id not in first_seen:
                    first_seen[inv.id] = now
                    _LOGGER.debug("New invader discovered: %s", inv.id)

        # Track previous status (current status becomes previous for next comparison)
        # Only update if status changed (to preserve history)
        previous_status = {}
        if self._previous_snapshot:
            previous_status = dict(self._previous_snapshot.previous_status)

        for inv_id, status in current_status.items():
            previous_inv_status = (
                self._previous_snapshot.status_by_invader.get(inv_id) if self._previous_snapshot else None
            )
            if previous_inv_status and previous_inv_status != status:
                # Status changed - record the old status for reactivation detection
                previous_status[inv_id] = previous_inv_status
                _LOGGER.info(
                    "Status change detected: %s went from %s to %s", inv_id, previous_inv_status.value, status.value
                )

        # Update city_first_seen: preserve existing entries, add newly discovered cities
        city_first_seen: dict[str, datetime] = {}
        if self._previous_snapshot:
            city_first_seen = dict(self._previous_snapshot.city_first_seen)

        for code in self._spotter.all_known_cities:
            if code not in city_first_seen:
                city_first_seen[code] = now
                _LOGGER.info("New city discovered in awazleon: %s", code)

        snapshot = StateSnapshot(
            timestamp=now,
            invader_ids_by_city=current_ids_by_city,
            status_by_invader=current_status,
            first_seen_date=first_seen,
            previous_status=previous_status,
            city_first_seen=city_first_seen,
        )

        await self._store.async_save_snapshot(snapshot)
        self._previous_snapshot = snapshot
        _LOGGER.debug("Saved snapshot with %d invaders tracked", len(current_status))

    def detect_new_cities(self) -> list[tuple[str, str, datetime]]:
        """Return cities first seen within the configured new_city_days window.

        Returns:
            List of (city_code, city_name, first_seen_datetime) tuples,
            most recently detected first.

        """
        if not self._previous_snapshot:
            return []

        cutoff = datetime.now() - timedelta(days=self._new_city_days)
        results: list[tuple[str, str, datetime]] = []

        for code, first_seen in self._previous_snapshot.city_first_seen.items():
            if first_seen >= cutoff:
                name = self._spotter.all_known_cities.get(code, code)
                results.append((code, name, first_seen))

        results.sort(key=lambda x: x[2], reverse=True)
        return results

    def compute_world_stats(self) -> CityStats:
        """Compute aggregated statistics across all tracked cities.

        Returns:
            CityStats whose counters sum all cities. city is a placeholder.

        """
        all_cities = self.get_all_tracked_cities()

        total_invaders: list[Invader] = []
        total_flashed: list = []
        total_new: list[Invader] = []
        total_reactivated: list[Invader] = []
        total_news: list[NewsEvent] = []

        for city_code in all_cities:
            stats = self.compute_city_stats(city_code)
            total_invaders.extend(stats.all_invaders)
            total_flashed.extend(stats.flashed_invaders)
            total_new.extend(stats.new_invaders)
            total_reactivated.extend(stats.reactivated_invaders)
            total_news.extend(stats.news_events)

        world_city = City(code="WORLD", name="World", total_invaders=len(total_invaders))

        return CityStats(
            city=world_city,
            all_invaders=total_invaders,
            flashed_invaders=total_flashed,
            new_invaders=total_new,
            reactivated_invaders=total_reactivated,
            news_events=total_news,
        )

    def get_all_tracked_cities(self) -> list[str]:
        """Get list of all tracked city codes."""
        if self._spotter.data is None:
            return []
        return list(self._spotter.data.keys())

    def get_total_stats(self) -> dict[str, int]:
        """Get aggregate stats across all cities.

        Returns:
            Dict with total counts

        """
        total_invaders = 0
        total_flashed = 0
        total_unflashed = 0
        total_gone = 0

        for city_code in self.get_all_tracked_cities():
            stats = self.compute_city_stats(city_code)
            total_invaders += stats.total_count
            total_flashed += stats.flashed_count
            total_unflashed += stats.unflashed_count
            total_gone += stats.unflashed_gone_count

        return {
            "total": total_invaders,
            "flashed": total_flashed,
            "unflashed": total_unflashed,
            "gone": total_gone,
        }
