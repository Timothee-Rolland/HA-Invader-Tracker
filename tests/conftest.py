"""Pytest fixtures for Invader Tracker tests."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest
from homeassistant.config_entries import ConfigEntry

from custom_components.invader_tracker.const import DOMAIN
from custom_components.invader_tracker.models import (
    FlashedInvader,
    Invader,
    InvaderStatus,
)


@pytest.fixture
def config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = {}
    entry.options = {}
    entry.unique_id = "test_unique_id"
    entry.version = 1
    return entry


@pytest.fixture
def mock_flash_invader_response() -> dict:
    """Create mock Flash Invader API response."""
    return {
        "invaders": {
            "PA_001": {
                "name": "PA_001",
                "point": 10,
                "city_id": 1,
                "image_url": "https://example.com/pa001.jpg",
                "date_pos": "2000-01-01",
                "date_flash": "2024-01-15 10:30:00",
            },
            "PA_002": {
                "name": "PA_002",
                "point": 20,
                "city_id": 1,
                "image_url": "https://example.com/pa002.jpg",
                "date_pos": "2000-01-02",
                "date_flash": "2024-02-20 14:45:00",
            },
            "LYN_001": {
                "name": "LYN_001",
                "point": 30,
                "city_id": 2,
                "image_url": "https://example.com/lyn001.jpg",
                "date_pos": "2005-03-15",
                "date_flash": "2024-03-10 09:00:00",
            },
        }
    }


@pytest.fixture
def mock_flashed_invaders() -> list[FlashedInvader]:
    """Create mock FlashedInvader objects."""
    return [
        FlashedInvader(
            id="PA_001",
            name="PA_001",
            city_id=1,
            points=10,
            image_url="https://example.com/pa001.jpg",
            install_date=date(2000, 1, 1),
            flash_date=datetime(2024, 1, 15, 10, 30, 0),
        ),
        FlashedInvader(
            id="PA_002",
            name="PA_002",
            city_id=1,
            points=20,
            image_url="https://example.com/pa002.jpg",
            install_date=date(2000, 1, 2),
            flash_date=datetime(2024, 2, 20, 14, 45, 0),
        ),
    ]


@pytest.fixture
def mock_invaders_paris() -> list[Invader]:
    """Create mock Invader objects for Paris."""
    return [
        Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 1),
        ),
        Invader(
            id="PA_002",
            city_code="PA",
            city_name="Paris",
            points=20,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 2),
        ),
        Invader(
            id="PA_003",
            city_code="PA",
            city_name="Paris",
            points=30,
            status=InvaderStatus.OK,
            install_date=date(2000, 1, 3),
        ),
        Invader(
            id="PA_004",
            city_code="PA",
            city_name="Paris",
            points=40,
            status=InvaderStatus.DESTROYED,
            install_date=date(2000, 1, 4),
        ),
    ]
