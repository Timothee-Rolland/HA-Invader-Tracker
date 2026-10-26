"""Flash Invader API client."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime

import aiohttp

from ..const import (
    FLASH_INVADER_ACCOUNT_ENDPOINT,
    FLASH_INVADER_BASE_URL,
    FLASH_INVADER_ENDPOINT,
    FLASH_INVADER_HIGHSCORE_ENDPOINT,
)
from ..exceptions import (
    AuthenticationError,
    FlashInvaderConnectionError,
    InvalidResponseError,
    ParseError,
    RateLimitError,
)
from ..models import FlashedInvader, FollowedPlayer, PlayerProfile

_LOGGER = logging.getLogger(__name__)


class FlashInvaderAPI:
    """Client for Flash Invader API."""

    def __init__(self, session: aiohttp.ClientSession, uid: str) -> None:
        """Initialize the API client.

        Args:
            session: aiohttp client session
            uid: User's Flash Invader UID

        """
        self._session = session
        self._uid = uid
        self._total_si_count: int = 0
        # city_id (int) -> si_count, populated after get_flashed_invaders
        self._si_count_by_city_id: dict[int, int] = {}
        # city_id (int) -> city_code (str), derived from flashed invaders IDs
        self._city_code_by_id: dict[int, str] = {}

    @property
    def total_si_count(self) -> int:
        """Return the total worldwide invader count (populated after get_flashed_invaders)."""
        return self._total_si_count

    def get_city_si_count(self, city_code: str) -> int | None:
        """Return total SI count for a city code, or None if unknown."""
        for city_id, code in self._city_code_by_id.items():
            if code == city_code.upper():
                return self._si_count_by_city_id.get(city_id)
        return None

    @property
    def _headers(self) -> dict[str, str]:
        """Build request headers."""
        return {
            "Accept": "*/*",
            "Origin": "https://pnote.eu",
            "Referer": "https://pnote.eu/",
        }

    async def get_flashed_invaders(self) -> list[FlashedInvader]:
        """Fetch all invaders flashed by user.

        Returns:
            List of FlashedInvader objects

        Raises:
            AuthenticationError: If UID is invalid
            FlashInvaderConnectionError: If connection fails
            ParseError: If response cannot be parsed
            RateLimitError: If rate limited

        """
        _LOGGER.debug("Fetching flashed invaders from Flash Invader API")

        try:
            async with self._session.get(
                f"{FLASH_INVADER_BASE_URL}{FLASH_INVADER_ENDPOINT}",
                params={"uid": self._uid},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                return await self._handle_response(response)

        except TimeoutError as err:
            _LOGGER.warning("Flash Invader API timeout")
            raise FlashInvaderConnectionError("Request timed out") from err

        except aiohttp.ClientError as err:
            _LOGGER.warning("Flash Invader API connection error: %s", type(err).__name__)
            raise FlashInvaderConnectionError(f"Connection failed: {err}") from err

    async def _handle_response(self, response: aiohttp.ClientResponse) -> list[FlashedInvader]:
        """Handle API response with status-specific error handling."""
        if response.status == 200:
            return await self._parse_response(response)

        if response.status == 401:
            _LOGGER.error("Flash Invader API: Invalid UID")
            raise AuthenticationError("Invalid UID")

        if response.status == 403:
            _LOGGER.error("Flash Invader API: Access forbidden")
            raise AuthenticationError("Access forbidden - UID may be blocked")

        if response.status == 429:
            retry_after = response.headers.get("Retry-After")
            _LOGGER.warning("Flash Invader API: Rate limited")
            raise RateLimitError(int(retry_after) if retry_after else None)

        if response.status == 400:
            body = await response.text()
            _LOGGER.error("Flash Invader API: Bad request (400) - UID format may be invalid. Response: %s", body[:200])
            raise AuthenticationError("Invalid UID format - check that your UID is correct")

        if response.status >= 500:
            _LOGGER.warning("Flash Invader API: Server error %d", response.status)
            raise FlashInvaderConnectionError(f"Server error: {response.status}")

        body = await response.text()
        _LOGGER.error("Flash Invader API: Unexpected status %d. Response: %s", response.status, body[:200])
        raise InvalidResponseError(f"Unexpected status: {response.status}")

    async def _parse_response(self, response: aiohttp.ClientResponse) -> list[FlashedInvader]:
        """Parse JSON response."""
        try:
            data = await response.json()
        except (ValueError, aiohttp.ContentTypeError) as err:
            _LOGGER.error("Flash Invader API: Invalid JSON response")
            raise ParseError("Invalid JSON response") from err

        if "invaders" not in data:
            _LOGGER.error("Flash Invader API: Missing 'invaders' key")
            raise InvalidResponseError("Response missing 'invaders' key")

        # Cache global stats for use by get_player_profile
        self._total_si_count = int(data.get("total_si_count", 0))

        # Parse per-city si_count from the cities list
        self._si_count_by_city_id = {
            int(c["id"]): int(c.get("si_count", 0)) for c in data.get("cities", []) if isinstance(c, dict) and "id" in c
        }

        invaders: list[FlashedInvader] = []
        for inv_id, inv_data in data["invaders"].items():
            try:
                invader = self._parse_invader(inv_id, inv_data)
                invaders.append(invader)
            except (KeyError, TypeError, ValueError) as err:
                _LOGGER.warning("Failed to parse invader %s: %s", inv_id, err)

        # Build city_id -> city_code mapping from flashed invaders IDs (e.g. "PA_593" + city_id=1 -> 1:"PA")
        for inv in invaders:
            if inv.city_id not in self._city_code_by_id:
                parts = inv.id.rsplit("_", 1)
                if len(parts) == 2:
                    self._city_code_by_id[inv.city_id] = parts[0].upper()

        _LOGGER.debug("Parsed %d flashed invaders (total worldwide: %d)", len(invaders), self._total_si_count)
        return invaders

    async def get_player_profile(self) -> PlayerProfile:
        """Fetch the authenticated user's profile.

        Returns:
            PlayerProfile object

        Raises:
            AuthenticationError: If UID is invalid
            FlashInvaderConnectionError: If connection fails
            ParseError: If response cannot be parsed

        """
        _LOGGER.debug("Fetching player profile from Flash Invader API")

        try:
            async with self._session.get(
                f"{FLASH_INVADER_BASE_URL}{FLASH_INVADER_ACCOUNT_ENDPOINT}",
                params={"uid": self._uid},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid UID")
                if response.status != 200:
                    raise FlashInvaderConnectionError(f"Server error: {response.status}")
                try:
                    data = await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise ParseError("Invalid JSON response") from err

                return PlayerProfile(
                    name=data.get("name", ""),
                    score=int(data.get("score", 0)),
                    rank=int(data.get("rank", 0)),
                    rank_str=data.get("rank_str", ""),
                    si_found=int(data.get("si_found", 0)),
                    city_found=int(data.get("city_found", 0)),
                    registration_date=data.get("registration_date", ""),
                )

        except TimeoutError as err:
            raise FlashInvaderConnectionError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise FlashInvaderConnectionError(f"Connection failed: {err}") from err

    async def get_followed_players(self) -> list[FollowedPlayer]:
        """Fetch the list of players followed by the authenticated user.

        Returns:
            List of FollowedPlayer objects (excluding current_player entry)

        Raises:
            AuthenticationError: If UID is invalid
            FlashInvaderConnectionError: If connection fails
            ParseError: If response cannot be parsed

        """
        _LOGGER.debug("Fetching followed players from Flash Invader highscore")

        try:
            async with self._session.get(
                f"{FLASH_INVADER_BASE_URL}{FLASH_INVADER_HIGHSCORE_ENDPOINT}",
                params={"uid": self._uid},
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise AuthenticationError("Invalid UID")
                if response.status != 200:
                    raise FlashInvaderConnectionError(f"Server error: {response.status}")

                html_content = await response.text()

        except TimeoutError as err:
            raise FlashInvaderConnectionError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise FlashInvaderConnectionError(f"Connection failed: {err}") from err

        return self._parse_followed_players(html_content)

    def _parse_followed_players(self, html_content: str) -> list[FollowedPlayer]:
        """Extract followed_players from the JSON embedded in the highscore page."""
        match = re.search(r"fillTalbleWithData\(JSON\.parse\('(.+?)'\)\)", html_content, re.DOTALL)
        if not match:
            raise ParseError("Could not find player data in highscore page")

        try:
            raw = match.group(1)
            # Unescape unicode sequences like \u0022 -> "
            raw = raw.encode().decode("unicode_escape")
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as err:
            raise ParseError(f"Failed to parse highscore JSON: {err}") from err

        players = []
        for p in data.get("followed_players", []):
            if p.get("player_status") == "current_player":
                continue
            players.append(
                FollowedPlayer(
                    name=p["name"],
                    score=int(p.get("score", 0)),
                    rank=int(p.get("rank", 0)),
                    rank_str=p.get("rank_str", ""),
                    invaders_count=int(p.get("invaders_count", 0)),
                )
            )

        _LOGGER.debug("Parsed %d followed players", len(players))
        return players

    def _parse_invader(self, inv_id: str, data: dict) -> FlashedInvader:
        """Parse a single invader from API response."""
        # Parse install date (None if invalid)
        install_date: date | None = None
        install_date_str = data.get("date_pos", "")
        if install_date_str:
            try:
                install_date = datetime.strptime(install_date_str, "%Y-%m-%d").date()
            except ValueError:
                _LOGGER.debug("Could not parse install_date for %s: %s", inv_id, install_date_str)

        # Parse flash date (None if invalid)
        flash_date: datetime | None = None
        flash_date_str = data.get("date_flash", "")
        if flash_date_str:
            try:
                flash_date = datetime.strptime(flash_date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                _LOGGER.debug("Could not parse flash_date for %s: %s", inv_id, flash_date_str)

        return FlashedInvader(
            id=inv_id,
            name=data.get("name", inv_id),
            city_id=int(data.get("city_id", 0)),
            points=int(data.get("point", 0)),
            image_url=data.get("image_url", ""),
            install_date=install_date,
            flash_date=flash_date,
        )
