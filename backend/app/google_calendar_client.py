"""
Thin client for Google's OAuth token endpoint and Calendar API.
Mirrors whatsapp_client.py's shape: plain httpx calls, no vendor SDK,
every function takes exactly what it needs as arguments rather than
reaching into settings/DB itself — that's calendar_sync_service.py's
job. Keeping this layer free of any app-specific state is what makes
it trivially mockable in tests (monkeypatch one function at a time,
no client object to construct).
"""
from __future__ import annotations

import datetime as dt

import httpx

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CALENDAR_LIST_URL = "https://www.googleapis.com/calendar/v3/users/me/calendarList"
FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"
EVENTS_URL_TEMPLATE = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events"
EVENT_URL_TEMPLATE = "https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events/{event_id}"

SCOPES = "https://www.googleapis.com/auth/calendar"
REQUEST_TIMEOUT_SECONDS = 15.0


class GoogleCalendarError(Exception):
    """Raised for any failure talking to Google — a timeout, a
    non-2xx response, a malformed reply. Callers (calendar_sync_service.py)
    decide what to do about it (fail-open vs fail-closed for slot
    generation, best-effort-and-swallow for event creation)."""


def build_auth_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPES, "access_type": "offline", "prompt": "consent", "state": state,
    }
    return f"{AUTH_BASE_URL}?{urlencode(params)}"


def _post_token(data: dict) -> dict:
    try:
        resp = httpx.post(TOKEN_URL, data=data, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        raise GoogleCalendarError(f"Token endpoint returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise GoogleCalendarError(f"Token endpoint request failed: {e}") from e


def exchange_code(*, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    """Returns {access_token, refresh_token, expires_in, ...} — Google
    only returns refresh_token on the *first* consent for a given
    account+scope, which is exactly why access_type=offline and
    prompt=consent are both set on the auth URL above."""
    return _post_token({
        "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri,
        "code": code, "grant_type": "authorization_code",
    })


def refresh_access_token(*, client_id: str, client_secret: str, refresh_token: str) -> dict:
    """Returns {access_token, expires_in, ...} — no new refresh_token
    is issued by this flow; the original one keeps working until
    revoked."""
    return _post_token({
        "client_id": client_id, "client_secret": client_secret,
        "refresh_token": refresh_token, "grant_type": "refresh_token",
    })


def revoke_token(token: str) -> bool:
    """Best-effort: returns False rather than raising on failure,
    since callers (calendar_sync_service.disconnect) must complete a
    local disconnect regardless of whether Google's side succeeds."""
    try:
        resp = httpx.post(REVOKE_URL, params={"token": token}, timeout=REQUEST_TIMEOUT_SECONDS)
        return resp.status_code < 300
    except httpx.HTTPError:
        return False


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def list_calendars(access_token: str) -> list[dict]:
    """Returns [{id, summary, primary}, ...]."""
    try:
        resp = httpx.get(CALENDAR_LIST_URL, headers=_auth_headers(access_token), timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except httpx.HTTPStatusError as e:
        raise GoogleCalendarError(f"Calendar list request returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise GoogleCalendarError(f"Calendar list request failed: {e}") from e
    return [{"id": c["id"], "summary": c.get("summary", c["id"]), "primary": c.get("primary", False)} for c in items]


def get_busy_times(access_token: str, *, calendar_id: str, time_min: dt.datetime, time_max: dt.datetime) -> list[tuple[str, str]]:
    """Returns [(start_iso, end_iso), ...] busy blocks on `calendar_id`
    within [time_min, time_max). One request regardless of how many
    candidate slots the caller will check against the result — see
    calendar_sync_service.busy_minutes_for_date, which calls this once
    per (date, calendar) rather than once per slot."""
    body = {
        "timeMin": time_min.isoformat(), "timeMax": time_max.isoformat(),
        "items": [{"id": calendar_id}],
    }
    try:
        resp = httpx.post(FREEBUSY_URL, headers=_auth_headers(access_token), json=body, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as e:
        raise GoogleCalendarError(f"Free/busy request returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise GoogleCalendarError(f"Free/busy request failed: {e}") from e

    calendars = data.get("calendars", {})
    entry = calendars.get(calendar_id, {})
    if entry.get("errors"):
        raise GoogleCalendarError(f"Free/busy API reported an error for {calendar_id!r}: {entry['errors']}")
    return [(b["start"], b["end"]) for b in entry.get("busy", [])]


def create_event(access_token: str, *, calendar_id: str, summary: str, description: str,
                  start_iso: str, end_iso: str, timezone: str) -> str:
    """Returns the created event's Google event id."""
    body = {
        "summary": summary, "description": description,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    try:
        resp = httpx.post(
            EVENTS_URL_TEMPLATE.format(calendar_id=calendar_id),
            headers=_auth_headers(access_token), json=body, timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()["id"]
    except httpx.HTTPStatusError as e:
        raise GoogleCalendarError(f"Event creation returned {e.response.status_code}") from e
    except httpx.HTTPError as e:
        raise GoogleCalendarError(f"Event creation request failed: {e}") from e


def delete_event(access_token: str, *, calendar_id: str, event_id: str) -> None:
    try:
        resp = httpx.delete(
            EVENT_URL_TEMPLATE.format(calendar_id=calendar_id, event_id=event_id),
            headers=_auth_headers(access_token), timeout=REQUEST_TIMEOUT_SECONDS,
        )
        # 404/410 mean the event is already gone on Google's side -
        # exactly the outcome we wanted, not a failure to report.
        if resp.status_code not in (204, 404, 410) and resp.status_code >= 300:
            raise GoogleCalendarError(f"Event deletion returned {resp.status_code}")
    except httpx.HTTPError as e:
        raise GoogleCalendarError(f"Event deletion request failed: {e}") from e
