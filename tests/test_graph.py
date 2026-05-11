from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.agents.arbitrator_agent import arbitrator_agent
from src.agents.preference_agent import make_preference_agent
from src.graph import build_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ai(content: str) -> AIMessage:
    return AIMessage(content=content)


@contextmanager
def mock_all_llms(pref_content: str, arb_content: str, comm_content: str):
    """Patches ChatOllama in all three agent modules simultaneously."""
    with (
        patch("src.agents.preference_agent.ChatOllama") as mock_pref,
        patch("src.agents.arbitrator_agent.ChatOllama") as mock_arb,
        patch("src.agents.communication_agent.ChatOllama") as mock_comm,
    ):
        mock_pref.return_value.invoke.return_value = ai(pref_content)
        mock_arb.return_value.invoke.return_value = ai(arb_content)
        mock_comm.return_value.invoke.return_value = ai(comm_content)
        yield mock_pref, mock_arb, mock_comm


# ---------------------------------------------------------------------------
# test_consensus_path
# ---------------------------------------------------------------------------

class TestConsensusPath:
    def test_status_is_consensus(self, base_state):
        with mock_all_llms(
            pref_content="Slot: Monday 10am-11am works best.",
            arb_content="CONSENSUS: YES\nMonday 10am-11am is the agreed slot.",
            comm_content="Hi team, meeting confirmed for Monday 10am.",
        ):
            result = build_graph().invoke(base_state)

        assert result["status"] == "consensus"

    def test_agreed_slot_is_populated(self, base_state):
        with mock_all_llms(
            pref_content="Slot: Monday 10am-11am.",
            arb_content="CONSENSUS: YES\nMonday 10am-11am.",
            comm_content="Meeting confirmed.",
        ):
            result = build_graph().invoke(base_state)

        assert result["agreed_slot"] is not None
        assert result["agreed_slot"].get("message") == "Meeting confirmed."

    def test_communication_agent_ran(self, base_state):
        with mock_all_llms(
            pref_content="Slot: Monday 10am.",
            arb_content="CONSENSUS: YES\nMonday 10am-11am.",
            comm_content="Confirmed: Monday 10am.",
        ) as (_, _, mock_comm):
            build_graph().invoke(base_state)

        mock_comm.return_value.invoke.assert_called_once()

    def test_resolves_in_one_round(self, base_state):
        with mock_all_llms(
            pref_content="Monday 10am works.",
            arb_content="CONSENSUS: YES\nMonday 10am-11am.",
            comm_content="Confirmed.",
        ):
            result = build_graph().invoke(base_state)

        assert result["round_count"] == 1


# ---------------------------------------------------------------------------
# test_escalation_path
# ---------------------------------------------------------------------------

class TestEscalationPath:
    def test_status_is_escalated(self, conflict_state):
        with mock_all_llms(
            pref_content="Tuesday 9am works for me.",
            arb_content="CONSENSUS: NO\nBob should flex to Alice's Tuesday morning.",
            comm_content="Escalation: no agreement after 3 rounds.",
        ):
            result = build_graph().invoke(conflict_state)

        assert result["status"] == "escalated"

    def test_round_count_is_three(self, conflict_state):
        with mock_all_llms(
            pref_content="Tuesday 9am works.",
            arb_content="CONSENSUS: NO\nBob should flex.",
            comm_content="Escalation notice.",
        ):
            result = build_graph().invoke(conflict_state)

        assert result["round_count"] == 3

    def test_escalation_message_in_agreed_slot(self, conflict_state):
        with mock_all_llms(
            pref_content="Tuesday 9am.",
            arb_content="CONSENSUS: NO\nBob should flex.",
            comm_content="No agreement reached. Please coordinate directly.",
        ):
            result = build_graph().invoke(conflict_state)

        assert result["agreed_slot"]["message"] == "No agreement reached. Please coordinate directly."

    def test_arbitrator_called_three_times(self, conflict_state):
        with mock_all_llms(
            pref_content="Tuesday 9am.",
            arb_content="CONSENSUS: NO\nBob should flex.",
            comm_content="Escalation.",
        ) as (_, mock_arb, _):
            build_graph().invoke(conflict_state)

        assert mock_arb.return_value.invoke.call_count == 3


# ---------------------------------------------------------------------------
# test_round_count_increments
# ---------------------------------------------------------------------------

class TestRoundCountIncrements:
    def test_arbitrator_increments_by_one(self, conflict_state):
        state = {**conflict_state, "round_count": 1}
        with patch("src.agents.arbitrator_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai(
                "CONSENSUS: NO\nBob should flex."
            )
            result = arbitrator_agent(state)

        assert result["round_count"] == 2

    def test_starts_at_zero_reaches_one(self, conflict_state):
        with patch("src.agents.arbitrator_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai(
                "CONSENSUS: NO\nBob should flex."
            )
            result = arbitrator_agent(conflict_state)

        assert result["round_count"] == 1

    def test_escalates_at_three(self, conflict_state):
        state = {**conflict_state, "round_count": 2}
        with patch("src.agents.arbitrator_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai(
                "CONSENSUS: NO\nNo agreement possible."
            )
            result = arbitrator_agent(state)

        assert result["round_count"] == 3
        assert result["status"] == "escalated"


# ---------------------------------------------------------------------------
# test_counteroffer_passed_to_preference_agents
# ---------------------------------------------------------------------------

class TestCounterOfferFeedback:
    def test_counteroffer_appears_in_llm_prompt(self, base_state):
        counteroffer_text = "Bob should flex to Alice's Tuesday morning slot."
        state = {
            **base_state,
            "round_count": 1,
            "counteroffer_reasoning": counteroffer_text,
        }
        agent_fn = make_preference_agent("A")

        with patch("src.agents.preference_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai("Revised: Tuesday 9am.")
            agent_fn(state)

        call_messages = mock_cls.return_value.invoke.call_args[0][0]
        full_prompt = " ".join(m.content for m in call_messages)
        assert counteroffer_text in full_prompt

    def test_no_pressure_block_on_round_zero(self, base_state):
        state = {**base_state, "round_count": 0, "counteroffer_reasoning": None}
        agent_fn = make_preference_agent("A")

        with patch("src.agents.preference_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai("Monday 10am works.")
            agent_fn(state)

        call_messages = mock_cls.return_value.invoke.call_args[0][0]
        full_prompt = " ".join(m.content for m in call_messages)
        assert "arbitrator has reviewed" not in full_prompt

    def test_counteroffer_in_state_after_no_consensus(self, conflict_state):
        with patch("src.agents.arbitrator_agent.ChatOllama") as mock_cls:
            reasoning = "CONSENSUS: NO\nBob should flex to Alice's Thursday slot."
            mock_cls.return_value.invoke.return_value = ai(reasoning)
            result = arbitrator_agent(conflict_state)

        assert result["counteroffer_reasoning"] is not None
        assert "CONSENSUS: NO" in result["counteroffer_reasoning"]

    def test_counteroffer_cleared_on_consensus(self, base_state):
        # counteroffer_reasoning should be None after a consensus round
        state = {
            **base_state,
            "counteroffer_reasoning": "Some prior counteroffer.",
            "round_count": 0,
        }
        with patch("src.agents.arbitrator_agent.ChatOllama") as mock_cls:
            mock_cls.return_value.invoke.return_value = ai(
                "CONSENSUS: YES\nMonday 10am-11am agreed."
            )
            result = arbitrator_agent(state)

        assert result["counteroffer_reasoning"] is None
        assert result["status"] == "consensus"
