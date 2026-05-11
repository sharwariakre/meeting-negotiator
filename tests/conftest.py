import pytest


@pytest.fixture
def sample_participants():
    return [
        {
            "id": "A",
            "name": "Alice",
            "role": "Engineering Manager",
            "seniority": "senior",
            "context": "Leading the project.",
            "availability": ["Monday 9-11am", "Wednesday 2-4pm", "Friday 10am-12pm"],
            "preferences": {
                "preferred_duration_minutes": 60,
                "preferred_times": ["morning"],
                "constraints": ["no early mornings before 9am"],
            },
        },
        {
            "id": "B",
            "name": "Bob",
            "role": "Software Engineer",
            "seniority": "junior",
            "context": "New team member.",
            "availability": ["Monday 10am-12pm", "Tuesday 1-3pm", "Wednesday 3-5pm"],
            "preferences": {
                "preferred_duration_minutes": 45,
                "preferred_times": ["afternoon"],
                "constraints": ["no Fridays"],
            },
        },
    ]


@pytest.fixture
def conflict_participants():
    return [
        {
            "id": "A",
            "name": "Alice",
            "role": "Engineering Manager",
            "seniority": "senior",
            "context": "Leading the project.",
            "availability": ["Tuesday 9-11am", "Thursday 2-4pm", "Friday 9-11am"],
            "preferences": {
                "preferred_duration_minutes": 60,
                "preferred_times": ["morning"],
                "constraints": [],
            },
        },
        {
            "id": "B",
            "name": "Bob",
            "role": "Software Engineer",
            "seniority": "junior",
            "context": "New team member.",
            "availability": ["Monday 1-3pm", "Wednesday 3-5pm", "Thursday 5-7pm"],
            "preferences": {
                "preferred_duration_minutes": 45,
                "preferred_times": ["afternoon"],
                "constraints": [],
            },
        },
    ]


@pytest.fixture
def sample_meeting():
    return {
        "title": "Project Kickoff",
        "required_duration_minutes": 60,
        "required_participants": ["A", "B"],
    }


@pytest.fixture
def base_state(sample_participants, sample_meeting):
    return {
        "messages": [],
        "participants": sample_participants,
        "meeting_request": sample_meeting,
        "proposal_a": None,
        "proposal_b": None,
        "agreed_slot": None,
        "round_count": 0,
        "counteroffer_reasoning": None,
        "status": "negotiating",
    }


@pytest.fixture
def conflict_state(conflict_participants, sample_meeting):
    return {
        "messages": [],
        "participants": conflict_participants,
        "meeting_request": sample_meeting,
        "proposal_a": None,
        "proposal_b": None,
        "agreed_slot": None,
        "round_count": 0,
        "counteroffer_reasoning": None,
        "status": "negotiating",
    }
