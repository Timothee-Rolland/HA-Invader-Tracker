"""Tests for DataProcessor."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.invader_tracker.models import (
    FlashedInvader,
    Invader,
    InvaderStatus,
    NewsEvent,
    NewsEventType,
    StateSnapshot,
)
from custom_components.invader_tracker.processor import DataProcessor


@pytest.fixture
def mock_spotter_coordinator() -> MagicMock:
    """Create a mock InvaderSpotterCoordinator."""
    coordinator = MagicMock()
    coordinator.data = {
        "PA": [
            Invader(id="PA_001", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
            Invader(id="PA_002", city_code="PA", city_name="Paris", points=20, status=InvaderStatus.OK),
            Invader(id="PA_003", city_code="PA", city_name="Paris", points=30, status=InvaderStatus.DESTROYED),
        ],
    }
    coordinator.get_news_events = AsyncMock(return_value=[])
    coordinator.get_news_for_city = MagicMock(return_value=[])
    return coordinator


@pytest.fixture
def mock_flash_coordinator() -> MagicMock:
    """Create a mock FlashInvaderCoordinator."""
    coordinator = MagicMock()
    coordinator.get_flashed_for_city = MagicMock(
        return_value=[
            FlashedInvader(
                id="PA_001",
                name="PA_001",
                city_id=1,
                points=10,
                image_url="https://example.com/pa001.jpg",
                install_date=date(2000, 1, 1),
                flash_date=datetime(2024, 1, 15, 10, 30, 0),
            ),
        ]
    )
    return coordinator


@pytest.fixture
def mock_store() -> MagicMock:
    """Create a mock StateStore."""
    store = MagicMock()
    store.async_load_snapshot = AsyncMock(return_value=None)
    store.async_save_snapshot = AsyncMock()
    return store


@pytest.fixture
def processor(mock_spotter_coordinator, mock_flash_coordinator, mock_store) -> DataProcessor:
    """Create a DataProcessor with mocked dependencies."""
    proc = DataProcessor(mock_spotter_coordinator, mock_flash_coordinator, mock_store, news_days=30)
    proc.set_city_names({"PA": "Paris"})
    return proc


class TestComputeCityStats:
    """Tests for compute_city_stats."""

    def test_basic_stats(self, processor: DataProcessor) -> None:
        """Test basic city stats computation."""
        stats = processor.compute_city_stats("PA")

        assert stats.total_count == 3
        assert stats.flashed_count == 1
        # PA_002 is unflashed and OK (flashable)
        assert stats.unflashed_count == 1
        # PA_003 is unflashed and DESTROYED (not flashable)
        assert stats.unflashed_gone_count == 1

    def test_city_name_mapping(self, processor: DataProcessor) -> None:
        """Test that city name is taken from set_city_names."""
        stats = processor.compute_city_stats("PA")
        assert stats.city.name == "Paris"
        assert stats.city.code == "PA"

    def test_no_data(self, processor: DataProcessor, mock_spotter_coordinator) -> None:
        """Test stats when spotter has no data."""
        mock_spotter_coordinator.data = None
        stats = processor.compute_city_stats("PA")

        assert stats.total_count == 0
        assert stats.flashed_count == 1  # Flash API still returns data
        assert stats.unflashed_count == 0

    def test_unknown_city(self, processor: DataProcessor) -> None:
        """Test stats for a city not in data."""
        stats = processor.compute_city_stats("LYN")
        assert stats.total_count == 0

    def test_news_based_new_invaders(self, processor: DataProcessor, mock_spotter_coordinator) -> None:
        """Test that new invaders come from news events."""
        news_events = [
            NewsEvent(
                event_type=NewsEventType.ADDED,
                invader_id="PA_002",
                city_code="PA",
                event_date=date.today(),
            ),
        ]
        mock_spotter_coordinator.get_news_for_city = MagicMock(return_value=news_events)

        stats = processor.compute_city_stats("PA")
        assert stats.new_count == 1
        assert stats.new_invaders[0].id == "PA_002"

    def test_news_based_reactivated(self, processor: DataProcessor, mock_spotter_coordinator) -> None:
        """Test that reactivated invaders come from news events."""
        news_events = [
            NewsEvent(
                event_type=NewsEventType.REACTIVATED,
                invader_id="PA_002",
                city_code="PA",
                event_date=date.today(),
            ),
        ]
        mock_spotter_coordinator.get_news_for_city = MagicMock(return_value=news_events)

        stats = processor.compute_city_stats("PA")
        assert len(stats.reactivated_invaders) == 1
        assert stats.reactivated_invaders[0].id == "PA_002"


class TestDetectChanges:
    """Tests for detect_changes."""

    def test_no_previous_snapshot(self, processor: DataProcessor) -> None:
        """Test change detection with no previous snapshot."""
        changes = processor.detect_changes("PA")
        assert changes.new_invaders == []
        assert changes.reactivated_invaders == []

    def test_with_previous_snapshot(self, processor: DataProcessor) -> None:
        """Test change detection with previous snapshot."""
        # Create a snapshot where PA_002 was first seen recently
        now = datetime.now()
        processor._previous_snapshot = StateSnapshot(
            timestamp=now - timedelta(hours=1),
            invader_ids_by_city={"PA": {"PA_001", "PA_002", "PA_003"}},
            status_by_invader={
                "PA_001": InvaderStatus.OK,
                "PA_002": InvaderStatus.OK,
                "PA_003": InvaderStatus.DESTROYED,
            },
            first_seen_date={
                "PA_001": now - timedelta(days=365),
                "PA_002": now - timedelta(days=5),  # Recently added
                "PA_003": now - timedelta(days=365),
            },
        )

        changes = processor.detect_changes("PA", recently_added_days=30)
        # PA_002 was first seen 5 days ago (within 30 days), so it's "new"
        assert len(changes.new_invaders) == 1
        assert changes.new_invaders[0].id == "PA_002"

    def test_reactivated_detection(self, processor: DataProcessor) -> None:
        """Test reactivated invader detection via snapshot."""
        now = datetime.now()
        # PA_003 was previously DESTROYED, now it's OK in the data
        processor._spotter.data["PA"][2] = Invader(
            id="PA_003",
            city_code="PA",
            city_name="Paris",
            points=30,
            status=InvaderStatus.OK,
        )
        processor._previous_snapshot = StateSnapshot(
            timestamp=now - timedelta(hours=1),
            invader_ids_by_city={"PA": {"PA_001", "PA_002", "PA_003"}},
            status_by_invader={
                "PA_001": InvaderStatus.OK,
                "PA_002": InvaderStatus.OK,
                "PA_003": InvaderStatus.OK,
            },
            first_seen_date={
                "PA_001": now - timedelta(days=365),
                "PA_002": now - timedelta(days=365),
                "PA_003": now - timedelta(days=365),
            },
            previous_status={
                "PA_003": InvaderStatus.DESTROYED,
            },
        )

        changes = processor.detect_changes("PA")
        assert len(changes.reactivated_invaders) == 1
        assert changes.reactivated_invaders[0].id == "PA_003"

    def test_no_data(self, processor: DataProcessor) -> None:
        """Test change detection when spotter has no data."""
        processor._previous_snapshot = StateSnapshot(
            timestamp=datetime.now(),
            invader_ids_by_city={"PA": {"PA_001"}},
            status_by_invader={"PA_001": InvaderStatus.OK},
        )
        processor._spotter.data = None

        changes = processor.detect_changes("PA")
        assert changes.new_invaders == []
        assert changes.reactivated_invaders == []


class TestAsyncSaveSnapshot:
    """Tests for async_save_snapshot."""

    @pytest.mark.asyncio
    async def test_save_snapshot(self, processor: DataProcessor, mock_store) -> None:
        """Test saving a snapshot."""
        await processor.async_save_snapshot()

        mock_store.async_save_snapshot.assert_called_once()
        saved_snapshot = mock_store.async_save_snapshot.call_args[0][0]

        assert isinstance(saved_snapshot, StateSnapshot)
        assert "PA" in saved_snapshot.invader_ids_by_city
        assert saved_snapshot.invader_ids_by_city["PA"] == {"PA_001", "PA_002", "PA_003"}
        assert saved_snapshot.status_by_invader["PA_001"] == InvaderStatus.OK

    @pytest.mark.asyncio
    async def test_save_preserves_first_seen(self, processor: DataProcessor, mock_store) -> None:
        """Test that first_seen dates are preserved across saves."""
        old_time = datetime(2024, 1, 1)
        processor._previous_snapshot = StateSnapshot(
            timestamp=old_time,
            invader_ids_by_city={"PA": {"PA_001"}},
            status_by_invader={"PA_001": InvaderStatus.OK},
            first_seen_date={"PA_001": old_time},
        )

        await processor.async_save_snapshot()

        saved = mock_store.async_save_snapshot.call_args[0][0]
        # PA_001's first_seen should be preserved from previous snapshot
        assert saved.first_seen_date["PA_001"] == old_time
        # PA_002 and PA_003 should have new first_seen dates
        assert "PA_002" in saved.first_seen_date
        assert "PA_003" in saved.first_seen_date

    @pytest.mark.asyncio
    async def test_save_no_data(self, processor: DataProcessor, mock_store, mock_spotter_coordinator) -> None:
        """Test saving when spotter has no data."""
        mock_spotter_coordinator.data = None

        await processor.async_save_snapshot()
        mock_store.async_save_snapshot.assert_not_called()


class TestGetTotalStats:
    """Tests for get_total_stats."""

    def test_total_stats(self, processor: DataProcessor) -> None:
        """Test aggregate stats computation."""
        totals = processor.get_total_stats()

        assert totals["total"] == 3
        assert totals["flashed"] == 1
        assert totals["unflashed"] == 1  # PA_002 (OK, not flashed)
        assert totals["gone"] == 1  # PA_003 (DESTROYED, not flashed)

    def test_total_stats_no_data(self, processor: DataProcessor, mock_spotter_coordinator) -> None:
        """Test aggregate stats with no data."""
        mock_spotter_coordinator.data = None
        totals = processor.get_total_stats()

        assert totals["total"] == 0
        assert totals["flashed"] == 0
        assert totals["unflashed"] == 0
        assert totals["gone"] == 0


class TestSetCityNames:
    """Tests for set_city_names."""

    def test_set_city_names(self, processor: DataProcessor) -> None:
        """Test updating city names."""
        processor.set_city_names({"PA": "Paris Updated", "LYN": "Lyon"})

        stats = processor.compute_city_stats("PA")
        assert stats.city.name == "Paris Updated"

    def test_missing_city_name_fallback(self, processor: DataProcessor) -> None:
        """Test fallback to city code when name not set."""
        processor.set_city_names({})

        stats = processor.compute_city_stats("PA")
        assert stats.city.name == "PA"


class TestAsyncInitialize:
    """Tests for async_initialize."""

    @pytest.mark.asyncio
    async def test_initialize_loads_snapshot(self, processor: DataProcessor, mock_store) -> None:
        """Test that initialize loads previous snapshot."""
        old_snapshot = StateSnapshot(
            timestamp=datetime(2024, 1, 1),
            invader_ids_by_city={"PA": {"PA_001"}},
            status_by_invader={"PA_001": InvaderStatus.OK},
        )
        mock_store.async_load_snapshot = AsyncMock(return_value=old_snapshot)

        await processor.async_initialize()

        assert processor._previous_snapshot == old_snapshot
        mock_store.async_load_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_no_previous_snapshot(self, processor: DataProcessor, mock_store) -> None:
        """Test initialize when no previous snapshot exists."""
        mock_store.async_load_snapshot = AsyncMock(return_value=None)

        await processor.async_initialize()

        assert processor._previous_snapshot is None
