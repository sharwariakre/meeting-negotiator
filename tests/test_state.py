import typing
import pytest
from src.state import MeetingState


class TestInitialStateDefaults:
    def test_status_is_negotiating(self, base_state):
        assert base_state["status"] == "negotiating"

    def test_round_count_is_zero(self, base_state):
        assert base_state["round_count"] == 0

    def test_counteroffer_reasoning_is_none(self, base_state):
        assert base_state["counteroffer_reasoning"] is None

    def test_proposals_are_none(self, base_state):
        assert base_state["proposal_a"] is None
        assert base_state["proposal_b"] is None

    def test_agreed_slot_is_none(self, base_state):
        assert base_state["agreed_slot"] is None

    def test_messages_is_empty(self, base_state):
        assert base_state["messages"] == []


class TestStateFieldsPresent:
    def test_all_required_fields_exist(self):
        hints = typing.get_type_hints(MeetingState)
        required = {
            "messages",
            "participants",
            "meeting_request",
            "proposal_a",
            "proposal_b",
            "agreed_slot",
            "round_count",
            "counteroffer_reasoning",
            "status",
        }
        assert required.issubset(set(hints.keys()))

    def test_no_stale_fields(self):
        # Ensure removed fields from prior refactors are gone
        hints = typing.get_type_hints(MeetingState)
        stale = {"negotiation_round", "extracted_preferences", "proposed_slots"}
        assert stale.isdisjoint(set(hints.keys()))


class TestStatusLiterals:
    def test_valid_values(self):
        hints = typing.get_type_hints(MeetingState)
        args = set(typing.get_args(hints["status"]))
        assert args == {"negotiating", "consensus", "escalated"}

    def test_no_extra_values(self):
        hints = typing.get_type_hints(MeetingState)
        args = typing.get_args(hints["status"])
        assert len(args) == 3

    @pytest.mark.parametrize("status", ["negotiating", "consensus", "escalated"])
    def test_each_valid_status_accepted(self, base_state, status):
        state = {**base_state, "status": status}
        assert state["status"] == status
