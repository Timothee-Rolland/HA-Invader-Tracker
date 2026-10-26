"""Awazleon.space REST API client for invader data."""

from __future__ import annotations

import logging
from datetime import date, datetime

import aiohttp

from ..const import AWAZLEON_BASE_URL
from ..exceptions import InvaderSpotterConnectionError, ParseError
from ..models import City, Invader, InvaderStatus, normalize_invader_id

_LOGGER = logging.getLogger(__name__)

# Mapping from awazleon state codes to InvaderStatus
STATE_MAPPING: dict[str, InvaderStatus] = {
    "A": InvaderStatus.OK,  # Alive
    "DG": InvaderStatus.DAMAGED,  # Damaged (dégradé / très dégradé combined)
    "D": InvaderStatus.DESTROYED,  # Dead
    "DD": InvaderStatus.DESTROYED,  # Dead definitive
    "H": InvaderStatus.NOT_VISIBLE,  # Hidden
}


class AwazleonClient:
    """Client for the awazleon.space REST API."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str = "") -> None:
        """Initialize the client."""
        self._session = session
        self._headers = {"X-API-Key": api_key} if api_key else {}

    async def get_cities(self) -> list[City]:
        """Fetch the list of all cities from awazleon.

        Returns:
            List of City objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If response cannot be parsed

        """
        _LOGGER.debug("Fetching cities from awazleon.space")
        url = f"{AWAZLEON_BASE_URL}/cities/info"

        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    raise InvaderSpotterConnectionError(f"HTTP {response.status} fetching cities from awazleon")
                try:
                    data = await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise ParseError("Invalid JSON from awazleon /cities/info") from err

        except TimeoutError as err:
            raise InvaderSpotterConnectionError("Timeout fetching cities from awazleon") from err
        except aiohttp.ClientError as err:
            raise InvaderSpotterConnectionError(f"Connection error: {err}") from err

        cities_wrapper = data.get("cities", {})
        if not isinstance(cities_wrapper, dict):
            raise ParseError("Unexpected format from awazleon /cities/info")

        # Structure: {"cities": {"number": N, "details": {"PA": {...}, ...}}}
        cities_data = cities_wrapper.get("details", cities_wrapper)
        if not isinstance(cities_data, dict):
            raise ParseError("Unexpected 'cities' format from awazleon /cities/info")

        cities: list[City] = []
        for prefix, info in cities_data.items():
            if not isinstance(info, dict):
                continue
            cities.append(
                City(
                    code=prefix.upper(),
                    name=str(info.get("name", prefix)),
                    country=str(info.get("country", "")),
                )
            )

        _LOGGER.debug("Fetched %d cities from awazleon", len(cities))
        return cities

    async def get_city_invaders(self, city_code: str, city_name: str = "") -> list[Invader]:
        """Fetch all invaders for a city from awazleon.

        Args:
            city_code: City prefix (e.g. "PA", "LDN")
            city_name: City name for Invader objects

        Returns:
            List of Invader objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If response cannot be parsed

        """
        _LOGGER.debug("Fetching invaders for city %s from awazleon", city_code)
        url = f"{AWAZLEON_BASE_URL}/invaders/{city_code.lower()}/city"

        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 404:
                    _LOGGER.warning("City %s not found on awazleon", city_code)
                    return []
                if response.status != 200:
                    raise InvaderSpotterConnectionError(
                        f"HTTP {response.status} fetching city {city_code} from awazleon"
                    )
                try:
                    data = await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise ParseError(f"Invalid JSON from awazleon for city {city_code}") from err

        except TimeoutError as err:
            raise InvaderSpotterConnectionError(f"Timeout fetching city {city_code} from awazleon") from err
        except aiohttp.ClientError as err:
            raise InvaderSpotterConnectionError(f"Connection error: {err}") from err

        # Structure: {"provider": ..., "timestamp": ..., "city": ...,
        #             "invadersState": {...}, "invaders": {"PA_01": {...}, ...}}
        invaders_data: dict = {}
        if isinstance(data, dict):
            invaders_data = data.get("invaders", {})
            if not isinstance(invaders_data, dict):
                invaders_data = {}

        if not invaders_data:
            _LOGGER.warning("No invaders found for city %s on awazleon", city_code)
            return []

        invaders: list[Invader] = []
        for ref, info in invaders_data.items():
            invader = self._parse_invader(ref, info, city_code, city_name)
            if invader:
                invaders.append(invader)

        _LOGGER.debug(
            "Fetched %d invaders for %s (%d flashable)",
            len(invaders),
            city_code,
            sum(1 for inv in invaders if inv.is_flashable),
        )
        return invaders

    def _parse_invader(
        self,
        ref: str,
        data: dict,
        city_code: str,
        city_name: str,
    ) -> Invader | None:
        """Parse a single invader entry from awazleon response."""
        try:
            state_code = data.get("state", "")
            status = STATE_MAPPING.get(state_code, InvaderStatus.UNKNOWN)

            install_date: date | None = None
            inv_date_str = data.get("invdate", "")
            if inv_date_str:
                try:
                    install_date = datetime.strptime(inv_date_str, "%Y-%m-%d").date()
                except ValueError:
                    _LOGGER.debug("Could not parse invdate for %s: %s", ref, inv_date_str)

            return Invader(
                id=normalize_invader_id(ref),
                city_code=city_code.upper(),
                city_name=city_name or city_code,
                points=int(data.get("pts", 0)),
                status=status,
                install_date=install_date,
            )
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.debug("Failed to parse invader %s: %s", ref, err)
            return None
