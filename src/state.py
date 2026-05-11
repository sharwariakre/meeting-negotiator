from typing import TypedDict, Annotated, List, Optional, Literal
from langgraph.graph.message import add_messages


class MeetingState(TypedDict):
    messages: Annotated[list, add_messages]
    participants: List[dict]
    meeting_request: dict
    proposal_a: Optional[dict]
    proposal_b: Optional[dict]
    agreed_slot: Optional[dict]
    round_count: int
    counteroffer_reasoning: Optional[str]
    status: Literal["negotiating", "consensus", "escalated"]
