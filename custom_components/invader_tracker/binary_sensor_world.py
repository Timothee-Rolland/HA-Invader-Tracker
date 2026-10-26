"""World aggregate binary sensor for Invader Tracker integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .sensor_world import _world_device_info

if TYPE_CHECKING:
    from .coordinator import InvaderSpotterCoordinator
    from .processor import DataProcessor

_LOGGER = logging.getLogger(__name__)


async def async_setup_world_binary_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up world aggregate binary sensor entities."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: InvaderSpotterCoordinator = runtime_data["spotter_coordinator"]
    processor: DataProcessor = runtime_data["processor"]

    async_add_entities(
        [
            WorldHasNewBinarySensor(coordinator, processor, entry),
        ]
    )


class WorldHasNewBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor — true if any tracked city has new or reactivated invaders."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:alert-decagram"
    _attr_name = "Has New Invaders"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_world_has_new"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return _world_device_info(self._entry)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and len(self.coordinator.data) > 0
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if any city has new or reactivated unflashed invaders."""
        if not self.available:
            return None
        return self._processor.compute_world_stats().unflashed_new_count > 0
