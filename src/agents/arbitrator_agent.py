import os
import re
from collections import defaultdict
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from src.state import MeetingState

_CONSENSUS_MARKER = "CONSENSUS: YES"


# ---------------------------------------------------------------------------
# Deterministic overlap detection
# ---------------------------------------------------------------------------

_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

# "Monday 9-11am"  → trailing period applies to both hours
_PATTERN_TRAILING = re.compile(r'^(\w+)\s+(\d+)-(\d+)(am|pm)$', re.IGNORECASE)
# "Friday 10am-12pm" → explicit period on each hour
_PATTERN_EXPLICIT = re.compile(r'^(\w+)\s+(\d+)(am|pm)-(\d+)(am|pm)$', re.IGNORECASE)


def _to_24h(hour: int, period: str) -> int:
    period = period.lower()
    if period == "am":
        return 0 if hour == 12 else hour
    else:  # pm
        return hour if hour == 12 else hour + 12


def _parse_window(text: str) -> Optional[tuple[str, int, int]]:
    """Return (day_lower, start_24h, end_24h) or None if unparseable."""
    text = text.strip()

    m = _PATTERN_EXPLICIT.match(text)
    if m:
        day = m.group(1).lower()
        if day in _DAYS:
            return day, _to_24h(int(m.group(2)), m.group(3)), _to_24h(int(m.group(4)), m.group(5))

    m = _PATTERN_TRAILING.match(text)
    if m:
        day = m.group(1).lower()
        if day in _DAYS:
            period = m.group(4)
            return day, _to_24h(int(m.group(2)), period), _to_24h(int(m.group(3)), period)

    return None


def _fmt_hour(h: int) -> str:
    if h == 0:
        return "12am"
    if h == 12:
        return "12pm"
    return f"{h}am" if h < 12 else f"{h - 12}pm"


def compute_overlaps(participants: list[dict], required_minutes: int) -> list[dict]:
    """
    Parse raw availability from participant profiles and return every window
    where ALL participants are free for at least `required_minutes`.
    Works with any number of participants.
    """
    # Build per-participant map: day → [(start, end), ...]
    per_participant: list[dict[str, list[tuple[int, int]]]] = []
    for p in participants:
        by_day: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for raw in p.get("availability", []):
            parsed = _parse_window(raw)
            if parsed:
                day, start, end = parsed
                by_day[day].append((start, end))
        per_participant.append(dict(by_day))

    required_hours = required_minutes / 60
    results: list[dict] = []

    # Only check days where every participant has at least one window
    all_days = set(per_participant[0].keys()) if per_participant else set()
    for pp in per_participant[1:]:
        all_days &= set(pp.keys())

    for day in sorted(all_days):
        # Start with first participant's windows, intersect with each next
        intervals: list[tuple[int, int]] = per_participant[0][day]
        for pp in per_participant[1:]:
            merged: list[tuple[int, int]] = []
            for s1, e1 in intervals:
                for s2, e2 in pp[day]:
                    start, end = max(s1, s2), min(e1, e2)
                    if (end - start) >= required_hours:
                        merged.append((start, end))
            intervals = merged

        for start, end in intervals:
            results.append({
                "day": day.capitalize(),
                "start": start,
                "end": end,
                "label": f"{day.capitalize()} {_fmt_hour(start)}–{_fmt_hour(end)}",
                "duration_minutes": int((end - start) * 60),
            })

    return results


# ---------------------------------------------------------------------------
# Arbitrator agent
# ---------------------------------------------------------------------------

