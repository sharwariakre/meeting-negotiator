from langgraph.graph import StateGraph, END
from src.state import MeetingState
from src.agents.preference_agent import preference_agent
from src.agents.arbitrator_agent import arbitrator_agent
from src.agents.communication_agent import communication_agent


def should_continue(state: MeetingState) -> str:
    status = state.get("status", "negotiating")
    round_num = state.get("negotiation_round", 0)

    if status == "agreed" or round_num >= 3:
        return "communicate"
    if status == "failed":
        return END
    return "arbitrate"


def build_graph() -> StateGraph:
    workflow = StateGraph(MeetingState)

    workflow.add_node("preferences", preference_agent)
    workflow.add_node("arbitrate", arbitrator_agent)
    workflow.add_node("communicate", communication_agent)

    workflow.set_entry_point("preferences")

    workflow.add_conditional_edges(
        "preferences",
        should_continue,
        {
            "arbitrate": "arbitrate",
            "communicate": "communicate",
            END: END,
        },
    )

    workflow.add_conditional_edges(
        "arbitrate",
        should_continue,
        {
            "arbitrate": "arbitrate",
            "communicate": "communicate",
            END: END,
        },
    )

    workflow.add_edge("communicate", END)

    return workflow.compile()
