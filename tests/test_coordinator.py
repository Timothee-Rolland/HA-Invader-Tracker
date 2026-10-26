"""Tests for data update coordinators."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.invader_tracker.coordinator import (
    FlashInvaderCoordinator,
    InvaderSpotterCoordinator,
)
from custom_components.invader_tracker.exceptions import (
    AuthenticationError,
    InvaderSpotterConnectionError,
    InvaderTrackerConnectionError,
    ParseError,
    RateLimitError,
)
from custom_components.invader_tracker.models import (
    FlashedInvader,
    Invader,
    InvaderStatus,
    NewsEvent,
    NewsEventType,
)


def _noop_coordinator_init(self, *args, **kwargs):
    """No-op init that sets minimal required attributes."""
    self.data = None
    self.last_update_success = True


@pytest.fixture(autouse=True)
def _patch_coordinator_init():
    """Patch DataUpdateCoordinator.__init__ to avoid HA frame helper requirement."""
    with patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__",
        _noop_coordinator_init,
    ):
        yield


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.loop = AsyncMock()
    return hass


@pytest.fixture
def mock_awazleon() -> MagicMock:
    """Create a mock AwazleonClient."""
    client = MagicMock()
    client.get_city_invaders = AsyncMock(
        return_value=[
            Invader(id="PA_001", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
        ]
    )
    return client


@pytest.fixture
def mock_scraper() -> MagicMock:
    """Create a mock InvaderSpotterScraper (news only)."""
    scraper = MagicMock()
    scraper.get_news = AsyncMock(return_value=[])
    return scraper


@pytest.fixture
def mock_flash_api() -> MagicMock:
    """Create a mock FlashInvaderAPI."""
    api = MagicMock()
    api.get_flashed_invaders = AsyncMock(
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
    return api


class TestInvaderSpotterCoordinator:
    """Tests for InvaderSpotterCoordinator."""

    def test_update_cities(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test updating tracked cities."""
        coordinator = InvaderSpotterCoordinator(
            mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris", "LYN": "Lyon"}, 60
        )

        # Add cache entry for Lyon
        coordinator._city_cache["LYN"] = (datetime.now(), [])

        # Remove Lyon, add MRS
        coordinator.update_cities({"PA": "Paris", "MRS": "Marseille"})

        assert coordinator.cities == {"PA": "Paris", "MRS": "Marseille"}
        # LYN cache should be cleaned up
        assert "LYN" not in coordinator._city_cache

    def test_is_cache_valid(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test cache validity check."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)

        # No cache
        assert coordinator._is_cache_valid("PA") is False

        # Fresh cache
        coordinator._city_cache["PA"] = (datetime.now(), [])
        assert coordinator._is_cache_valid("PA") is True

        # Expired cache (2 hours old, interval is 60 min)
        coordinator._city_cache["PA"] = (datetime.now() - timedelta(hours=2), [])
        assert coordinator._is_cache_valid("PA") is False

    @pytest.mark.asyncio
    async def test_async_update_data_fetches_uncached(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test that uncached cities are fetched from awazleon."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)

        with patch("custom_components.invader_tracker.coordinator.asyncio.sleep"):
            result = await coordinator._async_update_data()

        assert "PA" in result
        assert len(result["PA"]) == 1
        mock_awazleon.get_city_invaders.assert_called_once_with("PA", "Paris")

    @pytest.mark.asyncio
    async def test_async_update_data_uses_cache(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test that cached cities are not re-fetched."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)
        cached_invaders = [
            Invader(id="PA_CACHED", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
        ]
        coordinator._city_cache["PA"] = (datetime.now(), cached_invaders)

        result = await coordinator._async_update_data()

        assert result["PA"] == cached_invaders
        mock_awazleon.get_city_invaders.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_update_data_fallback_to_expired_cache(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test fallback to expired cache on fetch failure."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)
        cached_invaders = [
            Invader(id="PA_OLD", city_code="PA", city_name="Paris", points=10, status=InvaderStatus.OK),
        ]
        # Expired cache (2 hours old, interval is 60 min)
        coordinator._city_cache["PA"] = (datetime.now() - timedelta(hours=2), cached_invaders)

        mock_awazleon.get_city_invaders = AsyncMock(side_effect=InvaderSpotterConnectionError("Timeout"))

        with patch("custom_components.invader_tracker.coordinator.asyncio.sleep"):
            result = await coordinator._async_update_data()

        # Should use expired cache
        assert result["PA"] == cached_invaders

    @pytest.mark.asyncio
    async def test_async_update_data_all_fail_raises(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test that UpdateFailed is raised when all cities fail and no cache."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)
        mock_awazleon.get_city_invaders = AsyncMock(side_effect=InvaderSpotterConnectionError("Timeout"))

        with patch("custom_components.invader_tracker.coordinator.asyncio.sleep"), pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    def test_get_news_for_city(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test filtering news events by city."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)
        events = [
            NewsEvent(event_type=NewsEventType.ADDED, invader_id="PA_001", city_code="PA", event_date=date.today()),
            NewsEvent(event_type=NewsEventType.ADDED, invader_id="LYN_001", city_code="LYN", event_date=date.today()),
        ]
        result = coordinator.get_news_for_city("PA", events)

        assert len(result) == 1
        assert result[0].invader_id == "PA_001"

    @pytest.mark.asyncio
    async def test_get_news_events_caching(self, mock_hass, mock_awazleon, mock_scraper) -> None:
        """Test that news events are cached."""
        coordinator = InvaderSpotterCoordinator(mock_hass, mock_awazleon, mock_scraper, {"PA": "Paris"}, 60)
        mock_scraper.get_news = AsyncMock(
            return_value=[
                NewsEvent(event_type=NewsEventType.ADDED, invader_id="PA_001", city_code="PA", event_date=date.today()),
            ]
        )

        # First call fetches from scraper
        events1 = await coordinator.get_news_events(days=30)
        assert len(events1) == 1
        assert mock_scraper.get_news.call_count == 1

        # Second call uses cache
        events2 = await coordinator.get_news_events(days=30)
        assert len(events2) == 1
        assert mock_scraper.get_news.call_count == 1  # Not called again


class TestFlashInvaderCoordinator:
    """Tests for FlashInvaderCoordinator."""

    def test_get_flashed_for_city(self, mock_hass, mock_flash_api) -> None:
        """Test getting flashed invaders by city."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)

        # Simulate data loaded
        invaders = [
            FlashedInvader(
                id="PA_001", name="PA_001", city_id=1, points=10, image_url="", install_date=None, flash_date=None
            ),
            FlashedInvader(
                id="LYN_001", name="LYN_001", city_id=2, points=20, image_url="", install_date=None, flash_date=None
            ),
        ]
        coordinator._update_city_grouping(invaders)

        pa_invaders = coordinator.get_flashed_for_city("PA")
        assert len(pa_invaders) == 1
        assert pa_invaders[0].id == "PA_001"

        lyn_invaders = coordinator.get_flashed_for_city("LYN")
        assert len(lyn_invaders) == 1
        assert lyn_invaders[0].id == "LYN_001"

        # Unknown city
        unknown = coordinator.get_flashed_for_city("MRS")
        assert unknown == []

    def test_update_city_grouping(self, mock_hass, mock_flash_api) -> None:
        """Test city grouping logic."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)

        invaders = [
            FlashedInvader(
                id="PA_001", name="PA_001", city_id=1, points=10, image_url="", install_date=None, flash_date=None
            ),
            FlashedInvader(
                id="PA_002", name="PA_002", city_id=1, points=20, image_url="", install_date=None, flash_date=None
            ),
            FlashedInvader(
                id="LYN_001", name="LYN_001", city_id=2, points=30, image_url="", install_date=None, flash_date=None
            ),
        ]
        coordinator._update_city_grouping(invaders)

        assert len(coordinator._flashed_by_city["PA"]) == 2
        assert len(coordinator._flashed_by_city["LYN"]) == 1

    @pytest.mark.asyncio
    async def test_async_update_data_success(self, mock_hass, mock_flash_api) -> None:
        """Test successful data fetch."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)

        result = await coordinator._async_update_data()

        assert len(result) == 1
        assert result[0].id == "PA_001"
        mock_flash_api.get_flashed_invaders.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_update_data_auth_error(self, mock_hass, mock_flash_api) -> None:
        """Test that auth errors trigger ConfigEntryAuthFailed."""
        from homeassistant.exceptions import ConfigEntryAuthFailed

        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)
        mock_flash_api.get_flashed_invaders = AsyncMock(side_effect=AuthenticationError("Invalid UID"))

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_rate_limit(self, mock_hass, mock_flash_api) -> None:
        """Test that rate limit errors raise UpdateFailed."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)
        mock_flash_api.get_flashed_invaders = AsyncMock(side_effect=RateLimitError(60))

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_connection_error(self, mock_hass, mock_flash_api) -> None:
        """Test that connection errors raise UpdateFailed."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)
        mock_flash_api.get_flashed_invaders = AsyncMock(side_effect=InvaderTrackerConnectionError("Timeout"))

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    @pytest.mark.asyncio
    async def test_async_update_data_parse_error(self, mock_hass, mock_flash_api) -> None:
        """Test that parse errors raise UpdateFailed."""
        coordinator = FlashInvaderCoordinator(mock_hass, mock_flash_api, 60)
        mock_flash_api.get_flashed_invaders = AsyncMock(side_effect=ParseError("Bad response"))

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
