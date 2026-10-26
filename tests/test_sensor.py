"""Tests for sensor entities."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.invader_tracker.const import (
    DOMAIN,
    MAX_LISTED_INVADERS,
    SENSOR_TO_FLASH,
    SENSOR_TOTAL,
)
from custom_components.invader_tracker.models import (
    City,
    CityStats,
    FlashedInvader,
    Invader,
    InvaderStatus,
)
from custom_components.invader_tracker.sensor import (
    InvaderFlashedSensor,
    InvaderNewSensor,
    InvaderToFlashSensor,
    InvaderTotalSensor,
    InvaderUnflashedGoneSensor,
    InvaderUnflashedSensor,
)


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = {"PA": []}
    return coordinator


@pytest.fixture
def mock_processor() -> MagicMock:
    """Create a mock processor."""
    processor = MagicMock()
    invaders = [
        Invader(id="PA_001", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
        Invader(id="PA_002", city_code="PA", city_name="Paris", points=20, status=InvaderStatus.OK),
        Invader(id="PA_003", city_code="PA", city_name="Paris", points=30, status=InvaderStatus.DESTROYED),
    ]
    flashed = [
        FlashedInvader(
            id="PA_001",
            name="PA_001",
            city_id=1,
            points=10,
            image_url="",
            install_date=date(2000, 1, 1),
            flash_date=datetime(2024, 1, 15, 10, 30, 0),
        ),
    ]
    city = City(code="PA", name="Paris", total_invaders=3)
    stats = CityStats(
        city=city,
        all_invaders=invaders,
        flashed_invaders=flashed,
        new_invaders=[invaders[1]],  # PA_002 is new
        reactivated_invaders=[],
    )
    processor.compute_city_stats = MagicMock(return_value=stats)
    processor.get_flashed_for_city = MagicMock(return_value=flashed)
    return processor


@pytest.fixture
def mock_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    return entry


@pytest.fixture
def mock_flash_coordinator() -> MagicMock:
    """Create a mock flash coordinator."""
    coordinator = MagicMock()
    coordinator.last_update_success = True
    coordinator.data = []
    coordinator.get_city_si_count = MagicMock(return_value=1589)
    return coordinator


class TestInvaderTotalSensor:
    """Tests for InvaderTotalSensor."""

    def test_native_value(self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry) -> None:
        """Test total count from awazleon."""
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value == 3

    def test_native_value_fallback_to_flash_api(
        self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry
    ) -> None:
        """Test total count falls back to Flash Invader API when awazleon is down."""
        mock_coordinator.last_update_success = False
        mock_coordinator.data = None
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value == 1589

    def test_unavailable_when_both_down(
        self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry
    ) -> None:
        """Test sensor returns None when both awazleon and flash API are down."""
        mock_coordinator.last_update_success = False
        mock_coordinator.data = None
        mock_flash_coordinator.last_update_success = False
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value is None

    def test_attributes(self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include flashable count."""
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        attrs = sensor.extra_state_attributes

        assert "flashable_count" in attrs
        assert attrs["flashable_count"] == 2  # PA_001 and PA_002

    def test_unavailable(self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry) -> None:
        """Test sensor returns None when unavailable."""
        mock_coordinator.data = None
        mock_coordinator.last_update_success = False
        mock_flash_coordinator.last_update_success = False
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value is None
        assert sensor.extra_state_attributes == {}

    def test_unique_id(self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry) -> None:
        """Test unique ID format."""
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.unique_id == f"test_entry_PA_{SENSOR_TOTAL}"

    def test_device_info(self, mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry) -> None:
        """Test device info."""
        sensor = InvaderTotalSensor(mock_coordinator, mock_flash_coordinator, mock_processor, mock_entry, "PA", "Paris")
        info = sensor.device_info
        assert (DOMAIN, "test_entry_PA") in info["identifiers"]
        assert "Paris" in info["name"]


