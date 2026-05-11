import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def communication_agent(state: MeetingState) -> MeetingState:
    """Drafts participant-facing messages summarizing the negotiation outcome."""
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    slots = state.get("proposed_slots") or []
    slot_text = slots[-1].get("raw", "No slot proposed.") if slots else "No slot proposed."
    names = [p["name"] for p in state.get("participants", [])]
    meeting_title = state.get("meeting_request", {}).get("title", "the meeting")

    response = model.invoke([
        SystemMessage(content=(
            "You are a professional scheduling assistant. Write a clear, friendly message "
            "to meeting participants confirming the agreed time or explaining next steps."
        )),
        HumanMessage(content=(
            f"Participants: {', '.join(names)}\n"
            f"Meeting: {meeting_title}\n"
            f"Proposed slot details:\n{slot_text}\n\n"
            "Write a short confirmation message to send to all participants."
        )),
    ])

    agreed_slot = {"summary": slot_text, "message": response.content}

    return {
        **state,
        "agreed_slot": agreed_slot,
        "status": "agreed",
        "messages": state["messages"] + [response],
    }
