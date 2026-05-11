from typing import TypedDict, Annotated, List, Optional
from langgraph.graph.message import add_messages


class MeetingState(TypedDict):
    messages: Annotated[list, add_messages]
    participants: List[dict]
    meeting_request: dict
    extracted_preferences: Optional[dict]
    proposed_slots: Optional[List[dict]]
    agreed_slot: Optional[dict]
    negotiation_round: int
    status: str  # "collecting", "negotiating", "agreed", "failed"
