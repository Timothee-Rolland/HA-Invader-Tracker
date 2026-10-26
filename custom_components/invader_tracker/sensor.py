"""Sensor entities for Invader Tracker integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CITIES,
    DOMAIN,
    SENSOR_FLASHED,
    SENSOR_NEW,
    SENSOR_TO_FLASH,
    SENSOR_TOTAL,
    SENSOR_UNFLASHED,
    SENSOR_UNFLASHED_GONE,
)

if TYPE_CHECKING:
    from .coordinator import FlashInvaderCoordinator, InvaderSpotterCoordinator
    from .processor import DataProcessor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Invader Tracker sensors from config entry."""
    from .sensor_profile import async_setup_profile_entities
    from .sensor_world import async_setup_world_entities

    runtime_data = hass.data[DOMAIN][entry.entry_id]

    spotter_coordinator: InvaderSpotterCoordinator = runtime_data["spotter_coordinator"]
    flash_coordinator: FlashInvaderCoordinator = runtime_data["flash_coordinator"]
    processor: DataProcessor = runtime_data["processor"]
    # Read from options first (modified config), then data (initial config)
    cities: dict[str, str] = entry.options.get(CONF_CITIES) or entry.data.get(CONF_CITIES, {})

    # Set up profile entities (always, since UID is required)
    await async_setup_profile_entities(hass, entry, async_add_entities)

    # Set up world aggregate entities
    await async_setup_world_entities(hass, entry, async_add_entities)

    entities: list[SensorEntity] = []

    for city_code, city_name in cities.items():
        # Create sensors for each city
        entities.extend(
            [
                InvaderTotalSensor(spotter_coordinator, flash_coordinator, processor, entry, city_code, city_name),
                InvaderFlashedSensor(flash_coordinator, processor, entry, city_code, city_name),
                InvaderUnflashedSensor(spotter_coordinator, processor, entry, city_code, city_name),
                InvaderUnflashedGoneSensor(spotter_coordinator, processor, entry, city_code, city_name),
                InvaderNewSensor(spotter_coordinator, processor, entry, city_code, city_name),
                InvaderToFlashSensor(spotter_coordinator, processor, entry, city_code, city_name),
            ]
        )

    async_add_entities(entities)


class InvaderBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Invader Tracker sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            processor: Data processor
            entry: Config entry
            city_code: City code
            city_name: City display name
            sensor_type: Type of sensor

        """
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._city_code = city_code
        self._city_name = city_name
        self._sensor_type = sensor_type

        self._attr_unique_id = f"{entry.entry_id}_{city_code}_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._city_code}")},
            name=f"City - {self._city_name}",
            manufacturer="Space Invader",
            model="City Tracker",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if self.coordinator.data is None:
            return False
        return self._city_code in self.coordinator.data


class InvaderTotalSensor(InvaderBaseSensor):
    """Sensor for total invaders in a city."""

    _attr_icon = "mdi:space-invaders"
    _attr_translation_key = "total"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        flash_coordinator: FlashInvaderCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, processor, entry, city_code, city_name, SENSOR_TOTAL)
        self._flash_coordinator = flash_coordinator
        self._attr_name = "Total Invaders"

    @property
    def available(self) -> bool:
        """Return if entity is available — awazleon or flash invader API is enough."""
        if super().available:
            return True
        return (
            self._flash_coordinator.last_update_success
            and self._flash_coordinator.get_city_si_count(self._city_code) is not None
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.available:
            return None
        if super().available:
            stats = self._processor.compute_city_stats(self._city_code)
            return stats.total_count
        return self._flash_coordinator.get_city_si_count(self._city_code)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not super().available:
            return {}
        stats = self._processor.compute_city_stats(self._city_code)
        return {
            "flashable_count": sum(1 for inv in stats.all_invaders if inv.is_flashable),
        }


class InvaderFlashedSensor(CoordinatorEntity["FlashInvaderCoordinator"], SensorEntity):
    """Sensor for flashed invaders in a city — depends only on Flash Invader API."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:check-circle"
    _attr_translation_key = "flashed"

    def __init__(
        self,
        coordinator: FlashInvaderCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._city_code = city_code
        self._city_name = city_name
        self._attr_unique_id = f"{entry.entry_id}_{city_code}_{SENSOR_FLASHED}"
        self._attr_name = "Flashed"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._city_code}")},
            name=f"City - {self._city_name}",
            manufacturer="Space Invader",
            model="City Tracker",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.available:
            return None
        return len(self._processor.get_flashed_for_city(self._city_code))


class InvaderUnflashedSensor(InvaderBaseSensor):
    """Sensor for unflashed but available invaders."""

    _attr_icon = "mdi:crosshairs-question"
    _attr_translation_key = "unflashed"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, processor, entry, city_code, city_name, SENSOR_UNFLASHED)
        self._attr_name = "Unflashed (Available)"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.available:
            return None
        stats = self._processor.compute_city_stats(self._city_code)
        return stats.unflashed_count


class InvaderUnflashedGoneSensor(InvaderBaseSensor):
    """Sensor for unflashed and no longer available invaders."""

    _attr_icon = "mdi:ghost-off"
    _attr_translation_key = "unflashed_gone"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, processor, entry, city_code, city_name, SENSOR_UNFLASHED_GONE)
        self._attr_name = "Unflashed (Gone)"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.available:
            return None
        stats = self._processor.compute_city_stats(self._city_code)
        return stats.unflashed_gone_count


class InvaderNewSensor(InvaderBaseSensor):
    """Sensor for new and reactivated invaders (not yet flashed)."""

    _attr_icon = "mdi:new-box"
    _attr_translation_key = "new"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, processor, entry, city_code, city_name, SENSOR_NEW)
        self._attr_name = "New & Reactivated"

    @property
    def native_value(self) -> int | None:
        """Return the count of unflashed new and reactivated invaders."""
        if not self.available:
            return None
        stats = self._processor.compute_city_stats(self._city_code)
        return stats.unflashed_new_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.available:
            return {}
        stats = self._processor.compute_city_stats(self._city_code)
        return {
            "new_count": len(stats.unflashed_new),
            "reactivated_count": len(stats.unflashed_reactivated),
        }


class InvaderToFlashSensor(CoordinatorEntity, SensorEntity):
    """Text sensor displaying the list of new/reactivated invaders to flash."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:format-list-bulleted"
    _attr_translation_key = "to_flash"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._city_code = city_code
        self._city_name = city_name
        self._attr_unique_id = f"{entry.entry_id}_{city_code}_{SENSOR_TO_FLASH}"
        self._attr_name = "Invaders To Flash"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._city_code}")},
            name=f"City - {self._city_name}",
            manufacturer="Space Invader",
            model="City Tracker",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        if self.coordinator.data is None:
            return False
        return self._city_code in self.coordinator.data

    @property
    def native_value(self) -> str | None:
        """Return the list of new and reactivated unflashed invaders as text."""
        if not self.available:
            return None
        stats = self._processor.compute_city_stats(self._city_code)
        to_flash_ids = [inv.id for inv in stats.unflashed_new] + [inv.id for inv in stats.unflashed_reactivated]
        return ", ".join(to_flash_ids) if to_flash_ids else None
