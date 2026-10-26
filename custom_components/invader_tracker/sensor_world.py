"""World aggregate sensor entities for Invader Tracker integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import InvaderSpotterCoordinator
    from .processor import DataProcessor

_LOGGER = logging.getLogger(__name__)

_WORLD_DEVICE_ID = "world"


def _world_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return device info for the World aggregate device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{_WORLD_DEVICE_ID}")},
        name="World",
        manufacturer="Space Invader",
        model="World Tracker",
    )


async def async_setup_world_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up world aggregate sensor entities."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: InvaderSpotterCoordinator = runtime_data["spotter_coordinator"]
    processor: DataProcessor = runtime_data["processor"]

    async_add_entities(
        [
            WorldTotalSensor(coordinator, processor, entry),
            WorldFlashedSensor(coordinator, processor, entry),
            WorldUnflashedSensor(coordinator, processor, entry),
            WorldUnflashedGoneSensor(coordinator, processor, entry),
            WorldNewSensor(coordinator, processor, entry),
            WorldToFlashSensor(coordinator, processor, entry),
            WorldNewCitySensor(coordinator, processor, entry),
        ]
    )


class WorldBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for world aggregate sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{_WORLD_DEVICE_ID}_{sensor_type}"

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


class WorldTotalSensor(WorldBaseSensor):
    """Total invaders across all tracked cities."""

    _attr_icon = "mdi:earth"
    _attr_name = "Total Invaders"

    def __init__(self, coordinator, processor, entry) -> None:
        super().__init__(coordinator, processor, entry, "total")

    @property
    def native_value(self) -> int | None:
        if not self.available:
            return None
        stats = self._processor.compute_world_stats()
        return stats.total_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.available:
            return {}
        stats = self._processor.compute_world_stats()
        return {
            "flashable_count": sum(1 for inv in stats.all_invaders if inv.is_flashable),
        }


class WorldFlashedSensor(WorldBaseSensor):
    """Flashed invaders across all tracked cities."""

    _attr_icon = "mdi:check-circle"
    _attr_name = "Flashed"

    def __init__(self, coordinator, processor, entry) -> None:
        super().__init__(coordinator, processor, entry, "flashed")

    @property
    def native_value(self) -> int | None:
        if not self.available:
            return None
        return self._processor.compute_world_stats().flashed_count


class WorldUnflashedSensor(WorldBaseSensor):
    """Unflashed but available invaders across all tracked cities."""

    _attr_icon = "mdi:crosshairs-question"
    _attr_name = "Unflashed (Available)"

    def __init__(self, coordinator, processor, entry) -> None:
        super().__init__(coordinator, processor, entry, "unflashed")

    @property
    def native_value(self) -> int | None:
        if not self.available:
            return None
        return self._processor.compute_world_stats().unflashed_count


class WorldUnflashedGoneSensor(WorldBaseSensor):
    """Unflashed and gone invaders across all tracked cities."""

    _attr_icon = "mdi:ghost-off"
    _attr_name = "Unflashed (Gone)"

    def __init__(self, coordinator, processor, entry) -> None:
        super().__init__(coordinator, processor, entry, "unflashed_gone")

    @property
    def native_value(self) -> int | None:
        if not self.available:
            return None
        return self._processor.compute_world_stats().unflashed_gone_count


class WorldNewSensor(WorldBaseSensor):
    """New & reactivated invaders (not yet flashed) across all tracked cities."""

    _attr_icon = "mdi:new-box"
    _attr_name = "New & Reactivated"

    def __init__(self, coordinator, processor, entry) -> None:
        super().__init__(coordinator, processor, entry, "new")

    @property
    def native_value(self) -> int | None:
        if not self.available:
            return None
        return self._processor.compute_world_stats().unflashed_new_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.available:
            return {}
        stats = self._processor.compute_world_stats()
        return {
            "new_count": len(stats.unflashed_new),
            "reactivated_count": len(stats.unflashed_reactivated),
        }


class WorldToFlashSensor(CoordinatorEntity, SensorEntity):
    """List of new/reactivated unflashed invaders across all tracked cities."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:format-list-bulleted"
    _attr_name = "Invaders To Flash"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{_WORLD_DEVICE_ID}_to_flash"

    @property
    def device_info(self) -> DeviceInfo:
        return _world_device_info(self._entry)

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and len(self.coordinator.data) > 0
        )

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        stats = self._processor.compute_world_stats()
        to_flash_ids = [inv.id for inv in stats.unflashed_new] + [inv.id for inv in stats.unflashed_reactivated]
        return ", ".join(to_flash_ids) if to_flash_ids else None


class WorldNewCitySensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the most recently invaded city (within the configured window).

    Value = city name if a new city was detected within new_city_days, else None.
    Attributes:
      - detected_at: ISO datetime of first detection
      - also_new: list of other cities detected in the same window (if any)
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:map-marker-plus"
    _attr_name = "New City Invaded"
    _attr_state_class = None  # Not a measurement — string value

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{_WORLD_DEVICE_ID}_new_city"

    @property
    def device_info(self) -> DeviceInfo:
        return _world_device_info(self._entry)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> str | None:
        """Return the most recently detected new city name, or None."""
        new_cities = self._processor.detect_new_cities()
        if not new_cities:
            return None
        _code, name, _dt = new_cities[0]
        return name

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detection date and any additional new cities."""
        new_cities = self._processor.detect_new_cities()
        if not new_cities:
            return {}
        _code, _name, detected_at = new_cities[0]
        attrs: dict[str, Any] = {"detected_at": detected_at.isoformat()}
        if len(new_cities) > 1:
            attrs["also_new"] = [name for _c, name, _d in new_cities[1:]]
        return attrs
