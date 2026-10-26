"""Binary sensor entities for Invader Tracker integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_HAS_NEW, CONF_CITIES, DOMAIN

if TYPE_CHECKING:
    from .coordinator import InvaderSpotterCoordinator
    from .processor import DataProcessor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Invader Tracker binary sensors from config entry."""
    from .binary_sensor_world import async_setup_world_binary_entities

    runtime_data = hass.data[DOMAIN][entry.entry_id]

    spotter_coordinator: InvaderSpotterCoordinator = runtime_data["spotter_coordinator"]
    processor: DataProcessor = runtime_data["processor"]
    # Read from options first (modified config), then data (initial config)
    cities: dict[str, str] = entry.options.get(CONF_CITIES) or entry.data.get(CONF_CITIES, {})

    entities: list[BinarySensorEntity] = []

    for city_code, city_name in cities.items():
        entities.append(InvaderHasNewBinarySensor(spotter_coordinator, processor, entry, city_code, city_name))

    async_add_entities(entities)

    # Set up world aggregate binary entities
    await async_setup_world_binary_entities(hass, entry, async_add_entities)


class InvaderHasNewBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating if there are new invaders."""

    _attr_has_entity_name = True
    # No device_class to avoid confusing "à jour"/"Mise à jour" labels
    _attr_icon = "mdi:alert-decagram"
    _attr_translation_key = "has_new"

    def __init__(
        self,
        coordinator: InvaderSpotterCoordinator,
        processor: DataProcessor,
        entry: ConfigEntry,
        city_code: str,
        city_name: str,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: Data coordinator
            processor: Data processor
            entry: Config entry
            city_code: City code
            city_name: City display name

        """
        super().__init__(coordinator)
        self._processor = processor
        self._entry = entry
        self._city_code = city_code
        self._city_name = city_name

        self._attr_unique_id = f"{entry.entry_id}_{city_code}_{BINARY_SENSOR_HAS_NEW}"
        self._attr_name = "Has New Invaders"

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
    def is_on(self) -> bool | None:
        """Return true if there are new invaders."""
        if not self.available:
            return None
        stats = self._processor.compute_city_stats(self._city_code)
        return stats.unflashed_new_count > 0
