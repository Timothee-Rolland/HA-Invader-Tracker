"""Tests for city device removal functionality."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.invader_tracker.const import (
    CONF_CITIES,
    CONF_UID,
    DOMAIN,
)


def _make_hass(entry_id: str) -> MagicMock:
    """Create a minimal mock hass object."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.config_entries = MagicMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    return hass


def _make_entry(entry_id: str, data: dict, options: dict | None = None) -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = data
    entry.options = options or {}
    return entry


@pytest.mark.asyncio
async def test_city_removal_deletes_device() -> None:
    """Test that removing a city deletes its device."""
    entry_id = "test_entry_id"
    initial_cities = {"PA": "Paris", "LYN": "Lyon"}
    new_cities = {"PA": "Paris"}

    entry = _make_entry(
        entry_id,
        data={CONF_UID: "12345678-1234-1234-1234-123456789abc", CONF_CITIES: initial_cities},
        options={CONF_CITIES: new_cities},
    )

    hass = _make_hass(entry_id)
    hass.data[DOMAIN][entry_id] = {
        "spotter_coordinator": MagicMock(update_cities=MagicMock()),
        "processor": MagicMock(set_city_names=MagicMock()),
    }

    device_registry = MagicMock()
    device_registry.async_get_device = MagicMock(return_value=MagicMock(id="device_id_lyn"))
    device_registry.async_remove_device = MagicMock()

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        from custom_components.invader_tracker import async_update_options

        await async_update_options(hass, entry)

    device_registry.async_get_device.assert_called_once_with(identifiers={(DOMAIN, f"{entry_id}_LYN")})
    device_registry.async_remove_device.assert_called_once_with("device_id_lyn")

    runtime_data = hass.data[DOMAIN][entry_id]
    runtime_data["spotter_coordinator"].update_cities.assert_called_once_with(new_cities)
    runtime_data["processor"].set_city_names.assert_called_once_with(new_cities)


@pytest.mark.asyncio
async def test_city_removal_no_device_found() -> None:
    """Test handling when device is not found in registry."""
    entry_id = "test_entry_id"
    initial_cities = {"PA": "Paris", "LYN": "Lyon"}
    new_cities = {"PA": "Paris"}

    entry = _make_entry(
        entry_id,
        data={CONF_UID: "12345678-1234-1234-1234-123456789abc", CONF_CITIES: initial_cities},
        options={CONF_CITIES: new_cities},
    )

    hass = _make_hass(entry_id)
    hass.data[DOMAIN][entry_id] = {
        "spotter_coordinator": MagicMock(update_cities=MagicMock()),
        "processor": MagicMock(set_city_names=MagicMock()),
    }

    device_registry = MagicMock()
    device_registry.async_get_device = MagicMock(return_value=None)
    device_registry.async_remove_device = MagicMock()

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        from custom_components.invader_tracker import async_update_options

        await async_update_options(hass, entry)

    device_registry.async_remove_device.assert_not_called()


@pytest.mark.asyncio
async def test_city_addition_no_device_removal() -> None:
    """Test that adding a city doesn't trigger device removal."""
    entry_id = "test_entry_id"
    initial_cities = {"PA": "Paris"}
    new_cities = {"PA": "Paris", "LYN": "Lyon"}

    entry = _make_entry(
        entry_id,
        data={CONF_UID: "12345678-1234-1234-1234-123456789abc", CONF_CITIES: initial_cities},
        options={CONF_CITIES: new_cities},
    )

    hass = _make_hass(entry_id)
    hass.data[DOMAIN][entry_id] = {
        "spotter_coordinator": MagicMock(update_cities=MagicMock()),
        "processor": MagicMock(set_city_names=MagicMock()),
    }

    device_registry = MagicMock()
    device_registry.async_get_device = MagicMock()
    device_registry.async_remove_device = MagicMock()

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        return_value=device_registry,
    ):
        from custom_components.invader_tracker import async_update_options

        await async_update_options(hass, entry)

    device_registry.async_get_device.assert_not_called()
    device_registry.async_remove_device.assert_not_called()
