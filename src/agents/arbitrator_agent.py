import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def arbitrator_agent(state: MeetingState) -> MeetingState:
    """Proposes meeting slots by arbitrating between participant preferences."""
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    preferences = state.get("extracted_preferences", {})
    round_num = state.get("negotiation_round", 0) + 1
    prior_slots = state.get("proposed_slots") or []

    prior_context = ""
    if prior_slots:
        prior_context = f"\nPreviously proposed slots (rejected): {prior_slots}\n"

    response = model.invoke([
        SystemMessage(content=(
            "You are a neutral meeting arbitrator. Given participant availability analysis, "
            "propose up to 3 concrete meeting time slots ranked by suitability. "
            "Avoid previously rejected slots. Respond with a JSON list of slot objects "
            "with keys: day, time, duration_minutes, rationale."
        )),
        HumanMessage(content=(
            f"Round {round_num} of negotiation.\n"
            f"Preference summary:\n{preferences.get('summary', '')}"
            f"{prior_context}"
            "\nPropose the best available meeting slots."
        )),
    ])

    proposed = [{"raw": response.content, "round": round_num}]

    new_status = "agreed" if round_num >= 3 else "negotiating"

    return {
        **state,
        "proposed_slots": proposed,
        "negotiation_round": round_num,
        "status": new_status,
        "messages": state["messages"] + [response],
    }
