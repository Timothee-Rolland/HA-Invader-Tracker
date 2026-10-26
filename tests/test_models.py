"""Tests for data models."""

from datetime import datetime

from custom_components.invader_tracker.models import (
    City,
    CityStats,
    FlashedInvader,
    Invader,
    InvaderStatus,
    StateSnapshot,
    normalize_invader_id,
)


class TestNormalizeInvaderId:
    """Tests for normalize_invader_id."""

    def test_strips_zero_padding(self):
        """Awazleon pads the number, Flash Invader does not."""
        assert normalize_invader_id("PA_01") == "PA_1"
        assert normalize_invader_id("PA_0346") == "PA_346"

    def test_upper_cases_and_trims(self):
        """Casing and stray whitespace must not break the matching."""
        assert normalize_invader_id("na_01") == "NA_1"
        assert normalize_invader_id("  pa_1  ") == "PA_1"

    def test_already_normalized_is_unchanged(self):
        """An already normalized ID stays as is."""
        assert normalize_invader_id("PA_1554") == "PA_1554"

    def test_non_numeric_suffix_is_kept(self):
        """IDs that do not end with a number are only upper-cased."""
        assert normalize_invader_id("pa_bis") == "PA_BIS"
        assert normalize_invader_id("paris") == "PARIS"


class TestInvader:
    """Tests for Invader model."""

    def test_is_flashable_ok(self):
        """Test is_flashable for OK status."""
        invader = Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.OK,
        )
        assert invader.is_flashable is True

    def test_is_flashable_damaged(self):
        """Test is_flashable for DAMAGED status."""
        invader = Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.DAMAGED,
        )
        assert invader.is_flashable is True

    def test_is_flashable_destroyed(self):
        """Test is_flashable for DESTROYED status."""
        invader = Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.DESTROYED,
        )
        assert invader.is_flashable is False

    def test_is_flashable_unknown(self):
        """Test is_flashable for UNKNOWN status."""
        invader = Invader(
            id="PA_001",
            city_code="PA",
            city_name="Paris",
            points=10,
            status=InvaderStatus.UNKNOWN,
        )
        assert invader.is_flashable is False


class TestCityStats:
    """Tests for CityStats model."""

    def test_unflashed_count(self, mock_invaders_paris, mock_flashed_invaders):
        """Test unflashed count calculation."""
        city = City(code="PA", name="Paris")
        stats = CityStats(
            city=city,
            all_invaders=mock_invaders_paris,
            flashed_invaders=mock_flashed_invaders,
        )

        # PA_001 and PA_002 are flashed
        # PA_003 is unflashed and OK (flashable)
        # PA_004 is unflashed and DESTROYED (not flashable)
        assert stats.unflashed_count == 1  # Only PA_003
        assert stats.unflashed_gone_count == 1  # Only PA_004

    def test_padded_flashed_ids_still_count_as_flashed(self):
        """Nantes: Flash Invader returns "NA_01", awazleon "NA_1" — same invader.

        Before normalization both sources were compared raw, so a flashed
        invader was counted a second time as unflashed (available or gone)
        and flashed + unflashed + gone overshot the total.
        """
        city = City(code="NA", name="Nantes")
        all_invaders = [
            Invader(id="NA_1", city_code="NA", city_name="Nantes", points=50, status=InvaderStatus.OK),
            Invader(id="NA_2", city_code="NA", city_name="Nantes", points=50, status=InvaderStatus.DESTROYED),
            Invader(id="NA_3", city_code="NA", city_name="Nantes", points=50, status=InvaderStatus.DESTROYED),
        ]
        flashed = [
            FlashedInvader(id="NA_01", name="NA_01", city_id=42, points=50, image_url=""),
            FlashedInvader(id="na_02", name="na_02", city_id=42, points=50, image_url=""),
        ]
        stats = CityStats(city=city, all_invaders=all_invaders, flashed_invaders=flashed)

        assert stats.flashed_count == 2
        assert stats.unflashed_count == 0
        assert [inv.id for inv in stats.unflashed_gone] == ["NA_3"]
        assert stats.flashed_count + stats.unflashed_count + stats.unflashed_gone_count == stats.total_count

    def test_padded_flashed_ids_in_news_lists(self):
        """New/reactivated invaders flashed under a padded ID are not offered again."""
        city = City(code="NA", name="Nantes")
        new = Invader(id="NA_4", city_code="NA", city_name="Nantes", points=50, status=InvaderStatus.OK)
        reactivated = Invader(id="NA_5", city_code="NA", city_name="Nantes", points=50, status=InvaderStatus.OK)
        stats = CityStats(
            city=city,
            all_invaders=[new, reactivated],
            flashed_invaders=[
                FlashedInvader(id="NA_04", name="NA_04", city_id=42, points=50, image_url=""),
                FlashedInvader(id="na_05", name="na_05", city_id=42, points=50, image_url=""),
            ],
            new_invaders=[new],
            reactivated_invaders=[reactivated],
        )

        assert stats.unflashed_new == []
        assert stats.unflashed_reactivated == []
        assert stats.unflashed_new_count == 0

    def test_total_count(self, mock_invaders_paris):
        """Test total count."""
        city = City(code="PA", name="Paris")
        stats = CityStats(
            city=city,
            all_invaders=mock_invaders_paris,
        )
        assert stats.total_count == 4

    def test_flashed_count(self, mock_flashed_invaders):
        """Test flashed count."""
        city = City(code="PA", name="Paris")
        stats = CityStats(
            city=city,
            flashed_invaders=mock_flashed_invaders,
        )
        assert stats.flashed_count == 2


class TestStateSnapshot:
    """Tests for StateSnapshot model."""

    def test_get_new_invaders(self):
        """Test detecting new invaders."""
        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            invader_ids_by_city={"PA": {"PA_001", "PA_002"}},
            status_by_invader={},
        )

        current_ids = {"PA_001", "PA_002", "PA_003"}
        new_ids = snapshot.get_new_invaders("PA", current_ids)

        assert new_ids == {"PA_003"}

    def test_get_new_invaders_empty_previous(self):
        """Test detecting new invaders with no previous data."""
        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            invader_ids_by_city={},
            status_by_invader={},
        )

        current_ids = {"PA_001", "PA_002"}
        new_ids = snapshot.get_new_invaders("PA", current_ids)

        assert new_ids == {"PA_001", "PA_002"}

    def test_get_reactivated(self):
        """Test detecting reactivated invaders."""
        snapshot = StateSnapshot(
            timestamp=datetime.now(),
            invader_ids_by_city={"PA": {"PA_001"}},
            status_by_invader={"PA_001": InvaderStatus.OK},  # Current status in snapshot
            previous_status={"PA_001": InvaderStatus.DESTROYED},  # Was destroyed before
        )

        current_invaders = [
            Invader(
                id="PA_001",
                city_code="PA",
                city_name="Paris",
                points=10,
                status=InvaderStatus.OK,  # Now OK (reactivated)
            )
        ]

        reactivated = snapshot.get_reactivated(current_invaders)
        assert len(reactivated) == 1
        assert reactivated[0].id == "PA_001"