class TestInvaderFlashedSensor:
    """Tests for InvaderFlashedSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test flashed count."""
        sensor = InvaderFlashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value == 1

    def test_attributes_with_flash_date(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test no extra attributes on flashed sensor."""
        sensor = InvaderFlashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes is None or sensor.extra_state_attributes == {}

    def test_attributes_with_none_flash_date(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test no extra attributes on flashed sensor (None flash_date)."""
        sensor = InvaderFlashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes is None or sensor.extra_state_attributes == {}


class TestInvaderUnflashedSensor:
    """Tests for InvaderUnflashedSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unflashed count (only flashable, not flashed)."""
        sensor = InvaderUnflashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        # PA_002 is OK and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test the unflashed sensor lists the IDs left to flash."""
        sensor = InvaderUnflashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes == {"invaders": ["PA_002"]}

    def test_attributes_unavailable(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test no attributes when the sensor is unavailable."""
        mock_coordinator.last_update_success = False
        sensor = InvaderUnflashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes == {}

    def test_attributes_capped(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test the ID list is capped: recorder drops attributes over 16 KiB."""
        stats = mock_processor.compute_city_stats.return_value
        stats.all_invaders = [
            Invader(
                id=f"PA_{i}",
                city_code="PA",
                city_name="Paris",
                points=10,
                status=InvaderStatus.OK,
            )
            for i in range(MAX_LISTED_INVADERS + 100)
        ]
        stats.flashed_invaders = []

        sensor = InvaderUnflashedSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        attrs = sensor.extra_state_attributes

        assert len(attrs["invaders"]) == MAX_LISTED_INVADERS
        assert attrs["invaders_truncated"] is True


class TestInvaderUnflashedGoneSensor:
    """Tests for InvaderUnflashedGoneSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unflashed gone count."""
        sensor = InvaderUnflashedGoneSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        # PA_003 is DESTROYED and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test the unflashed gone sensor lists the IDs that can no longer be flashed."""
        sensor = InvaderUnflashedGoneSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes == {"invaders": ["PA_003"]}

    def test_attributes_unavailable(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test no attributes when the sensor is unavailable."""
        mock_coordinator.last_update_success = False
        sensor = InvaderUnflashedGoneSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes == {}


class TestInvaderNewSensor:
    """Tests for InvaderNewSensor."""

    def test_native_value(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test new + reactivated count (unflashed only)."""
        sensor = InvaderNewSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        # PA_002 is new and not flashed
        assert sensor.native_value == 1

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test attributes include new/reactivated breakdown."""
        sensor = InvaderNewSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        attrs = sensor.extra_state_attributes

        assert attrs["new_count"] == 1
        assert attrs["reactivated_count"] == 0


class TestInvaderToFlashSensor:
    """Tests for InvaderToFlashSensor."""

    def test_native_value_with_targets(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test CSV list of invader IDs."""
        sensor = InvaderToFlashSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        # PA_002 is new and not flashed
        assert sensor.native_value == "PA_002"

    def test_native_value_no_targets(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test None when no targets (HA convention, see 2.6.0)."""
        stats = mock_processor.compute_city_stats.return_value
        stats.new_invaders = []
        stats.reactivated_invaders = []

        sensor = InvaderToFlashSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value is None

    def test_attributes(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test no extra attributes on to_flash sensor."""
        sensor = InvaderToFlashSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.extra_state_attributes is None or sensor.extra_state_attributes == {}

    def test_unavailable(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test sensor returns None when unavailable."""
        mock_coordinator.last_update_success = False
        sensor = InvaderToFlashSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.native_value is None
        assert sensor.extra_state_attributes is None or sensor.extra_state_attributes == {}

    def test_unique_id(self, mock_coordinator, mock_processor, mock_entry) -> None:
        """Test unique ID format."""
        sensor = InvaderToFlashSensor(mock_coordinator, mock_processor, mock_entry, "PA", "Paris")
        assert sensor.unique_id == f"test_entry_PA_{SENSOR_TO_FLASH}"
