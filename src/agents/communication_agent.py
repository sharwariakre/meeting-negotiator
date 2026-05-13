import os
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def communication_agent(state: MeetingState) -> MeetingState:
    """Drafts the final participant-facing message for consensus or escalation outcomes."""
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    status = state.get("status", "consensus")
    resolution = (state.get("agreed_slot") or {}).get("resolution", "No resolution available.")
    names = [p["name"] for p in state.get("participants", [])]
    meeting_title = state.get("meeting_request", {}).get("title", "the meeting")
    round_count = state.get("round_count", 0)

    if status == "escalated":
        system_prompt = (
            "You are a professional scheduling assistant. The automated negotiation failed to reach "
            "consensus after multiple rounds. Write a brief, professional message to the participants "
            "informing them that human intervention is needed to schedule this meeting. "
            "Summarize what was attempted without blame. Suggest they coordinate directly or involve a manager."
        )
        user_prompt = (
            f"Participants: {', '.join(names)}\n"
            f"Meeting: {meeting_title}\n"
            f"Rounds attempted: {round_count}\n"
            f"Final arbitrator notes:\n{resolution}\n\n"
            "Write the escalation message."
        )
    else:
        system_prompt = (
            "You are a professional scheduling assistant. Write a clear, friendly message "
            "confirming the agreed meeting time to all participants."
        )
        user_prompt = (
            f"Participants: {', '.join(names)}\n"
            f"Meeting: {meeting_title}\n"
            f"Arbitration resolution:\n{resolution}\n\n"
            "Write a short confirmation message to send to all participants."
        )

    response = model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    return {
        **state,
        "agreed_slot": {**(state.get("agreed_slot") or {}), "resolution": resolution, "message": response.content},
        "messages": state["messages"] + [response],
    }
