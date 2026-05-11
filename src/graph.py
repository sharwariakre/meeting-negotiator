from langgraph.graph import StateGraph, END
from src.state import MeetingState
from src.agents.preference_agent import make_preference_agent
from src.agents.arbitrator_agent import arbitrator_agent
from src.agents.communication_agent import communication_agent


def _route_after_arbitration(state: MeetingState) -> str:
    status = state.get("status")
    if status == "consensus":
        return "communicate"
    if status == "escalated":
        return "communicate"
    # "negotiating" — loop back for another round
    return "preferences_a"


def build_graph() -> StateGraph:
    workflow = StateGraph(MeetingState)

    workflow.add_node("preferences_a", make_preference_agent("A"))
    workflow.add_node("preferences_b", make_preference_agent("B"))
    workflow.add_node("arbitrate", arbitrator_agent)
    workflow.add_node("communicate", communication_agent)

    workflow.set_entry_point("preferences_a")

    # Each round: A proposes → B proposes → arbitrate
    workflow.add_edge("preferences_a", "preferences_b")
    workflow.add_edge("preferences_b", "arbitrate")

    # After arbitration: consensus or escalated → communicate; still negotiating → loop
    workflow.add_conditional_edges(
        "arbitrate",
        _route_after_arbitration,
        {
            "communicate": "communicate",
            "preferences_a": "preferences_a",
        },
    )

    workflow.add_edge("communicate", END)

    return workflow.compile()
