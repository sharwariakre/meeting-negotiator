import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def preference_agent(state: MeetingState) -> MeetingState:
    """Extracts and structures participant preferences from profiles."""
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    participants_summary = "\n".join(
        f"- {p['name']}: available {', '.join(p['availability'])}; "
        f"prefers {', '.join(p['preferences']['preferred_times'])} meetings; "
        f"constraints: {', '.join(p['preferences']['constraints'])}"
        for p in state["participants"]
    )

    meeting = state["meeting_request"]

    response = model.invoke([
        SystemMessage(content=(
            "You are a scheduling assistant. Analyze participant availability and preferences, "
            "then return a structured JSON summary of overlapping availability windows "
            "and any conflicts to resolve."
        )),
        HumanMessage(content=(
            f"Meeting: {meeting['title']} ({meeting['required_duration_minutes']} min)\n\n"
            f"Participants:\n{participants_summary}\n\n"
            "Identify overlapping time slots and summarize each participant's constraints."
        )),
    ])

    return {
        **state,
        "extracted_preferences": {
            "summary": response.content,
            "participants": state["participants"],
        },
        "status": "negotiating",
        "messages": state["messages"] + [response],
    }
