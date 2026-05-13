import os
from typing import Callable
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def make_preference_agent(participant_id: str) -> Callable[[MeetingState], MeetingState]:
    """
    Factory returning a node that advocates for one participant.
    On subsequent rounds it reads counteroffer_reasoning and adjusts proposals
    under pressure — while still representing the participant's real constraints.
    """
    proposal_key = f"proposal_{participant_id.lower()}"

    def agent(state: MeetingState) -> MeetingState:
        model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

        participant = next(
            p for p in state["participants"] if p["id"] == participant_id
        )
        meeting = state["meeting_request"]
        round_count = state.get("round_count", 0)
        counteroffer = state.get("counteroffer_reasoning")

        pressure_block = ""
        if counteroffer and round_count > 0:
            pressure_block = (
                f"\n\nThe arbitrator has reviewed both proposals and returned the following feedback "
                f"after round {round_count}:\n\"{counteroffer}\"\n\n"
                "You must respond to this pressure as a real advocate would: acknowledge the arbitrator's "
                "reasoning, but push back where your participant's constraints are genuinely non-negotiable. "
                "If there is room to flex on a lower-priority constraint, do so — but be explicit about what "
                "you are conceding and what you are holding firm on. Revise your proposed slots accordingly."
            )

        response = model.invoke([
            SystemMessage(content=(
                "You are a scheduling advocate for a single meeting participant. "
                "Propose slots that work for YOUR participant. Do not seek overlap yourself — "
                "that is the arbitrator's job. Represent their constraints honestly, "
                "and when under pressure, negotiate like a real advocate: flex where you can, "
                "hold firm where you must, and explain every decision."
            )),
            HumanMessage(content=(
                f"You are representing: {participant['name']} ({participant['role']}, {participant['seniority']})\n"
                f"Context: {participant['context']}\n\n"
                f"Meeting: {meeting['title']} ({meeting['required_duration_minutes']} min)\n\n"
                f"Availability: {', '.join(s['label'] if isinstance(s, dict) else s for s in participant.get('availability', []))}\n"
                f"Preferred times: {', '.join(participant['preferences']['preferred_times'])}\n"
                f"Constraints: {', '.join(participant['preferences']['constraints'])}"
                f"{pressure_block}\n\n"
                "Propose up to 3 slots. For each, state the day/time and why it works for your participant."
            )),
        ])

        proposal = {
            "participant_id": participant_id,
            "name": participant["name"],
            "role": participant["role"],
            "seniority": participant["seniority"],
            "slots": response.content,
            "round": round_count,
        }

        return {
            **state,
            proposal_key: proposal,
            "messages": state["messages"] + [response],
        }

    agent.__name__ = f"preference_agent_{participant_id}"
    return agent
