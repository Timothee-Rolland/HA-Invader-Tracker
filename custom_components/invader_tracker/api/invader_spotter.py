"""Invader Spotter scraper."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import date, datetime, timedelta

import aiohttp
from bs4 import BeautifulSoup

from ..const import INVADER_SPOTTER_BASE_URL, SCRAPE_MAX_RETRIES, SCRAPE_RETRY_BACKOFF
from ..exceptions import InvaderSpotterConnectionError, ParseError
from ..models import City, Invader, InvaderStatus, NewsEvent, NewsEventType

_LOGGER = logging.getLogger(__name__)

# Regex patterns
INVADER_ID_PATTERN = re.compile(r"^[A-Z]{2,5}_\d{1,4}$")
POINTS_PATTERN = re.compile(r"\[(\d+)\s*pts?\]", re.IGNORECASE)
DATE_PATTERN_FR = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

# Pattern to extract invader IDs from news links: javascript:lienm("PA12",1554)
NEWS_INVADER_PATTERN = re.compile(r'javascript:lienm\("([A-Z]+)\d*",(\d+)\)')
# Pattern for month headers: "janvier 2026"
MONTH_PATTERN = re.compile(
    r"(janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(\d{4})",
    re.IGNORECASE,
)
# Month name to number mapping
MONTH_NAMES = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}

# News event type keywords (French)
NEWS_EVENT_KEYWORDS = {
    "ajout": NewsEventType.ADDED,
    "réactivation": NewsEventType.REACTIVATED,
    "restauration": NewsEventType.RESTORED,
    "dégradation": NewsEventType.DEGRADED,
    "destruction": NewsEventType.DESTROYED,
    "mise à jour": NewsEventType.STATUS_UPDATE,
    "alerte": NewsEventType.ALERT,
}

# Status mappings (French to enum) - based on invader-spotter.art values
# Flashable: OK, Dégradé, Très dégradé
# NOT flashable: Détruit, Non visible, Inconnu
STATUS_MAPPING: dict[str, InvaderStatus] = {
    # OK status
    "ok": InvaderStatus.OK,
    "intact": InvaderStatus.OK,
    # Damaged (flashable)
    "dégradé": InvaderStatus.DAMAGED,
    "un peu dégradé": InvaderStatus.DAMAGED,
    # Very damaged (flashable)
    "très dégradé": InvaderStatus.VERY_DAMAGED,
    # Destroyed (NOT flashable)
    "détruit": InvaderStatus.DESTROYED,
    "détruit !": InvaderStatus.DESTROYED,
    "disparu": InvaderStatus.DESTROYED,
    # Not visible (NOT flashable)
    "non visible": InvaderStatus.NOT_VISIBLE,
    # Unknown (NOT flashable)
    "inconnu": InvaderStatus.UNKNOWN,
}


class InvaderSpotterScraper:
    """Scraper for invader-spotter.art."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the scraper.

        Args:
            session: aiohttp client session

        """
        self._session = session

    async def get_cities(self) -> list[City]:
        """Scrape list of all cities.

        Returns:
            List of City objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If page cannot be parsed

        """
        _LOGGER.debug("Fetching cities from invader-spotter.art")
        url = f"{INVADER_SPOTTER_BASE_URL}/villes.php"

        last_err: InvaderSpotterConnectionError | None = None
        for attempt in range(1, SCRAPE_MAX_RETRIES + 1):
            try:
                async with self._session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        raise InvaderSpotterConnectionError(f"HTTP {response.status} fetching cities")

                    html_content = await response.text()
                    return self._parse_cities_page(html_content)

            except TimeoutError:
                last_err = InvaderSpotterConnectionError("Timeout fetching cities")
                _LOGGER.warning(
                    "Invader Spotter timeout fetching cities (attempt %d/%d)",
                    attempt,
                    SCRAPE_MAX_RETRIES,
                )

            except aiohttp.ClientError as err:
                last_err = InvaderSpotterConnectionError(str(err))
                _LOGGER.warning(
                    "Invader Spotter connection error fetching cities (attempt %d/%d): %s",
                    attempt,
                    SCRAPE_MAX_RETRIES,
                    type(err).__name__,
                )

            if attempt < SCRAPE_MAX_RETRIES:
                try:
                    await asyncio.sleep(SCRAPE_RETRY_BACKOFF * attempt)
                except asyncio.CancelledError:
                    raise

        raise last_err or InvaderSpotterConnectionError("Failed to fetch cities")

    def _parse_cities_page(self, html_content: str) -> list[City]:
        """Parse cities list page."""
        soup = BeautifulSoup(html_content, "html.parser")
        cities: list[City] = []
        seen_codes: set[str] = set()

        # Look for city links - they use javascript:envoi("CODE") format
        for link in soup.find_all("a", href=True):
            href = str(link.get("href", ""))

            # Match javascript:envoi("CODE") pattern
            match = re.search(r"javascript:envoi\(['\"]([A-Z0-9_]+)['\"]\)", href, re.IGNORECASE)
            if match:
                city_code = match.group(1).upper()

                # Skip if already seen (avoid duplicates from map and list)
                if city_code in seen_codes:
                    continue
                seen_codes.add(city_code)

                city_name = link.get_text(strip=True) or city_code

                # Clean up city name
                city_name = html.unescape(city_name)

                cities.append(
                    City(
                        code=city_code,
                        name=city_name,
                    )
                )

        _LOGGER.debug("Found %d cities", len(cities))
        return cities

    async def get_city_invaders(self, city_code: str, city_name: str = "") -> list[Invader]:
        """Scrape all invaders for a city (handles pagination).

        Args:
            city_code: City code (e.g., "PA", "LYN")
            city_name: City name (optional, for Invader objects)

        Returns:
            List of Invader objects

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If page cannot be parsed

        """
        _LOGGER.debug("Fetching invaders for city %s", city_code)

        all_invaders: list[Invader] = []
        page = 1
        max_pages = 100  # Safety limit

        while page <= max_pages:
            invaders, has_more = await self._fetch_city_page(city_code, city_name, page)
            all_invaders.extend(invaders)

            if not has_more or not invaders:
                break

            page += 1
            # Small delay between pages to be respectful
            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                raise

        _LOGGER.debug("Fetched total %d invaders for %s across %d pages", len(all_invaders), city_code, page)
        return all_invaders

    async def _fetch_city_page(self, city_code: str, city_name: str, page: int) -> tuple[list[Invader], bool]:
        """Fetch a single page of invaders for a city, with retries.

        Returns:
            Tuple of (invaders list, has_more_pages)
        """
        url = f"{INVADER_SPOTTER_BASE_URL}/listing.php"

        data = {
            "ville": city_code,
            "arron": "00",
            "mode": "lst",
            "page": str(page),
        }
        headers = {
            "Referer": f"{INVADER_SPOTTER_BASE_URL}/villes.php",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        last_err: InvaderSpotterConnectionError | None = None
        for attempt in range(1, SCRAPE_MAX_RETRIES + 1):
            try:
                async with self._session.post(
                    url,
                    data=data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status != 200:
                        raise InvaderSpotterConnectionError(f"HTTP {response.status} for city {city_code} page {page}")

                    html_content = await response.text()
                    invaders = self._parse_city_page(html_content, city_code, city_name)
                    has_more = self._has_next_page(html_content, page)
                    return invaders, has_more

            except TimeoutError:
                last_err = InvaderSpotterConnectionError(f"Timeout for {city_code}")
                _LOGGER.warning(
                    "Invader Spotter timeout for city %s page %d (attempt %d/%d)",
                    city_code,
                    page,
                    attempt,
                    SCRAPE_MAX_RETRIES,
                )

            except aiohttp.ClientError as err:
                last_err = InvaderSpotterConnectionError(str(err))
                _LOGGER.warning(
                    "Invader Spotter connection error for %s page %d (attempt %d/%d): %s",
                    city_code,
                    page,
                    attempt,
                    SCRAPE_MAX_RETRIES,
                    type(err).__name__,
                )

            if attempt < SCRAPE_MAX_RETRIES:
                try:
                    await asyncio.sleep(SCRAPE_RETRY_BACKOFF * attempt)
                except asyncio.CancelledError:
                    raise

        raise last_err or InvaderSpotterConnectionError(f"Failed to fetch city {city_code}")

    def _has_next_page(self, html_content: str, current_page: int) -> bool:
        """Check if there's a next page of results."""
        # Look for pagination links like changepage(N) where N > current_page
        pattern = rf"changepage\({current_page + 1}\)"
        return bool(re.search(pattern, html_content))

    def _parse_city_page(self, html_content: str, city_code: str, city_name: str) -> list[Invader]:
        """Parse city invaders page."""
        soup = BeautifulSoup(html_content, "html.parser")
        invaders: list[Invader] = []
        parse_errors = 0

        # Try multiple selectors for invader entries
        # The actual structure may vary - we try common patterns
        entries = self._find_invader_entries(soup)

        if not entries:
            _LOGGER.warning(
                "No invader entries found for %s - page structure may have changed",
                city_code,
            )
            return []

        for entry in entries:
            try:
                invader = self._parse_invader_entry(entry, city_code, city_name)
                if invader:
                    invaders.append(invader)
            except Exception as err:  # noqa: BLE001
                parse_errors += 1
                _LOGGER.debug("Failed to parse entry in %s: %s", city_code, err)

        if parse_errors > 0:
            _LOGGER.warning(
                "Failed to parse %d/%d entries for %s",
                parse_errors,
                len(entries),
                city_code,
            )

        if not invaders and entries:
            raise ParseError(
                f"Found {len(entries)} entries for {city_code} but parsed 0 - HTML structure may have changed"
            )

        _LOGGER.debug(
            "Parsed %d invaders for %s (%d flashable)",
            len(invaders),
            city_code,
            sum(1 for inv in invaders if inv.is_flashable),
        )
        return invaders

    def _find_invader_entries(self, soup: BeautifulSoup) -> list:
        """Find invader entry elements - each invader is in a <td> with rowspan."""
        entries = []

        # The site structure: each invader is in a <td align="left" rowspan="2">
        # containing <b>XX_NN [pts]</b> and other info
        for td in soup.find_all("td", {"rowspan": "2"}):
            # Check if this td contains an invader ID pattern
            text = td.get_text()
            if re.search(r"[A-Z]{2,5}_\d{1,4}", text):
                entries.append(td)

        if entries:
            return entries

        # Fallback: Look for <b> tags with invader IDs
        for bold in soup.find_all("b"):
            text = bold.get_text()
            if re.search(r"[A-Z]{2,5}_\d{1,4}\s*\[\d+\s*pts?\]", text, re.IGNORECASE):
                # Get the parent td
                parent = bold.find_parent("td")
                if parent and parent not in entries:
                    entries.append(parent)

        return entries

    def _parse_invader_entry(self, entry, city_code: str, city_name: str) -> Invader | None:
        """Parse a single invader entry."""
        text = entry.get_text(" ", strip=True)
        html_str = str(entry)

        # Extract invader ID
        inv_id = self._extract_invader_id(text, city_code)
        if not inv_id:
            return None

        # Extract points
        points = self._extract_points(text)

        # Extract status from images or text
        status = self._extract_status_from_html(html_str, text)

        # Extract install date
        install_date = self._extract_date(text)

        return Invader(
            id=inv_id,
            city_code=city_code,
            city_name=city_name or city_code,
            points=points,
            status=status,
            install_date=install_date,
        )

    def _extract_invader_id(self, text: str, city_code: str) -> str | None:
        """Extract and validate invader ID from text."""
        # Look for pattern like PA_001, LYN_42, etc.
        pattern = rf"({city_code}_\d{{1,4}})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            inv_id = match.group(1).upper()
            if INVADER_ID_PATTERN.match(inv_id):
                return inv_id

        # Fallback: any invader ID pattern
        match = re.search(r"([A-Z]{2,5}_\d{1,4})", text)
        if match:
            inv_id = match.group(1).upper()
            if INVADER_ID_PATTERN.match(inv_id):
                return inv_id

        return None

    def _extract_points(self, text: str) -> int:
        """Extract points value from text."""
        match = POINTS_PATTERN.search(text)
        if match:
            try:
                points = int(match.group(1))
                # Sanity check - points are typically 10-100
                if 0 < points <= 1000:
                    return points
            except ValueError:
                pass
        return 0

    def _extract_status_from_html(self, html_str: str, text: str) -> InvaderStatus:
        """Extract status from HTML (checking images) or text."""
        html_lower = html_str.lower()
        text_lower = text.lower()

        # Check for status images first (more reliable)
        if "spot_invader_destroyed" in html_lower:
            return InvaderStatus.DESTROYED
        if "spot_invader_degraded" in html_lower:
            # Need to distinguish between "dégradé" and "très dégradé"
            if "très dégradé" in text_lower:
                return InvaderStatus.VERY_DAMAGED
            return InvaderStatus.DAMAGED
        if "spot_invader_ok" in html_lower:
            return InvaderStatus.OK
        if "spot_invader_unknown" in html_lower:
            return InvaderStatus.UNKNOWN
        if "spot_invader_notvisible" in html_lower or "non visible" in text_lower:
            return InvaderStatus.NOT_VISIBLE

        # Fallback to text-based extraction
        return self._extract_status(text)

    def _extract_status(self, text: str) -> InvaderStatus:
        """Extract status from text."""
        text_lower = text.lower()

        # Look for status keywords
        for keyword, status in STATUS_MAPPING.items():
            if keyword in text_lower:
                return status

        # Check for specific patterns
        if "dernier état" in text_lower or "état connu" in text_lower:
            # Try to find status after these phrases
            for keyword, status in STATUS_MAPPING.items():
                pattern = rf"(?:dernier état|état connu)[^:]*:\s*{keyword}"
                if re.search(pattern, text_lower):
                    return status

        return InvaderStatus.UNKNOWN

    def _extract_date(self, text: str) -> date | None:
        """Extract date from text (French format DD/MM/YYYY)."""
        match = DATE_PATTERN_FR.search(text)
        if match:
            try:
                day = int(match.group(1))
                month = int(match.group(2))
                year = int(match.group(3))
                return datetime(year, month, day).date()
            except ValueError:
                pass
        return None

    async def get_news(
        self,
        days: int = 30,
        city_codes: set[str] | None = None,
    ) -> list[NewsEvent]:
        """Scrape news from invader-spotter.art/news.php.

        Args:
            days: Number of days of news to fetch (default 30)
            city_codes: Optional set of city codes to filter by

        Returns:
            List of NewsEvent objects, most recent first

        Raises:
            InvaderSpotterConnectionError: If connection fails
            ParseError: If page cannot be parsed

        """
        _LOGGER.debug("Fetching news from invader-spotter.art (last %d days)", days)
        url = f"{INVADER_SPOTTER_BASE_URL}/news.php"

        try:
            async with self._session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                if response.status != 200:
                    raise InvaderSpotterConnectionError(f"HTTP {response.status} fetching news")
                html_content = await response.text()

        except aiohttp.ClientError as err:
            raise InvaderSpotterConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise InvaderSpotterConnectionError("Timeout fetching news") from err

        return self._parse_news(html_content, days, city_codes)

    def _parse_news(
        self,
        html_content: str,
        days: int,
        city_codes: set[str] | None,
    ) -> list[NewsEvent]:
        """Parse news HTML content.

        Args:
            html_content: Raw HTML
            days: Number of days to include
            city_codes: Optional city filter

        Returns:
            List of NewsEvent objects

        """
        soup = BeautifulSoup(html_content, "html.parser")
        events: list[NewsEvent] = []
        cutoff_date = datetime.now().date() - timedelta(days=days)

        current_year: int | None = None
        current_month: int | None = None

        # Find all text content that contains news
        # The page structure has months as headers followed by day entries
        content = soup.get_text()
        raw_lines = content.split("\n")

        # Merge continuation lines: a line that does NOT start with "DD :" or a month
        # header is a continuation of the previous day entry (e.g. long "Ajout" lists).
        merged_lines: list[str] = []
        for raw in raw_lines:
            stripped = raw.strip()
            if not stripped:
                continue
            is_day_line = bool(re.match(r"^\d{1,2}\s*:", stripped))
            is_month_line = bool(MONTH_PATTERN.search(stripped))
            if (is_day_line or is_month_line) or not merged_lines:
                merged_lines.append(stripped)
            else:
                # Continuation: append to previous line with a space
                merged_lines[-1] = merged_lines[-1] + " " + stripped

        for line in merged_lines:
            # Check for month header (e.g., "janvier 2026")
            month_match = MONTH_PATTERN.search(line)
            if month_match:
                month_name = month_match.group(1).lower()
                current_year = int(month_match.group(2))
                current_month = MONTH_NAMES.get(month_name)
                continue

            # Check for day entry (starts with "DD :")
            day_match = re.match(r"^(\d{1,2})\s*:", line)
            if day_match and current_year and current_month:
                day = int(day_match.group(1))
                try:
                    event_date = datetime(current_year, current_month, day).date()
                except ValueError:
                    continue

                # Skip if before cutoff
                if event_date < cutoff_date:
                    continue

                # Parse events from this line
                line_events = self._parse_news_line(line, event_date, city_codes)
                events.extend(line_events)

        _LOGGER.debug("Parsed %d news events", len(events))
        return events

    def _parse_news_line(
        self,
        line: str,
        event_date: date,
        city_codes: set[str] | None,
    ) -> list[NewsEvent]:
        """Parse a single news line for events.

        A news line can contain multiple event types separated by periods.
        Example: "Réactivation de PA_08. Destruction de PA_834"

        Args:
            line: The news line text
            event_date: Date of this news entry
            city_codes: Optional city filter

        Returns:
            List of NewsEvent objects found in this line

        """
        events: list[NewsEvent] = []

        # Split line into segments by periods (but keep segments together)
        # Each segment may have a different event type
        segments = re.split(r"\.(?=\s*[A-ZÀ-Ü])", line)

        for segment in segments:
            segment = segment.strip()
            if not segment:
                continue

            segment_lower = segment.lower()

            # Determine event type for this segment
            event_type: NewsEventType | None = None
            for keyword, etype in NEWS_EVENT_KEYWORDS.items():
                if keyword in segment_lower:
                    event_type = etype
                    break

            if not event_type:
                continue

            # Find all invader IDs in this segment
            # Pattern: PA_1554, NY_156, etc.
            invader_ids = re.findall(r"([A-Z]{2,5}_\d{1,4})", segment)

            for invader_id in invader_ids:
                # Extract city code from invader ID (e.g., "PA" from "PA_1554")
                city_code = invader_id.split("_")[0]

                # Filter by city if specified
                if city_codes and city_code not in city_codes:
                    continue

                events.append(
                    NewsEvent(
                        event_type=event_type,
                        invader_id=invader_id,
                        city_code=city_code,
                        event_date=event_date,
                        raw_text=segment,
                    )
                )

        return events

    async def get_news_for_cities(
        self,
        city_codes: set[str],
        days: int = 30,
    ) -> dict[str, list[NewsEvent]]:
        """Get news events grouped by city.

        Args:
            city_codes: Set of city codes to fetch news for
            days: Number of days of news to fetch

        Returns:
            Dict mapping city code to list of NewsEvent

        """
        all_events = await self.get_news(days=days, city_codes=city_codes)

        # Group by city
        by_city: dict[str, list[NewsEvent]] = {code: [] for code in city_codes}
        for event in all_events:
            if event.city_code in by_city:
                by_city[event.city_code].append(event)

        return by_city
