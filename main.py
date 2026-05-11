import argparse
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from src.graph import build_graph
from src.state import MeetingState

load_dotenv()


def load_profiles(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def _fetch_calendar_availability(data: dict) -> dict:
    """Replaces each participant's availability with live Google Calendar data."""
    from src.calendar_client import GoogleCalendarClient

    search_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    search_end = search_start + timedelta(days=7)
    required = data["meeting"]["required_duration_minutes"]

    for participant in data["participants"]:
        pid = participant["id"].lower()
        token_path = f"token_{participant['name'].lower()}.json"

        print(f"Authenticating {participant['name']} ({token_path})...")
        client = GoogleCalendarClient(token_path)

        slots = client.get_free_slots("primary", search_start, search_end, required)
        if not slots:
            print(f"  Warning: no free slots found for {participant['name']} in the next 7 days.")
        else:
            print(f"  Found {len(slots)} free slot(s) for {participant['name']}.")

        participant["availability"] = slots
        participant["_client"] = client  # stash for event creation

    data["_search_start"] = search_start
    return data


def _create_calendar_event(data: dict, result: dict) -> None:
    """Creates the agreed event on all participants' calendars."""
    agreed = result.get("agreed_slot", {})
    chosen = agreed.get("chosen_slot")
    if not chosen:
        print("No chosen_slot in agreed_slot — skipping calendar event creation.")
        return

    slot_label = chosen["label"]
    search_from = data["_search_start"]
    title = data["meeting"]["title"]
    attendee_emails = [p["email"] for p in data["participants"] if "email" in p]

    # Use the first participant's client to create the event (invited as organiser)
    client = data["participants"][0].get("_client")
    if not client:
        print("No calendar client available — skipping event creation.")
        return

    print(f"\nCreating calendar event: {title} — {slot_label}")
    try:
        link = client.create_event(
            calendar_id="primary",
            title=title,
            slot_label=slot_label,
            attendee_emails=attendee_emails,
            search_from=search_from,
        )
        print(f"Event created: {link}")
    except Exception as e:
        print(f"Failed to create event: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", default="data/profiles.json")
    parser.add_argument(
        "--use-calendar",
        action="store_true",
        help="Fetch real availability from Google Calendar instead of profiles.json",
    )
    args = parser.parse_args()

    data = load_profiles(args.profiles)

    if args.use_calendar:
        data = _fetch_calendar_availability(data)

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

    print(f"\nStarting meeting negotiation for: {data['meeting']['title']}")
    print("-" * 50)

    result = graph.invoke(initial_state)

    print("\n=== Negotiation Complete ===")
    print(f"Status: {result['status']}")
    print(f"Rounds: {result['round_count']}")

    if result.get("agreed_slot"):
        label = "Confirmation" if result["status"] == "consensus" else "Escalation Notice"
        print(f"\n--- {label} ---")
        print(result["agreed_slot"].get("message", "No message generated."))

    if args.use_calendar and result["status"] == "consensus":
        _create_calendar_event(data, result)


if __name__ == "__main__":
    main()
