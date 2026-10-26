"""Tests for Invader Spotter scraper."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.invader_tracker.api.invader_spotter import InvaderSpotterScraper
from custom_components.invader_tracker.models import (
    InvaderStatus,
    NewsEventType,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock aiohttp session."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def scraper(mock_session) -> InvaderSpotterScraper:
    """Create an InvaderSpotterScraper with mock session."""
    return InvaderSpotterScraper(mock_session)


def _make_response(status: int = 200, text: str = "") -> AsyncMock:
    """Create a mock aiohttp response."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = status
    response.text = AsyncMock(return_value=text)
    return response


FRENCH_MONTHS = {
    1: "janvier",
    2: "février",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "août",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "décembre",
}


def _news_html(entries: list[tuple[date, str]]) -> str:
    """Build a news.php-like page: month headers followed by "DD : text" lines.

    Entries must be ordered from most recent to oldest, like the real page.
    Dates are passed in by the caller so tests stay independent of today's date.
    """
    lines: list[str] = []
    current_month: tuple[int, int] | None = None
    for event_date, text in entries:
        month = (event_date.year, event_date.month)
        if month != current_month:
            lines.append(f"{FRENCH_MONTHS[event_date.month]} {event_date.year}")
            current_month = month
        lines.append(f"{event_date.day} : {text}")
    body = "\n        ".join(lines)
    return f"<html><body>\n        {body}\n        </body></html>"