def arbitrator_agent(state: MeetingState) -> MeetingState:
    """
    1. Deterministically computes verified overlap windows from raw profiles.
    2. Hands ground-truth slots to the LLM, which picks the best one (or
       issues a counteroffer if no overlap exists — but cannot invent slots).
    """
    model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3"))

    proposal_a = state.get("proposal_a") or {}
    proposal_b = state.get("proposal_b") or {}
    meeting = state["meeting_request"]
    participants = state["participants"]
    round_count = state.get("round_count", 0) + 1

    # --- Deterministic step ---
    verified_overlaps = compute_overlaps(participants, meeting["required_duration_minutes"])

    def format_proposal(p: dict) -> str:
        if not p:
            return "No proposal received."
        return (
            f"Participant: {p.get('name')} | Role: {p.get('role')} | "
            f"Seniority: {p.get('seniority')} | Round: {p.get('round', 0)}\n"
            f"Proposed slots:\n{p.get('slots', 'None')}"
        )

    def format_participant_context(p: dict) -> str:
        prefs = p.get("preferences", {})
        return (
            f"{p['name']} ({p['role']}, {p['seniority']}): "
            f"prefers {', '.join(prefs.get('preferred_times', []))}; "
            f"constraints: {', '.join(prefs.get('constraints', []))}"
        )

    participant_context = "\n".join(format_participant_context(p) for p in participants)

    if verified_overlaps:
        overlap_block = "\n".join(
            f"  • {s['label']} ({s['duration_minutes']} min available)"
            for s in verified_overlaps
        )
        senior = next((p for p in participants if p.get("seniority") == "senior"), None)
        senior_name = senior["name"] if senior else "the most senior participant"
        senior_prefs = (
            ", ".join(senior["preferences"].get("preferred_times", [])) if senior else "morning"
        )
        system_prompt = (
            "You are a meeting arbitrator. Verified overlapping availability has been "
            "computed deterministically from participant calendars — these slots are ground truth. "
            "You MUST choose from the verified list only. Do not suggest any slot not on it.\n\n"
            "Slot selection priority:\n"
            f"1. SENIORITY (highest weight): {senior_name} is the most senior participant. "
            f"Their preferred times ({senior_prefs}) take precedence when multiple valid slots exist. "
            "Choose the slot that best matches the senior participant's preferences first.\n"
            "2. MUTUAL FIT (tiebreaker): if two slots are equally good for the senior participant, "
            "prefer the one that also works better for the other participant.\n\n"
            "Output exactly 'CONSENSUS: YES' on its own line, then name the chosen slot and "
            "explain in 2–3 sentences — lead with why it satisfies the senior participant's "
            "preferences, then note how it accommodates the other participant."
        )
        user_prompt = (
            f"Meeting: {meeting['title']} ({meeting['required_duration_minutes']} min)\n"
            f"Arbitration round: {round_count}\n\n"
            f"VERIFIED OVERLAPPING SLOTS (ground truth):\n{overlap_block}\n\n"
            f"Participant preferences:\n{participant_context}\n\n"
            f"--- What each participant proposed ---\n"
            f"Proposal A:\n{format_proposal(proposal_a)}\n\n"
            f"Proposal B:\n{format_proposal(proposal_b)}\n\n"
            "Choose the best verified slot. Output 'CONSENSUS: YES' first."
        )
    else:
        system_prompt = (
            "You are a neutral meeting arbitrator. A deterministic calendar check has confirmed "
            "there are NO overlapping availability windows between participants right now. "
            "You cannot invent or suggest a slot that is not in someone's availability. "
            "Instead, issue a counteroffer: identify who has more flexibility (based on role, "
            "seniority, and context), specify which existing availability window they should "
            "treat as negotiable, and explain why. Keep it under 5 sentences. "
            "Output exactly 'CONSENSUS: NO' on its own line first."
        )
        user_prompt = (
            f"Meeting: {meeting['title']} ({meeting['required_duration_minutes']} min)\n"
            f"Arbitration round: {round_count}\n\n"
            "VERIFIED OVERLAP: None — no common windows exist in current availability.\n\n"
            f"Participant availability and preferences:\n{participant_context}\n\n"
            f"--- What each participant proposed ---\n"
            f"Proposal A:\n{format_proposal(proposal_a)}\n\n"
            f"Proposal B:\n{format_proposal(proposal_b)}\n\n"
            "Issue a counteroffer. Output 'CONSENSUS: NO' first."
        )

    response = model.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    content = response.content
    consensus_reached = _CONSENSUS_MARKER in content

    if consensus_reached:
        # Best-effort: find the overlap whose day name appears first in the LLM response
        chosen_slot = next(
            (o for o in verified_overlaps if o["day"].lower() in content.lower()),
            verified_overlaps[0] if verified_overlaps else None,
        )
        return {
            **state,
            "round_count": round_count,
            "agreed_slot": {
                "resolution": content,
                "verified_overlaps": verified_overlaps,
                "chosen_slot": chosen_slot,
            },
            "counteroffer_reasoning": None,
            "status": "consensus",
            "messages": state["messages"] + [response],
        }

    if round_count >= 3:
        escalation = (
            f"After {round_count} rounds, no consensus was reached. "
            f"Verified overlapping slots at time of escalation: "
            f"{[s['label'] for s in verified_overlaps] or 'none'}.\n\n"
            f"Final arbitrator assessment:\n{content}"
        )
        return {
            **state,
            "round_count": round_count,
            "agreed_slot": {"resolution": escalation},
            "counteroffer_reasoning": content,
            "status": "escalated",
            "messages": state["messages"] + [response],
        }

    return {
        **state,
        "round_count": round_count,
        "counteroffer_reasoning": content,
        "status": "negotiating",
        "messages": state["messages"] + [response],
    }
