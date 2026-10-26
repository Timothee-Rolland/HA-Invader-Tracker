"""Tests for Flash Invader API client."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.invader_tracker.api.flash_invader import FlashInvaderAPI
from custom_components.invader_tracker.exceptions import (
    AuthenticationError,
    FlashInvaderConnectionError,
    InvalidResponseError,
    ParseError,
    RateLimitError,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def api(mock_session) -> FlashInvaderAPI:
    """Create a FlashInvaderAPI with mock session."""
    return FlashInvaderAPI(mock_session, "test-uid-1234")


def _make_response(status: int = 200, json_data: dict | None = None, text: str = "") -> AsyncMock:
    """Create a mock aiohttp response."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = status
    response.json = AsyncMock(return_value=json_data or {})
    response.text = AsyncMock(return_value=text)
    response.headers = {}
    return response


class TestGetFlashedInvaders:
    """Tests for get_flashed_invaders."""

    @pytest.mark.asyncio
    async def test_successful_response(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test parsing a successful API response."""
        json_data = {
            "invaders": {
                "PA_001": {
                    "name": "PA_001",
                    "point": 10,
                    "city_id": 1,
                    "image_url": "https://example.com/pa001.jpg",
                    "date_pos": "2000-01-01",
                    "date_flash": "2024-01-15 10:30:00",
                },
                "LYN_042": {
                    "name": "LYN_042",
                    "point": 50,
                    "city_id": 2,
                    "image_url": "https://example.com/lyn042.jpg",
                    "date_pos": "2005-06-15",
                    "date_flash": "2024-06-20 18:00:00",
                },
            }
        }
        response = _make_response(200, json_data)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        invaders = await api.get_flashed_invaders()

        assert len(invaders) == 2
        assert invaders[0].id == "PA_001"
        assert invaders[0].points == 10
        assert invaders[0].install_date == date(2000, 1, 1)
        assert invaders[0].flash_date == datetime(2024, 1, 15, 10, 30, 0)
        assert invaders[1].id == "LYN_042"
        assert invaders[1].points == 50

    @pytest.mark.asyncio
    async def test_empty_invaders(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test response with empty invaders dict."""
        response = _make_response(200, {"invaders": {}})
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        invaders = await api.get_flashed_invaders()
        assert invaders == []

    @pytest.mark.asyncio
    async def test_missing_invaders_key(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test response missing 'invaders' key raises InvalidResponseError."""
        response = _make_response(200, {"data": []})
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(InvalidResponseError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_auth_error_401(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test 401 response raises AuthenticationError."""
        response = _make_response(401)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(AuthenticationError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_auth_error_403(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test 403 response raises AuthenticationError."""
        response = _make_response(403)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(AuthenticationError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_rate_limit_429(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test 429 response raises RateLimitError."""
        response = _make_response(429)
        response.headers = {"Retry-After": "60"}
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(RateLimitError) as exc_info:
            await api.get_flashed_invaders()
        assert exc_info.value.retry_after == 60

    @pytest.mark.asyncio
    async def test_bad_request_400(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test 400 response raises AuthenticationError."""
        response = _make_response(400, text="Bad Request")
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(AuthenticationError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_server_error_500(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test 500 response raises FlashInvaderConnectionError."""
        response = _make_response(500)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(FlashInvaderConnectionError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_invalid_json(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test invalid JSON response raises ParseError."""
        response = _make_response(200)
        response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        with pytest.raises(ParseError):
            await api.get_flashed_invaders()

    @pytest.mark.asyncio
    async def test_malformed_invader_skipped(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test that malformed invader entries are skipped."""
        json_data = {
            "invaders": {
                "PA_001": {
                    "name": "PA_001",
                    "point": 10,
                    "city_id": 1,
                    "image_url": "https://example.com/pa001.jpg",
                },
                "PA_BAD": {
                    "name": "PA_BAD",
                    "point": "not_a_number",  # int() will raise ValueError
                    "city_id": "bad",
                    "image_url": "",
                },
            }
        }
        response = _make_response(200, json_data)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        invaders = await api.get_flashed_invaders()
        # Only PA_001 should be parsed, PA_BAD should be skipped
        assert len(invaders) == 1
        assert invaders[0].id == "PA_001"

    @pytest.mark.asyncio
    async def test_missing_dates_parsed_as_none(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test that missing date fields result in None."""
        json_data = {
            "invaders": {
                "PA_001": {
                    "name": "PA_001",
                    "point": 10,
                    "city_id": 1,
                    "image_url": "https://example.com/pa001.jpg",
                    # No date_pos or date_flash
                },
            }
        }
        response = _make_response(200, json_data)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        invaders = await api.get_flashed_invaders()
        assert len(invaders) == 1
        assert invaders[0].install_date is None
        assert invaders[0].flash_date is None

    @pytest.mark.asyncio
    async def test_invalid_date_format_parsed_as_none(self, api: FlashInvaderAPI, mock_session) -> None:
        """Test that invalid date formats result in None."""
        json_data = {
            "invaders": {
                "PA_001": {
                    "name": "PA_001",
                    "point": 10,
                    "city_id": 1,
                    "image_url": "https://example.com/pa001.jpg",
                    "date_pos": "not-a-date",
                    "date_flash": "also-not-a-date",
                },
            }
        }
        response = _make_response(200, json_data)
        mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=response)))

        invaders = await api.get_flashed_invaders()
        assert len(invaders) == 1
        assert invaders[0].install_date is None
        assert invaders[0].flash_date is None
