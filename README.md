# Meeting Negotiator

![Tests](https://github.com/sharwariakre/meeting-negotiator/actions/workflows/tests.yml/badge.svg)

A multi-agent LangGraph system that autonomously negotiates meeting times between participants, reasoning about seniority, preferences, and constraints the way a skilled executive assistant would.

---

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│  Preference Agent A │     │  Preference Agent B │
│  (advocates for A)  │     │  (advocates for B)  │
└────────┬────────────┘     └──────────┬──────────┘
         │                             │
         └──────────────┬──────────────┘
                        ▼
              ┌─────────────────┐
              │    Arbitrator   │◄──────────────────┐
              │  (deterministic │                   │
              │  overlap check  │                   │ no consensus
              │  + LLM flex     │                   │ (max 3 rounds)
              │  reasoning)     │                   │
              └────────┬────────┘                   │
                       │                            │
          ┌────────────┴────────────┐               │
          │ consensus?              │               │
         YES                       NO ─────────────┘
          │                        │
          │               round_count >= 3?
          │                       YES
          │                        │
          ▼                        ▼
 ┌─────────────────┐    ┌─────────────────────┐
 │  Communication  │    │  Communication      │
 │  Agent          │    │  Agent              │
 │  (confirmation) │    │  (escalation notice)│
 └─────────────────┘    └─────────────────────┘
```

What makes this genuinely multi-agent rather than a single LLM with a long prompt: each agent has a different principal it's loyal to. Preference agents have conflicting goals by design — Agent A is trying to get Alice a morning slot, Agent B is trying to get Bob an afternoon slot. The arbitrator is a third party with no stake in either outcome. Separating these concerns means the negotiation surface is real: agents push back, revise under pressure, and occasionally fail to agree.

---

## Agents

**Preference Agent** (`src/agents/preference_agent.py`)
Instantiated once per participant via a factory function (`make_preference_agent("A")`). Each instance reads only its participant's availability, preferred times, and constraints, then proposes up to 3 slots that work for that participant alone — no attempt at overlap. On subsequent rounds it receives the arbitrator's counteroffer reasoning and responds like a real advocate: conceding on low-priority constraints while holding firm on hard ones, explaining every decision.

**Arbitrator Agent** (`src/agents/arbitrator_agent.py`)
Runs a deterministic interval-intersection algorithm against the raw participant profiles before invoking the LLM. If verified overlapping windows exist, the LLM is shown them as ground truth and asked only to pick the best one — it cannot suggest a slot not on the list. If no overlap exists, the LLM reasons about who should flex based on seniority, role, and context, then issues a counteroffer that feeds back into the next preference round. After 3 failed rounds it sets `status = "escalated"`.

**Communication Agent** (`src/agents/communication_agent.py`)
Reads the final `status` from state and drafts the appropriate message: a short confirmation for consensus outcomes, or a professional escalation notice for failed negotiations that suggests direct coordination or manager involvement.

---

## Key design decisions

- **Deterministic overlap detection before LLM reasoning** — the arbitrator computes real interval intersections from raw profile data. The LLM is only allowed to choose from verified slots, preventing it from hallucinating availability that doesn't exist.
- **Seniority-based preference resolution** — when multiple valid overlapping slots exist, the arbitrator prompt explicitly prioritises the senior participant's preferred times. Seniority is read dynamically from the profile, not hardcoded.
- **Negotiation loop with counteroffer feedback** — each preference agent receives the arbitrator's reasoning on losing rounds and revises its proposal accordingly, simulating real advocacy under pressure.
- **Escalation path** — after 3 rounds without consensus, the system exits cleanly with a structured escalation message rather than looping indefinitely or forcing a bad slot.

---

## How to run

**Prerequisites**
- Python 3.10+
- [Ollama](https://ollama.com) running locally with a model pulled:
  ```bash
  ollama pull llama3.1:8b
  ```

**Install dependencies**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Run — default profiles (overlapping availability, resolves in 1 round)**
```bash
python3 main.py
```

**Run — conflict profiles (zero overlap, forces 3-round loop + escalation)**
```bash
python3 main.py --profiles data/profiles_conflict.json
```

**Swap in Anthropic API instead of Ollama**

Add to `.env`:
```
ANTHROPIC_API_KEY=your_key_here
```

Replace the model instantiation in each agent file:
```python
# before
from langchain_ollama import ChatOllama
model = ChatOllama(model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"))

# after
from langchain_anthropic import ChatAnthropic
model = ChatAnthropic(model="claude-sonnet-4-6")
```

Install the extra dependency:
```bash
pip install langchain-anthropic
```

---

## Sample output

**Consensus case** (`data/profiles.json`)

Alice and Bob have two verified overlapping windows: Monday 10am–11am and Wednesday 3pm–4pm. The arbitrator picks Monday morning because Alice is senior and prefers mornings.

```
Starting meeting negotiation for: Project Kickoff
--------------------------------------------------

=== Negotiation Complete ===
Status: consensus
Rounds: 1

--- Confirmation ---
Hello Alice and Bob,

We've confirmed our meeting for Monday from 10am-11am. We'll use this
time for our Project Kickoff discussion. If you have any questions,
feel free to reach out.

Looking forward to seeing you both then!
```

**Escalation case** (`data/profiles_conflict.json`)

Alice's availability (Tue/Thu morning, Fri morning) and Bob's availability (Mon/Wed afternoon, Thu evening) share no common windows. The loop runs 3 rounds; each time the deterministic check confirms zero overlap regardless of what the preference agents propose.

```
Starting meeting negotiation for: Project Kickoff
--------------------------------------------------

=== Negotiation Complete ===
Status: escalated
Rounds: 3

--- Escalation Notice ---
Subject: Meeting Schedule Escalation - Project Kickoff

Dear Alice and Bob,

We've reached a point where human intervention is necessary to schedule
the Project Kickoff meeting. After three rounds of negotiation, no
mutually agreeable time was found.

We recommend you coordinate directly or involve a manager to facilitate
further scheduling. Thursday afternoon was surfaced as a possible
candidate for manual consideration.

Best regards,
Scheduling Assistant
```

---

## Google Calendar integration

Real availability can be fetched directly from Google Calendar instead of using static `profiles.json` slots.

### Get credentials.json

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services** → **Library**
2. Enable the **Google Calendar API**
3. Go to **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
4. Application type: **Desktop app**
5. Download the JSON and save it as `credentials.json` in the project root

### Run with live calendar data

```bash
python3 main.py --use-calendar
```

On first run, a browser window opens **twice** — once for each participant account. Each person logs in and grants calendar access. Tokens are saved as `token_alice.json` and `token_bob.json` locally. Subsequent runs use the saved tokens and refresh them automatically.

After consensus, the agreed slot is written as a real calendar event and attendees receive invites.

### Token files

`credentials.json` and `token_*.json` are listed in `.gitignore` and must never be committed.

### What it does

- `get_free_slots` queries the freebusy API for the next 7 days within working hours (9am–6pm), inverts busy periods to find free windows, snaps to integer-hour boundaries, and returns strings in the same format as `profiles.json` so the rest of the pipeline is unchanged.
- `create_event` parses the agreed slot label back into a concrete datetime, anchors the day name to the actual upcoming date, and creates the event with all participants as attendees.

---

## Tech stack

| Component | Library |
|---|---|
| Agent orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM interface | [LangChain](https://github.com/langchain-ai/langchain) |
| Local model serving | [Ollama](https://ollama.com) via `langchain-ollama` |
| Model | Llama 3.1 8B (configurable via `OLLAMA_MODEL` in `.env`) |
| Language | Python 3.10+ |

---

## Project structure

```
meeting-negotiator/
├── main.py                        # entry point, --profiles / --use-calendar
├── credentials.json               # OAuth client secret (not committed)
├── token_alice.json               # saved token per account (not committed)
├── token_bob.json
├── data/
│   ├── profiles.json              # default: overlapping availability
│   └── profiles_conflict.json     # test: zero overlap, forces escalation
└── src/
    ├── state.py                   # MeetingState TypedDict
    ├── graph.py                   # LangGraph workflow definition
    ├── calendar_client.py         # Google Calendar OAuth + freebusy + event creation
    └── agents/
        ├── preference_agent.py    # per-participant advocate (factory)
        ├── arbitrator_agent.py    # deterministic overlap + LLM resolution
        └── communication_agent.py # confirmation or escalation message
```
