"""Tests for the Awazleon REST API client."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.invader_tracker.api.awazleon import STATE_MAPPING, AwazleonClient
from custom_components.invader_tracker.exceptions import InvaderSpotterConnectionError
from custom_components.invader_tracker.models import InvaderStatus


@pytest.fixture
def session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock()


@pytest.fixture
def client(session: MagicMock) -> AwazleonClient:
    """Create an AwazleonClient with a mock session."""
    return AwazleonClient(session)


CITIES_RESPONSE = {
    "provider": "awazleon.space",
    "timestamp": "2026-04-15",
    "cities": {
        "number": 2,
        "details": {
            "PA": {"prefix": "PA", "name": "Paris", "country": "France", "iso": "fr", "invaders": 1568, "pts": 43510},
            "LDN": {"prefix": "LDN", "name": "London", "country": "UK", "iso": "gb", "invaders": 84, "pts": 2040},
        },
    },
}

CITY_INVADERS_RESPONSE = {
    "provider": "awazleon.space",
    "timestamp": "2026-04-15",
    "city": "pa",
    "invadersState": {"alive": 2, "dead": 3, "hidden": 1},
    "invaders": {
        "PA_01": {"pts": 10, "state": "A", "invdate": "2000-01-15", "CP": "75004"},
        "PA_02": {"pts": 20, "state": "DG", "invdate": "2001-06-01", "CP": "75001"},
        "PA_03": {"pts": 30, "state": "D", "invdate": "1999-11-20", "CP": "75003"},
        "PA_04": {"pts": 10, "state": "H", "invdate": "2005-03-10", "CP": "75002"},
        "PA_05": {"pts": 50, "state": "DD", "invdate": "2002-08-22", "CP": "75005"},
        "PA_06": {"pts": 20, "state": "UNKNOWN_CODE", "invdate": "2003-12-01", "CP": "75006"},
    },
}


def _make_response(json_data, status: int = 200) -> MagicMock:
    """Build a mock aiohttp response."""
    resp = MagicMock()
    resp.status = status
    resp.json = AsyncMock(return_value=json_data)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


class TestStateMapping:
    """Test awazleon state code to InvaderStatus mapping."""

    def test_alive_maps_to_ok(self) -> None:
        assert STATE_MAPPING["A"] == InvaderStatus.OK

    def test_damaged_maps_correctly(self) -> None:
        assert STATE_MAPPING["DG"] == InvaderStatus.DAMAGED

    def test_dead_maps_to_destroyed(self) -> None:
        assert STATE_MAPPING["D"] == InvaderStatus.DESTROYED
        assert STATE_MAPPING["DD"] == InvaderStatus.DESTROYED

    def test_hidden_maps_to_not_visible(self) -> None:
        assert STATE_MAPPING["H"] == InvaderStatus.NOT_VISIBLE


class TestGetCities:
    """Tests for AwazleonClient.get_cities."""

    @pytest.mark.asyncio
    async def test_returns_city_list(self, client: AwazleonClient) -> None:
        """Test that cities are parsed correctly."""
        resp = _make_response(CITIES_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        cities = await client.get_cities()

        assert len(cities) == 2
        codes = {c.code for c in cities}
        assert "PA" in codes
        assert "LDN" in codes

    @pytest.mark.asyncio
    async def test_city_fields(self, client: AwazleonClient) -> None:
        """Test that city fields are populated."""
        resp = _make_response(CITIES_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        cities = await client.get_cities()
        paris = next(c for c in cities if c.code == "PA")

        assert paris.name == "Paris"
        assert paris.country == "France"

    @pytest.mark.asyncio
    async def test_http_error_raises(self, client: AwazleonClient) -> None:
        """Test that non-200 status raises InvaderSpotterConnectionError."""
        resp = _make_response({}, status=500)
        client._session.get = MagicMock(return_value=resp)

        with pytest.raises(InvaderSpotterConnectionError):
            await client.get_cities()


class TestGetCityInvaders:
    """Tests for AwazleonClient.get_city_invaders."""

    @pytest.mark.asyncio
    async def test_returns_invaders(self, client: AwazleonClient) -> None:
        """Test that all invaders are returned."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")

        assert len(invaders) == 6

    @pytest.mark.asyncio
    async def test_status_mapping(self, client: AwazleonClient) -> None:
        """Test that state codes are correctly mapped to InvaderStatus."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")
        by_id = {inv.id: inv for inv in invaders}

        # IDs are normalized: PA_01 → PA_1
        assert by_id["PA_1"].status == InvaderStatus.OK
        assert by_id["PA_2"].status == InvaderStatus.DAMAGED
        assert by_id["PA_3"].status == InvaderStatus.DESTROYED
        assert by_id["PA_4"].status == InvaderStatus.NOT_VISIBLE
        assert by_id["PA_5"].status == InvaderStatus.DESTROYED
        assert by_id["PA_6"].status == InvaderStatus.UNKNOWN  # unknown code fallback

    @pytest.mark.asyncio
    async def test_install_date_parsed(self, client: AwazleonClient) -> None:
        """Test that invdate is parsed to a date object."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")
        pa001 = next(inv for inv in invaders if inv.id == "PA_1")

        assert pa001.install_date == date(2000, 1, 15)

    @pytest.mark.asyncio
    async def test_points_parsed(self, client: AwazleonClient) -> None:
        """Test that pts is correctly parsed."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")
        pa001 = next(inv for inv in invaders if inv.id == "PA_1")

        assert pa001.points == 10

    @pytest.mark.asyncio
    async def test_flashable_statuses(self, client: AwazleonClient) -> None:
        """Test that only A and DG invaders are flashable."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")
        flashable = [inv for inv in invaders if inv.is_flashable]

        # PA_1 (A) and PA_2 (DG) are flashable
        assert len(flashable) == 2
        flashable_ids = {inv.id for inv in flashable}
        assert "PA_1" in flashable_ids
        assert "PA_2" in flashable_ids

    @pytest.mark.asyncio
    async def test_404_returns_empty(self, client: AwazleonClient) -> None:
        """Test that 404 returns empty list (city not in awazleon)."""
        resp = _make_response({}, status=404)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("UNKNOWN", "Unknown City")

        assert invaders == []

    @pytest.mark.asyncio
    async def test_http_error_raises(self, client: AwazleonClient) -> None:
        """Test that server errors raise InvaderSpotterConnectionError."""
        resp = _make_response({}, status=500)
        client._session.get = MagicMock(return_value=resp)

        with pytest.raises(InvaderSpotterConnectionError):
            await client.get_city_invaders("PA", "Paris")

    @pytest.mark.asyncio
    async def test_city_name_on_invaders(self, client: AwazleonClient) -> None:
        """Test that city_name is set on all returned invaders."""
        resp = _make_response(CITY_INVADERS_RESPONSE)
        client._session.get = MagicMock(return_value=resp)

        invaders = await client.get_city_invaders("PA", "Paris")

        assert all(inv.city_name == "Paris" for inv in invaders)
        assert all(inv.city_code == "PA" for inv in invaders)
