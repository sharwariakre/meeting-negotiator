import os
from datetime import datetime, timedelta
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState


def _fmt_time(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "am" if dt.hour < 12 else "pm"
    if dt.minute == 0:
        return f"{hour}{suffix}"
    return f"{hour}:{dt.minute:02d}{suffix}"


def communication_agent(state: MeetingState) -> MeetingState:
    """Drafts the final participant-facing message for consensus or escalation outcomes."""
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    status = state.get("status", "consensus")
    agreed_slot = state.get("agreed_slot") or {}
    resolution = agreed_slot.get("resolution", "No resolution available.")
    names = [p["name"] for p in state.get("participants", [])]
    meeting_request = state.get("meeting_request", {})
    meeting_title = meeting_request.get("title", "the meeting")
    duration_minutes = meeting_request.get("required_duration_minutes", 60)
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
        chosen = agreed_slot.get("chosen_slot") or {}
        start_h = chosen.get("start")
        date_str = chosen.get("date")

        if start_h is not None and date_str:
            start_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=start_h)
            end_dt = start_dt + timedelta(minutes=duration_minutes)
            date_label = f"{start_dt.strftime('%A, %B')} {start_dt.day}"
            time_range = f"{_fmt_time(start_dt)} to {_fmt_time(end_dt)}"
            system_prompt = (
                "You are a professional scheduling assistant. "
                f"The meeting is confirmed for {date_label} from {time_range}. "
                "Do not change or invent these times. Use them exactly as written. "
                "Write a short, friendly confirmation message to all participants."
            )
            user_prompt = (
                f"Participants: {', '.join(names)}\n"
                f"Meeting: {meeting_title} ({duration_minutes} min)\n\n"
                "Write the confirmation using the exact date and time from the system prompt."
            )
        else:
            system_prompt = (
                "You are a professional scheduling assistant. Write a clear, friendly message "
                "confirming the agreed meeting time to all participants."
            )
            user_prompt = (
                f"Participants: {', '.join(names)}\n"
                f"Meeting: {meeting_title} ({duration_minutes} min)\n"
                f"Arbitration resolution:\n{resolution}\n\n"
                "Write a short confirmation message to send to all participants."
            )

    response = model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    return {
        **state,
        "agreed_slot": {**agreed_slot, "resolution": resolution, "message": response.content},
        "messages": state["messages"] + [response],
    }
