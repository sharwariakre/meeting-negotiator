import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.agents.arbitrator_agent import _parse_window

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _fmt_hour(h: int) -> str:
    if h == 0:
        return "12am"
    if h == 12:
        return "12pm"
    return f"{h}am" if h < 12 else f"{h - 12}pm"


class GoogleCalendarClient:
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events",
    ]

    def __init__(self, token_path: str, credentials_path: str = "credentials.json"):
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"'{self.credentials_path}' not found. Download it from Google Cloud "
                        "Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → "
                        "Download JSON and save it as 'credentials.json' in the project root."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.token_path, "w") as f:
                f.write(creds.to_json())

        return build("calendar", "v3", credentials=creds)

    def get_free_slots(
        self,
        calendar_id: str,
        start: datetime,
        end: datetime,
        required_duration_minutes: int,
        working_hours: tuple[int, int] = (9, 18),
    ) -> list[dict]:
        """
        Queries the freebusy API and returns free windows as dicts:
          {"label": "Tuesday May 19 9am-6pm", "date": "2026-05-19",
           "start": "09:00", "end": "18:00"}
        Only windows >= required_duration_minutes are returned.
        """
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": calendar_id}],
        }
        result = self.service.freebusy().query(body=body).execute()
        busy_raw = result["calendars"][calendar_id]["busy"]

        # Parse and localise busy intervals
        busy_intervals = [
            (
                datetime.fromisoformat(b["start"]).astimezone(),
                datetime.fromisoformat(b["end"]).astimezone(),
            )
            for b in busy_raw
        ]

        free_slots: list[dict] = []
        current = start.replace(hour=0, minute=0, second=0, microsecond=0)

        while current.date() < end.date():
            day_start = current.replace(hour=working_hours[0], minute=0, second=0, microsecond=0)
            day_end = current.replace(hour=working_hours[1], minute=0, second=0, microsecond=0)

            # Clip busy intervals to this day's working-hours window, then sort
            day_busy = sorted(
                (max(b_s, day_start), min(b_e, day_end))
                for b_s, b_e in busy_intervals
                if b_s < day_end and b_e > day_start
            )

            # Invert busy periods to get free windows
            free_windows = []
            cursor = day_start
            for b_s, b_e in day_busy:
                if b_s > cursor:
                    free_windows.append((cursor, b_s))
                cursor = max(cursor, b_e)
            if cursor < day_end:
                free_windows.append((cursor, day_end))

            for w_start, w_end in free_windows:
                # Snap to integer-hour boundaries (round start up, end down)
                start_hour = w_start.hour + (1 if w_start.minute > 0 else 0)
                end_hour = w_end.hour

                if (end_hour - start_hour) * 60 >= required_duration_minutes:
                    day_name = w_start.strftime("%A")
                    month_day = f"{w_start.strftime('%B')} {w_start.day}"
                    free_slots.append({
                        "label": f"{day_name} {month_day} {_fmt_hour(start_hour)}-{_fmt_hour(end_hour)}",
                        "date": w_start.strftime("%Y-%m-%d"),
                        "start": f"{start_hour:02d}:00",
                        "end": f"{end_hour:02d}:00",
                    })

            current += timedelta(days=1)

        return free_slots

    def create_event(
        self,
        calendar_id: str,
        title: str,
        slot_label: str,
        attendee_emails: list[str],
        search_from: datetime,
        duration_minutes: int,
        slot_date: str | None = None,
        slot_start_hour: int | None = None,
    ) -> str:
        """
        Creates a Google Calendar event with all attendees and returns the HTML link.
        Event duration is always exactly duration_minutes from the start of the free window.
        When slot_date/slot_start_hour are provided they are used directly;
        otherwise slot_label is parsed and the date is inferred from search_from.
        """
        if slot_date is not None and slot_start_hour is not None:
            event_date = datetime.strptime(slot_date, "%Y-%m-%d").date()
            start_hour = slot_start_hour
        else:
            # Normalise dashes — compute_overlaps labels use en-dash (–)
            normalised = slot_label.replace("–", "-").replace("—", "-")
            parsed = _parse_window(normalised)
            if not parsed:
                raise ValueError(f"Cannot parse slot label: {slot_label!r}")
            day_name, start_hour, _ = parsed
            # Find the first occurrence of that weekday on or after search_from
            target_wd = _WEEKDAYS.index(day_name)
            days_ahead = (target_wd - search_from.weekday()) % 7
            event_date = (search_from + timedelta(days=days_ahead)).date()

        tz = search_from.tzinfo
        event_start = datetime(event_date.year, event_date.month, event_date.day, start_hour, tzinfo=tz)
        event_end = event_start + timedelta(minutes=duration_minutes)

        body = {
            "summary": title,
            "start": {"dateTime": event_start.isoformat()},
            "end": {"dateTime": event_end.isoformat()},
            "attendees": [{"email": email} for email in attendee_emails],
        }

        event = (
            self.service.events()
            .insert(calendarId=calendar_id, body=body, sendUpdates="all")
            .execute()
        )
        return event.get("htmlLink", "")
