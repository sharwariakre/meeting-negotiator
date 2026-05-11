import pytest
from src.agents.arbitrator_agent import compute_overlaps, _parse_window


# ---------------------------------------------------------------------------
# _parse_window unit tests
# ---------------------------------------------------------------------------

class TestParseWindow:
    def test_trailing_period_am(self):
        assert _parse_window("Monday 9-11am") == ("monday", 9, 11)

    def test_trailing_period_pm(self):
        assert _parse_window("Wednesday 2-4pm") == ("wednesday", 14, 16)

    def test_explicit_period_crossing_noon(self):
        assert _parse_window("Friday 10am-12pm") == ("friday", 10, 12)

    def test_explicit_period_am_to_pm(self):
        assert _parse_window("Friday 11am-1pm") == ("friday", 11, 13)

    def test_case_insensitive(self):
        assert _parse_window("MONDAY 9-11AM") == ("monday", 9, 11)

    def test_invalid_day_returns_none(self):
        assert _parse_window("Someday 9-11am") is None

    def test_unparseable_returns_none(self):
        assert _parse_window("no time here") is None


# ---------------------------------------------------------------------------
# compute_overlaps tests
# ---------------------------------------------------------------------------

class TestComputeOverlaps:
    def test_basic_overlap(self):
        # Alice: Mon 9-11am, Bob: Mon 10am-12pm → overlap Mon 10-11am
        participants = [
            {"availability": ["Monday 9-11am"]},
            {"availability": ["Monday 10am-12pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert len(result) == 1
        assert result[0]["day"] == "Monday"
        assert result[0]["start"] == 10
        assert result[0]["end"] == 11
        assert result[0]["duration_minutes"] == 60

    def test_no_overlap(self):
        # Conflict profiles: Alice Tue/Thu/Fri mornings, Bob Mon/Wed/Thu evenings
        participants = [
            {"availability": ["Tuesday 9-11am", "Thursday 2-4pm", "Friday 9-11am"]},
            {"availability": ["Monday 1-3pm", "Wednesday 3-5pm", "Thursday 5-7pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert result == []

    def test_exact_duration_match(self):
        # Overlap window is exactly required_minutes — must be included
        participants = [
            {"availability": ["Monday 10-11am"]},
            {"availability": ["Monday 9am-12pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert len(result) == 1
        assert result[0]["duration_minutes"] == 60

    def test_below_duration_threshold(self):
        # Overlap is 60 min but meeting requires 90 — should return nothing
        participants = [
            {"availability": ["Monday 10-11am"]},
            {"availability": ["Monday 9am-12pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=90)
        assert result == []

    def test_multiple_overlaps(self):
        # Default profiles: Monday 10-11am and Wednesday 3-4pm both overlap
        participants = [
            {"availability": ["Monday 9-11am", "Wednesday 2-4pm"]},
            {"availability": ["Monday 10am-12pm", "Wednesday 3-5pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        days = {r["day"] for r in result}
        assert days == {"Monday", "Wednesday"}
        assert len(result) == 2

    def test_three_participants(self):
        # All three must share the window for it to count
        participants = [
            {"availability": ["Monday 9-11am"]},
            {"availability": ["Monday 10am-12pm"]},
            {"availability": ["Monday 10-11am"]},  # narrows the window
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert len(result) == 1
        assert result[0]["start"] == 10
        assert result[0]["end"] == 11

    def test_three_participants_no_common_window(self):
        # Third participant eliminates the overlap that exists between the first two
        participants = [
            {"availability": ["Monday 9-11am"]},
            {"availability": ["Monday 10am-12pm"]},
            {"availability": ["Tuesday 1-3pm"]},   # no Monday at all
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert result == []

    def test_noon_edge_case(self):
        # Window crosses noon: 11am-1pm parsed as 11:00-13:00
        participants = [
            {"availability": ["Friday 11am-1pm"]},   # 11:00-13:00
            {"availability": ["Friday 12pm-2pm"]},   # 12:00-14:00
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert len(result) == 1
        assert result[0]["start"] == 12   # noon
        assert result[0]["end"] == 13
        assert result[0]["duration_minutes"] == 60

    def test_result_label_format(self):
        participants = [
            {"availability": ["Monday 9-11am"]},
            {"availability": ["Monday 10am-12pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert result[0]["label"] == "Monday 10am–11am"

    def test_empty_availability(self):
        participants = [
            {"availability": []},
            {"availability": ["Monday 10am-12pm"]},
        ]
        result = compute_overlaps(participants, required_minutes=60)
        assert result == []
