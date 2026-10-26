"""State storage for Invader Tracker integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import InvaderStatus, StateSnapshot

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class StateStore:
    """Persistent storage for invader tracker state."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store.

        Args:
            hass: Home Assistant instance
            entry_id: Config entry ID for unique storage key

        """
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")

    async def async_save_snapshot(self, snapshot: StateSnapshot) -> None:
        """Save snapshot to storage.

        Args:
            snapshot: State snapshot to save

        """
        data = {
            "timestamp": snapshot.timestamp.isoformat(),
            "invader_ids_by_city": {city: list(ids) for city, ids in snapshot.invader_ids_by_city.items()},
            "status_by_invader": {inv_id: status.value for inv_id, status in snapshot.status_by_invader.items()},
            "first_seen_date": {inv_id: dt.isoformat() for inv_id, dt in snapshot.first_seen_date.items()},
            "previous_status": {inv_id: status.value for inv_id, status in snapshot.previous_status.items()},
            "city_first_seen": {city: dt.isoformat() for city, dt in snapshot.city_first_seen.items()},
        }

        await self._store.async_save(data)
        _LOGGER.debug(
            "Saved snapshot with %d cities, %d invaders",
            len(snapshot.invader_ids_by_city),
            len(snapshot.status_by_invader),
        )

    async def async_load_snapshot(self) -> StateSnapshot | None:
        """Load snapshot from storage.

        Returns:
            StateSnapshot if found, None otherwise

        """
        data = await self._store.async_load()
        if not data:
            _LOGGER.debug("No existing snapshot found")
            return None

        try:
            snapshot = StateSnapshot(
                timestamp=datetime.fromisoformat(data["timestamp"]),
                invader_ids_by_city={city: set(ids) for city, ids in data["invader_ids_by_city"].items()},
                status_by_invader={
                    inv_id: InvaderStatus(status) for inv_id, status in data["status_by_invader"].items()
                },
                first_seen_date={
                    inv_id: datetime.fromisoformat(dt) for inv_id, dt in data.get("first_seen_date", {}).items()
                },
                previous_status={
                    inv_id: InvaderStatus(status) for inv_id, status in data.get("previous_status", {}).items()
                },
                city_first_seen={
                    city: datetime.fromisoformat(dt) for city, dt in data.get("city_first_seen", {}).items()
                },
            )
            _LOGGER.debug(
                "Loaded snapshot from %s with %d cities",
                snapshot.timestamp.isoformat(),
                len(snapshot.invader_ids_by_city),
            )
            return snapshot

        except (KeyError, ValueError) as err:
            _LOGGER.warning("Failed to parse stored snapshot: %s", err)
            return None

    async def async_remove(self) -> None:
        """Remove stored data."""
        await self._store.async_remove()
        _LOGGER.debug("Removed stored snapshot")
