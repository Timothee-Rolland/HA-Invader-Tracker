"""Tests for data models."""

from datetime import datetime

from custom_components.invader_tracker.models import (
    City,
    CityStats,
    Invader,
    InvaderStatus,
    StateSnapshot,
)


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
