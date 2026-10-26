"""Profile sensor entities for Invader Tracker integration."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FlashInvaderProfileCoordinator

if TYPE_CHECKING:
    from .models import FollowedPlayer

_LOGGER = logging.getLogger(__name__)


async def async_setup_profile_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up profile and followed player sensor entities."""
    runtime_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: FlashInvaderProfileCoordinator = runtime_data["profile_coordinator"]

    entities: list[SensorEntity] = [
        PlayerScoreSensor(coordinator, entry),
        PlayerRankSensor(coordinator, entry),
        PlayerInvadersFoundSensor(coordinator, entry),
        PlayerCitiesFoundSensor(coordinator, entry),
        PlayerRegistrationDateSensor(coordinator, entry),
        PlayerTotalWorldSensor(coordinator, entry),
    ]

    if coordinator.track_followed and coordinator.data:
        for player in coordinator.followed_players:
            entities.extend(
                [
                    FollowedPlayerScoreSensor(coordinator, entry, player.name),
                    FollowedPlayerRankSensor(coordinator, entry, player.name),
                    FollowedPlayerInvadersFoundSensor(coordinator, entry, player.name),
                ]
            )

    async_add_entities(entities)


def _slugify(name: str) -> str:
    """Convert a player name to a safe entity id suffix."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower()).strip("_")


def _profile_device_info(entry: ConfigEntry, player_name: str) -> DeviceInfo:
    """Return device info for the main profile device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_profile")},
        name=f"User - {player_name}",
        manufacturer="Space Invader",
        model="Player Profile",
    )


def _followed_device_info(entry: ConfigEntry, player_name: str) -> DeviceInfo:
    """Return device info for a followed player device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_followed_{_slugify(player_name)}")},
        name=f"User - {player_name}",
        manufacturer="Space Invader",
        model="Followed Player",
    )


# ---------------------------------------------------------------------------
# Main player profile sensors
# ---------------------------------------------------------------------------


class ProfileBaseSensor(CoordinatorEntity["FlashInvaderProfileCoordinator"], SensorEntity):
    """Base class for main profile sensors."""

    _attr_has_entity_name = True
    _attr_state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_profile_{sensor_type}"

    @property
    def _profile(self):
        """Return profile, guaranteed non-None when available is True."""
        return self.coordinator.profile

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info, using the player's name once available."""
        name = self.coordinator.profile.name if self.coordinator.profile else "Profil"
        return _profile_device_info(self._entry, name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self.coordinator.profile is not None
        )


class PlayerScoreSensor(ProfileBaseSensor):
    """Sensor for the player's total score."""

    _attr_icon = "mdi:trophy"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "score")
        self._attr_name = "Score"

    @property
    def native_value(self) -> int | None:
        """Return the score."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.score


class PlayerRankSensor(ProfileBaseSensor):
    """Sensor for the player's global rank."""

    _attr_icon = "mdi:podium"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "rank")
        self._attr_name = "Rank"

    @property
    def native_value(self) -> int | None:
        """Return the rank."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.rank

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rank_str as attribute."""
        if not self.available:
            return {}
        profile = self.coordinator.profile
        assert profile is not None
        return {"rank_str": profile.rank_str}


class PlayerInvadersFoundSensor(ProfileBaseSensor):
    """Sensor for total invaders found."""

    _attr_icon = "mdi:space-invaders"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "invaders_found")
        self._attr_name = "Invaders Found"

    @property
    def native_value(self) -> int | None:
        """Return the total invaders found."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.si_found


class PlayerCitiesFoundSensor(ProfileBaseSensor):
    """Sensor for total cities with at least one flash."""

    _attr_icon = "mdi:city"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "cities_found")
        self._attr_name = "Cities Found"

    @property
    def native_value(self) -> int | None:
        """Return the number of cities."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.city_found


class PlayerRegistrationDateSensor(ProfileBaseSensor):
    """Sensor for the player's registration date."""

    _attr_icon = "mdi:calendar"
    _attr_state_class: SensorStateClass | None = None  # Not a measurement

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "registration_date")
        self._attr_name = "Registration Date"

    @property
    def native_value(self) -> str | None:
        """Return the registration date."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.registration_date or None


class PlayerTotalWorldSensor(ProfileBaseSensor):
    """Sensor for the total number of invaders worldwide."""

    _attr_icon = "mdi:earth"

    def __init__(self, coordinator: FlashInvaderProfileCoordinator, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, "total_world")
        self._attr_name = "Total Invaders Worldwide"

    @property
    def native_value(self) -> int | None:
        """Return the total worldwide invader count."""
        if not self.available:
            return None
        profile = self.coordinator.profile
        assert profile is not None
        return profile.total_si_count or None


# ---------------------------------------------------------------------------
# Followed player sensors
# ---------------------------------------------------------------------------


class FollowedPlayerBaseSensor(CoordinatorEntity["FlashInvaderProfileCoordinator"], SensorEntity):
    """Base class for followed player sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        player_name: str,
        sensor_type: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._entry = entry
        self._player_name = player_name
        self._attr_unique_id = f"{entry.entry_id}_followed_{_slugify(player_name)}_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this followed player."""
        return _followed_device_info(self._entry, self._player_name)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    def _get_player(self) -> FollowedPlayer | None:
        """Find this player in coordinator data."""
        for p in self.coordinator.followed_players:
            if p.name == self._player_name:
                return p
        return None


class FollowedPlayerScoreSensor(FollowedPlayerBaseSensor):
    """Score sensor for a followed player."""

    _attr_icon = "mdi:trophy"

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, player_name, "score")
        self._attr_name = "Score"

    @property
    def native_value(self) -> int | None:
        """Return the player's score."""
        if not self.available:
            return None
        player = self._get_player()
        return player.score if player else None


class FollowedPlayerRankSensor(FollowedPlayerBaseSensor):
    """Rank sensor for a followed player."""

    _attr_icon = "mdi:podium"

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, player_name, "rank")
        self._attr_name = "Rank"

    @property
    def native_value(self) -> int | None:
        """Return the player's rank."""
        if not self.available:
            return None
        player = self._get_player()
        return player.rank if player else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return rank_str as attribute."""
        if not self.available:
            return {}
        player = self._get_player()
        if not player:
            return {}
        return {"rank_str": player.rank_str}


class FollowedPlayerInvadersFoundSensor(FollowedPlayerBaseSensor):
    """Invaders found sensor for a followed player."""

    _attr_icon = "mdi:space-invaders"

    def __init__(
        self,
        coordinator: FlashInvaderProfileCoordinator,
        entry: ConfigEntry,
        player_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, entry, player_name, "invaders_found")
        self._attr_name = "Invaders Found"

    @property
    def native_value(self) -> int | None:
        """Return the player's invader count."""
        if not self.available:
            return None
        player = self._get_player()
        return player.invaders_count if player else None
