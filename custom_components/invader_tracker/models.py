"""Data models for Invader Tracker integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum


class InvaderStatus(Enum):
    """Status from invader-spotter community data."""

    OK = "ok"  # Intact, flashable
    DAMAGED = "damaged"  # Dégradé, flashable
    VERY_DAMAGED = "very_damaged"  # Très dégradé, flashable
    DESTROYED = "destroyed"  # Détruit, NOT flashable
    NOT_VISIBLE = "not_visible"  # Non visible, NOT flashable
    UNKNOWN = "unknown"  # Inconnu, NOT flashable


@dataclass
class Invader:
    """Represents an invader from invader-spotter.art."""

    id: str  # e.g., "PA_346", "LYN_042"
    city_code: str  # e.g., "PA", "LYN"
    city_name: str  # e.g., "Paris", "Lyon"
    points: int  # Point value (10-100)
    status: InvaderStatus  # Current known status
    install_date: date | None = None  # Date de pose
    status_date: date | None = None  # When status was last reported
    status_source: str | None = None  # Who reported (e.g., "spott", "user")

    @property
    def is_flashable(self) -> bool:
        """Can this invader still be flashed?"""
        # Only OK, DAMAGED, and VERY_DAMAGED are flashable
        return self.status in (InvaderStatus.OK, InvaderStatus.DAMAGED, InvaderStatus.VERY_DAMAGED)


@dataclass
class FlashedInvader:
    """Represents an invader the user has flashed."""

    id: str  # e.g., "PA_346"
    name: str  # Same as ID typically
    city_id: int  # Numeric city ID from API
    points: int  # Points earned
    image_url: str  # URL to invader image
    install_date: date | None = None  # date_pos from API (None if parse failed)
    flash_date: datetime | None = None  # When user flashed it (None if parse failed)


@dataclass
class City:
    """Represents a city with invaders."""

    code: str  # e.g., "PA", "LYN"
    name: str  # e.g., "Paris", "Lyon"
    country: str = ""  # e.g., "France"
    total_invaders: int = 0  # Count from invader-spotter
    api_city_id: int | None = None  # Numeric ID from Flash Invader API


class NewsEventType(Enum):
    """Type of news event from invader-spotter.art/news.php."""

    ADDED = "added"  # Ajout - New invader added
    REACTIVATED = "reactivated"  # Réactivation - Was destroyed, now OK
    RESTORED = "restored"  # Restauration - Restored/repaired
    DEGRADED = "degraded"  # Dégradation - Status worsened
    DESTROYED = "destroyed"  # Destruction - Now destroyed
    STATUS_UPDATE = "status_update"  # Mise à jour du statut
    ALERT = "alert"  # Alerte


@dataclass
class NewsEvent:
    """A news event from invader-spotter.art/news.php."""

    event_type: NewsEventType
    invader_id: str  # e.g., "PA_1554"
    city_code: str  # e.g., "PA"
    event_date: date  # Date of the event
    raw_text: str = ""  # Original text for debugging

    @property
    def is_positive(self) -> bool:
        """Is this a positive event (new flashable opportunity)?"""
        return self.event_type in (
            NewsEventType.ADDED,
            NewsEventType.REACTIVATED,
            NewsEventType.RESTORED,
        )

    @property
    def is_negative(self) -> bool:
        """Is this a negative event (lost opportunity)?"""
        return self.event_type in (
            NewsEventType.DESTROYED,
            NewsEventType.DEGRADED,
        )


@dataclass
class CityStats:
    """Computed statistics for a tracked city."""

    city: City
    all_invaders: list[Invader] = field(default_factory=list)
    flashed_invaders: list[FlashedInvader] = field(default_factory=list)
    new_invaders: list[Invader] = field(default_factory=list)
    reactivated_invaders: list[Invader] = field(default_factory=list)
    news_events: list[NewsEvent] = field(default_factory=list)

    @property
    def flashed_ids(self) -> set[str]:
        """Get set of flashed invader IDs."""
        return {inv.id for inv in self.flashed_invaders}

    @property
    def unflashed(self) -> list[Invader]:
        """Invaders not flashed AND still flashable."""
        return [inv for inv in self.all_invaders if inv.id not in self.flashed_ids and inv.is_flashable]

    @property
    def unflashed_gone(self) -> list[Invader]:
        """Invaders not flashed AND no longer flashable (missed)."""
        return [inv for inv in self.all_invaders if inv.id not in self.flashed_ids and not inv.is_flashable]

    @property
    def total_count(self) -> int:
        """Total invaders in city."""
        return len(self.all_invaders)

    @property
    def flashed_count(self) -> int:
        """Number of flashed invaders."""
        return len(self.flashed_invaders)

    @property
    def unflashed_count(self) -> int:
        """Number of unflashed but flashable invaders."""
        return len(self.unflashed)

    @property
    def unflashed_gone_count(self) -> int:
        """Number of unflashed and no longer flashable invaders."""
        return len(self.unflashed_gone)

    @property
    def new_count(self) -> int:
        """Number of new + reactivated invaders."""
        return len(self.new_invaders) + len(self.reactivated_invaders)

    @property
    def unflashed_new(self) -> list[Invader]:
        """New invaders that have not been flashed yet."""
        return [inv for inv in self.new_invaders if inv.id not in self.flashed_ids]

    @property
    def unflashed_reactivated(self) -> list[Invader]:
        """Reactivated invaders that have not been flashed yet."""
        return [inv for inv in self.reactivated_invaders if inv.id not in self.flashed_ids]

    @property
    def unflashed_new_count(self) -> int:
        """Number of new + reactivated invaders not yet flashed."""
        return len(self.unflashed_new) + len(self.unflashed_reactivated)

    @property
    def positive_news_count(self) -> int:
        """Number of positive news events (added, reactivated, restored)."""
        return sum(1 for e in self.news_events if e.is_positive)


@dataclass
class StateSnapshot:
    """Snapshot of state for detecting changes."""

    timestamp: datetime
    invader_ids_by_city: dict[str, set[str]] = field(default_factory=dict)
    status_by_invader: dict[str, InvaderStatus] = field(default_factory=dict)
    # Track when each invader was first seen (for "new" detection)
    first_seen_date: dict[str, datetime] = field(default_factory=dict)
    # Track status history for reactivation detection
    previous_status: dict[str, InvaderStatus] = field(default_factory=dict)
    # Track when each city was first seen in awazleon (for new city detection)
    city_first_seen: dict[str, datetime] = field(default_factory=dict)

    def get_new_invaders(self, city_code: str, current_ids: set[str]) -> set[str]:
        """Return IDs that are in current but not in snapshot."""
        previous = self.invader_ids_by_city.get(city_code, set())
        return current_ids - previous

    def get_recently_added(self, current_invaders: list[Invader], days: int = 30) -> list[Invader]:
        """Return invaders first seen within the last N days."""
        cutoff = datetime.now() - timedelta(days=days)
        recently_added = []
        for inv in current_invaders:
            first_seen = self.first_seen_date.get(inv.id)
            if first_seen and first_seen >= cutoff:
                recently_added.append(inv)
        return recently_added

    def get_reactivated(self, current_invaders: list[Invader]) -> list[Invader]:
        """Return invaders whose status changed from non-flashable to flashable."""
        non_flashable = {InvaderStatus.DESTROYED, InvaderStatus.NOT_VISIBLE, InvaderStatus.UNKNOWN}
        flashable = {InvaderStatus.OK, InvaderStatus.DAMAGED, InvaderStatus.VERY_DAMAGED}
        reactivated = []
        for inv in current_invaders:
            prev_status = self.previous_status.get(inv.id)
            if prev_status in non_flashable and inv.status in flashable:
                reactivated.append(inv)
        return reactivated


@dataclass
class ChangeSet:
    """Changes detected since last snapshot."""

    new_invaders: list[Invader] = field(default_factory=list)
    reactivated_invaders: list[Invader] = field(default_factory=list)


@dataclass
class PlayerProfile:
    """Profile of the authenticated user from Flash Invader API."""

    name: str
    score: int
    rank: int
    rank_str: str
    si_found: int
    city_found: int
    registration_date: str = ""
    total_si_count: int = 0


@dataclass
class FollowedPlayer:
    """A player followed by the authenticated user."""

    name: str
    score: int
    rank: int
    rank_str: str
    invaders_count: int
