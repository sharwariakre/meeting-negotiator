import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState

_CONSENSUS_MARKER = "CONSENSUS: YES"
_NO_CONSENSUS_MARKER = "CONSENSUS: NO"


def arbitrator_agent(state: MeetingState) -> MeetingState:
    """
    Compares both proposals and either finds consensus or issues a counteroffer.
    Sets status to 'consensus', 'negotiating', or 'escalated'.
    Increments round_count each time it runs.
    """
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    proposal_a = state.get("proposal_a") or {}
    proposal_b = state.get("proposal_b") or {}
    meeting = state["meeting_request"]
    round_count = state.get("round_count", 0) + 1

    def format_proposal(p: dict) -> str:
        if not p:
            return "No proposal received."
        return (
            f"Participant: {p.get('name')} | Role: {p.get('role')} | "
            f"Seniority: {p.get('seniority')} | Round: {p.get('round', 0)}\n"
            f"Proposed slots:\n{p.get('slots', 'None')}"
        )

    response = model.invoke([
        SystemMessage(content=(
            "You are a neutral meeting arbitrator. Your task each round:\n"
            "1. Check whether any slot appears in BOTH proposals (same day and overlapping time).\n"
            "2. If overlap exists: output exactly the line 'CONSENSUS: YES' on its own line, "
            "then name the agreed slot and briefly explain why it works for both.\n"
            "3. If no overlap exists: output exactly the line 'CONSENSUS: NO' on its own line, "
            "then write a counteroffer addressed to both participants. Be specific about "
            "who should flex, which constraint they should relax, and why — using their "
            "seniority and context as justification. Keep this under 5 sentences.\n"
            "Be decisive. Do not hedge. Seniority and meeting ownership are legitimate factors."
        )),
        HumanMessage(content=(
            f"Meeting: {meeting['title']} ({meeting['required_duration_minutes']} min)\n"
            f"Arbitration round: {round_count}\n\n"
            f"--- Proposal A ---\n{format_proposal(proposal_a)}\n\n"
            f"--- Proposal B ---\n{format_proposal(proposal_b)}\n\n"
            "Determine whether consensus exists. Follow the output format exactly."
        )),
    ])

    content = response.content
    consensus_reached = _CONSENSUS_MARKER in content

    if consensus_reached:
        return {
            **state,
            "round_count": round_count,
            "agreed_slot": {"resolution": content},
            "counteroffer_reasoning": None,
            "status": "consensus",
            "messages": state["messages"] + [response],
        }

    # No consensus — escalate if rounds exhausted, otherwise issue counteroffer
    if round_count >= 3:
        escalation = (
            f"After {round_count} rounds of negotiation, no consensus was reached.\n\n"
            f"Final arbitrator assessment:\n{content}"
        )
        return {
            **state,
            "round_count": round_count,
            "agreed_slot": {"resolution": escalation},
            "counteroffer_reasoning": content,
            "status": "escalated",
            "messages": state["messages"] + [response],
        }

    return {
        **state,
        "round_count": round_count,
        "counteroffer_reasoning": content,
        "status": "negotiating",
        "messages": state["messages"] + [response],
    }
