import json
import os
from dotenv import load_dotenv
from src.graph import build_graph
from src.state import MeetingState

load_dotenv()


def load_profiles(path: str = "data/profiles.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)


def main():
    data = load_profiles()

    initial_state: MeetingState = {
        "messages": [],
        "participants": data["participants"],
        "meeting_request": data["meeting"],
        "proposal_a": None,
        "proposal_b": None,
        "agreed_slot": None,
        "round_count": 0,
        "counteroffer_reasoning": None,
        "status": "negotiating",
    }

    graph = build_graph()

    print(f"Starting meeting negotiation for: {data['meeting']['title']}")
    print("-" * 50)

    result = graph.invoke(initial_state)

    print("\n=== Negotiation Complete ===")
    print(f"Status: {result['status']}")
    print(f"Rounds: {result['round_count']}")

    if result.get("agreed_slot"):
        label = "Confirmation" if result["status"] == "consensus" else "Escalation Notice"
        print(f"\n--- {label} ---")
        print(result["agreed_slot"].get("message", "No message generated."))


if __name__ == "__main__":
    main()