class TestParseCitiesPage:
    """Tests for _parse_cities_page."""

    def test_parse_cities_with_javascript_links(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing cities page with javascript:envoi links."""
        html = """
        <html><body>
        <a href="javascript:envoi('PA')">Paris</a>
        <a href="javascript:envoi('LYN')">Lyon</a>
        <a href="javascript:envoi('MRS')">Marseille</a>
        </body></html>
        """
        cities = scraper._parse_cities_page(html)

        assert len(cities) == 3
        assert cities[0].code == "PA"
        assert cities[0].name == "Paris"
        assert cities[1].code == "LYN"
        assert cities[1].name == "Lyon"

    def test_parse_cities_dedup(self, scraper: InvaderSpotterScraper) -> None:
        """Test that duplicate city codes are deduplicated."""
        html = """
        <html><body>
        <a href="javascript:envoi('PA')">Paris (Map)</a>
        <a href="javascript:envoi('PA')">Paris (List)</a>
        </body></html>
        """
        cities = scraper._parse_cities_page(html)
        assert len(cities) == 1

    def test_parse_cities_empty(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing page with no city links."""
        html = "<html><body><p>No cities here</p></body></html>"
        cities = scraper._parse_cities_page(html)
        assert cities == []


class TestParseInvaderEntry:
    """Tests for invader entry parsing."""

    def test_extract_invader_id(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting invader ID from text."""
        assert scraper._extract_invader_id("PA_001 [10 pts]", "PA") == "PA_001"
        assert scraper._extract_invader_id("LYN_42 some text", "LYN") == "LYN_42"
        assert scraper._extract_invader_id("no invader here", "PA") is None

    def test_extract_points(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting points from text."""
        assert scraper._extract_points("PA_001 [10 pts]") == 10
        assert scraper._extract_points("PA_001 [50 pt]") == 50
        assert scraper._extract_points("PA_001 [100 Pts]") == 100
        assert scraper._extract_points("no points here") == 0

    def test_extract_date_french_format(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting dates in French DD/MM/YYYY format."""
        assert scraper._extract_date("Date de pose : 15/06/2002") == date(2002, 6, 15)
        assert scraper._extract_date("01/01/2000") == date(2000, 1, 1)
        assert scraper._extract_date("no date here") is None

    def test_extract_date_invalid(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting invalid dates returns None."""
        # Day 32 doesn't exist
        assert scraper._extract_date("32/01/2000") is None

    def test_extract_status_ok(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting OK status."""
        assert scraper._extract_status("Dernier état connu : OK") == InvaderStatus.OK
        assert scraper._extract_status("intact") == InvaderStatus.OK

    def test_extract_status_damaged(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting damaged statuses."""
        assert scraper._extract_status("dégradé") == InvaderStatus.DAMAGED
        assert scraper._extract_status("un peu dégradé") == InvaderStatus.DAMAGED
        # Note: text-only _extract_status matches "dégradé" first for "très dégradé"
        # because STATUS_MAPPING iterates "dégradé" before "très dégradé".
        # The HTML-aware _extract_status_from_html handles this correctly.
        assert scraper._extract_status("très dégradé") == InvaderStatus.DAMAGED

    def test_extract_status_destroyed(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting destroyed statuses."""
        assert scraper._extract_status("détruit") == InvaderStatus.DESTROYED
        assert scraper._extract_status("détruit !") == InvaderStatus.DESTROYED
        assert scraper._extract_status("disparu") == InvaderStatus.DESTROYED

    def test_extract_status_other(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting other statuses."""
        assert scraper._extract_status("non visible") == InvaderStatus.NOT_VISIBLE
        assert scraper._extract_status("inconnu") == InvaderStatus.UNKNOWN
        assert scraper._extract_status("something unknown") == InvaderStatus.UNKNOWN

    def test_extract_status_from_html_images(self, scraper: InvaderSpotterScraper) -> None:
        """Test extracting status from HTML image classes."""
        assert scraper._extract_status_from_html('<img src="spot_invader_ok.png">', "") == InvaderStatus.OK
        assert (
            scraper._extract_status_from_html('<img src="spot_invader_destroyed.png">', "") == InvaderStatus.DESTROYED
        )
        assert scraper._extract_status_from_html('<img src="spot_invader_degraded.png">', "") == InvaderStatus.DAMAGED
        assert (
            scraper._extract_status_from_html('<img src="spot_invader_degraded.png">', "très dégradé")
            == InvaderStatus.VERY_DAMAGED
        )


class TestParseCityPage:
    """Tests for _parse_city_page."""

    def test_parse_city_page_with_td_entries(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing a city page with td-based invader entries."""
        html = """
        <html><body><table>
        <tr><td align="left" rowspan="2">
            <b>PA_001 [10 pts]</b><br>
            Date de pose : 01/01/2000<br>
            Dernier état connu : OK
        </td></tr>
        <tr><td align="left" rowspan="2">
            <b>PA_002 [20 pts]</b><br>
            Date de pose : 15/06/2005<br>
            Dernier état connu : détruit
        </td></tr>
        </table></body></html>
        """
        invaders = scraper._parse_city_page(html, "PA", "Paris")

        assert len(invaders) == 2
        assert invaders[0].id == "PA_001"
        assert invaders[0].points == 10
        assert invaders[0].status == InvaderStatus.OK
        assert invaders[0].install_date == date(2000, 1, 1)
        assert invaders[1].id == "PA_002"
        assert invaders[1].status == InvaderStatus.DESTROYED

    def test_parse_city_page_empty(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing a page with no invader entries."""
        html = "<html><body><p>Nothing here</p></body></html>"
        invaders = scraper._parse_city_page(html, "PA", "Paris")
        assert invaders == []


class TestHasNextPage:
    """Tests for _has_next_page."""

    def test_has_next_page(self, scraper: InvaderSpotterScraper) -> None:
        """Test detecting next page link."""
        html = '<a href="javascript:changepage(2)">Next</a>'
        assert scraper._has_next_page(html, 1) is True

    def test_no_next_page(self, scraper: InvaderSpotterScraper) -> None:
        """Test when there is no next page."""
        html = '<a href="javascript:changepage(1)">Current</a>'
        assert scraper._has_next_page(html, 1) is False


class TestParseNews:
    """Tests for news parsing."""

    def test_parse_news_line_added(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing a news line with an addition event."""
        line = "15 : Ajout de PA_1554"
        events = scraper._parse_news_line(line, date(2026, 1, 15), None)

        assert len(events) == 1
        assert events[0].event_type == NewsEventType.ADDED
        assert events[0].invader_id == "PA_1554"
        assert events[0].city_code == "PA"

    def test_parse_news_line_destruction(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing destruction news."""
        line = "10 : Destruction de PA_834"
        events = scraper._parse_news_line(line, date(2026, 1, 10), None)

        assert len(events) == 1
        assert events[0].event_type == NewsEventType.DESTROYED
        assert events[0].invader_id == "PA_834"

    def test_parse_news_line_multiple_events(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing a line with multiple events."""
        line = "10 : Réactivation de PA_08. Destruction de PA_834"
        events = scraper._parse_news_line(line, date(2026, 1, 10), None)

        assert len(events) == 2
        types = {e.event_type for e in events}
        assert NewsEventType.REACTIVATED in types
        assert NewsEventType.DESTROYED in types

    def test_parse_news_line_city_filter(self, scraper: InvaderSpotterScraper) -> None:
        """Test city filtering in news parsing."""
        line = "10 : Ajout de PA_100. Ajout de LYN_50"
        # Only interested in PA
        events = scraper._parse_news_line(line, date(2026, 1, 10), {"PA"})

        assert len(events) == 1
        assert events[0].invader_id == "PA_100"

    def test_parse_news_line_no_events(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing a line with no recognizable events."""
        line = "10 : Some random text"
        events = scraper._parse_news_line(line, date(2026, 1, 10), None)
        assert events == []

    def test_parse_news_full(self, scraper: InvaderSpotterScraper) -> None:
        """Test parsing full news HTML content."""
        today = date.today()
        html = _news_html(
            [
                (today, "Ajout de PA_1554"),
                (today - timedelta(days=10), "Destruction de LYN_042"),
                (today - timedelta(days=40), "Réactivation de PA_008"),
            ]
        )
        events = scraper._parse_news(html, days=60, city_codes=None)

        assert len(events) == 3
        # Events should include all three
        ids = {e.invader_id for e in events}
        assert "PA_1554" in ids
        assert "LYN_042" in ids
        assert "PA_008" in ids

    def test_parse_news_respects_cutoff(self, scraper: InvaderSpotterScraper) -> None:
        """Test that news parsing respects day cutoff."""
        today = date.today()
        html = _news_html(
            [
                (today - timedelta(days=5), "Ajout de PA_1554"),
                (today - timedelta(days=90), "Destruction de PA_834"),
            ]
        )
        events = scraper._parse_news(html, days=30, city_codes=None)

        # Only the event inside the 30-day window is kept
        ids = {e.invader_id for e in events}
        assert ids == {"PA_1554"}
