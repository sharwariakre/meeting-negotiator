import asyncio
import json
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

load_dotenv()

# Allow OAuth over plain HTTP in local development
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]
CREDENTIALS_PATH = "credentials.json"
CALLBACK_BASE = "http://localhost:8000/auth/callback"
FRONTEND_URL = "http://localhost:3000"

_pending_flows: dict = {}


class NegotiateRequest(BaseModel):
    participant_a_email: str
    participant_b_email: str
    meeting_title: str
    duration_minutes: int = 60


def _token_path(participant: str) -> str:
    return f"token_{participant}.json"


def _is_authenticated(participant: str) -> bool:
    from google.oauth2.credentials import Credentials

    path = _token_path(participant)
    if not os.path.exists(path):
        return False
    try:
        creds = Credentials.from_authorized_user_file(path, SCOPES)
        return creds.valid or bool(creds.expired and creds.refresh_token)
    except Exception:
        return False


@app.get("/auth/status")
async def auth_status():
    return {
        "alice_authenticated": _is_authenticated("alice"),
        "bob_authenticated": _is_authenticated("bob"),
    }


@app.get("/auth/{participant}")
async def start_auth(participant: str):
    if participant not in ("alice", "bob"):
        raise HTTPException(status_code=400, detail="participant must be 'alice' or 'bob'")
    if not os.path.exists(CREDENTIALS_PATH):
        raise HTTPException(status_code=500, detail="credentials.json not found in project root")

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri=f"{CALLBACK_BASE}/{participant}",
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    _pending_flows[participant] = flow
    return {"auth_url": auth_url}


@app.get("/auth/callback/{participant}")
async def auth_callback(participant: str, request: Request):
    if participant not in _pending_flows:
        raise HTTPException(status_code=400, detail="No pending auth flow — start auth again")

    flow = _pending_flows.pop(participant)
    try:
        flow.fetch_token(authorization_response=str(request.url))
        with open(_token_path(participant), "w") as f:
            f.write(flow.credentials.to_json())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auth failed: {e}")

    return RedirectResponse(url=f"{FRONTEND_URL}?auth=success")


def _negotiate_sync(req: NegotiateRequest) -> dict:
    from src.calendar_client import GoogleCalendarClient
    from src.graph import build_graph
    from src.state import MeetingState

    with open("data/profiles.json") as f:
        data = json.load(f)

    email_map = {"A": req.participant_a_email, "B": req.participant_b_email}
    for p in data["participants"]:
        p["email"] = email_map.get(p["id"], p["email"])
    data["meeting"]["title"] = req.meeting_title
    data["meeting"]["required_duration_minutes"] = req.duration_minutes

    search_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    search_end = search_start + timedelta(days=7)

    clients: dict = {}
    state_participants = []
    for participant in data["participants"]:
        token = _token_path(participant["name"].lower())
        if not os.path.exists(token):
            raise ValueError(
                f"{participant['name']} is not authenticated — connect their calendar first."
            )
        client = GoogleCalendarClient(token)
        slots = client.get_free_slots("primary", search_start, search_end, req.duration_minutes)
        clients[participant["id"]] = client
        state_participants.append({**participant, "availability": slots})

    initial_state: MeetingState = {
        "messages": [],
        "participants": state_participants,
        "meeting_request": data["meeting"],
        "proposal_a": None,
        "proposal_b": None,
        "agreed_slot": None,
        "round_count": 0,
        "counteroffer_reasoning": None,
        "status": "negotiating",
    }

    result = build_graph().invoke(initial_state)

    agreed = result.get("agreed_slot") or {}
    chosen = agreed.get("chosen_slot")
    event_link = ""

    if result["status"] == "consensus" and chosen:
        client = clients.get("A")
        if client:
            try:
                event_link = client.create_event(
                    calendar_id="primary",
                    title=req.meeting_title,
                    slot_label=chosen.get("label", ""),
                    attendee_emails=[p["email"] for p in state_participants],
                    search_from=search_start,
                    duration_minutes=req.duration_minutes,
                    slot_date=chosen.get("date"),
                    slot_start_hour=chosen.get("start"),
                )
            except Exception as e:
                event_link = f"error: {e}"

    return {
        "status": result["status"],
        "rounds": result["round_count"],
        "agreed_slot": chosen,
        "confirmation_message": agreed.get("message", ""),
        "event_link": event_link,
    }


@app.post("/negotiate")
async def negotiate(req: NegotiateRequest):
    try:
        return await asyncio.to_thread(_negotiate_sync, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
