"""Pass 12 — external calendar sync (Google, opt-in). No live Google
account is used or required: every test monkeypatches
app.google_calendar_client's functions directly, matching the plan's
"integration test against a mocked Google client" requirement.
See docs/CALENDAR_MODULE_PLAN.md and PASS12_NOTES.md."""
import datetime as dt

import pytest

from app.db import session_scope
from app.models import CalendarCredential
from app.security import encrypt_secret
from app.settings_service import set_setting


@pytest.fixture(autouse=True)
def _widen_booking_window():
    """This file's dates start at nth-workday 250, clear of every other
    file's window (see PASS9_NOTES.md)."""
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 365, actor_id=None, actor_username="test-setup")
    yield
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 30, actor_id=None, actor_username="test-teardown")


@pytest.fixture(autouse=True)
def _clear_calendar_state_after_test():
    """Every real booking made anywhere in the suite would otherwise
    try to sync against a credential left behind by this file — same
    pollution class documented in PASS9_NOTES.md/PASS11_NOTES.md."""
    yield
    with session_scope() as db:
        db.query(CalendarCredential).delete()
        set_setting(db, "features.calendar_sync_enabled", False, actor_id=None, actor_username="test-teardown")
        set_setting(db, "booking.calendar_sync_fail_open", False, actor_id=None, actor_username="test-teardown")


def _nth_future_workday(n: int) -> str:
    d = dt.date.today()
    found = 0
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            found += 1
            if found == n:
                return d.isoformat()


def _enable_sync(logged_in_client=None):
    with session_scope() as db:
        set_setting(db, "features.calendar_sync_enabled", True, actor_id=None, actor_username="test-setup")


def _create_active_credential(calendar_id="primary@group.calendar.google.com", expires_in_future=True):
    with session_scope() as db:
        cred = CalendarCredential(
            provider="google",
            access_token=encrypt_secret("fake-access-token"),
            refresh_token=encrypt_secret("fake-refresh-token"),
            token_expires_at=dt.datetime.now(dt.timezone.utc) + (
                dt.timedelta(hours=1) if expires_in_future else -dt.timedelta(hours=1)
            ),
            calendar_id=calendar_id, is_active=True,
        )
        db.add(cred)
        db.flush()
        return cred.id


def _configure_oauth_client(logged_in_client, redirect_uri="https://example.com/admin/api/calendar-sync/callback"):
    resp = logged_in_client.put("/admin/api/settings/calendar_sync", json={
        "calendar_sync.google_client_id": "test-client-id",
        "calendar_sync.google_client_secret": "test-client-secret",
        "calendar_sync.google_redirect_uri": redirect_uri,
    })
    assert resp.status_code == 200, resp.text


VALID_APPT = {"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-0100"}


# ── OAuth connect flow ───────────────────────────────────────────────

def test_connect_requires_client_credentials_configured(logged_in_client):
    resp = logged_in_client.get("/admin/api/calendar-sync/connect", follow_redirects=False)
    assert resp.status_code == 400


def test_connect_redirects_to_google(logged_in_client):
    _configure_oauth_client(logged_in_client)
    resp = logged_in_client.get("/admin/api/calendar-sync/connect", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert resp.headers["location"].startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "state=" in resp.headers["location"]


def test_callback_invalid_state_rejected(logged_in_client):
    _configure_oauth_client(logged_in_client)
    resp = logged_in_client.get("/admin/api/calendar-sync/callback?code=abc&state=not-a-real-state")
    assert resp.status_code == 400


def test_full_connect_flow(logged_in_client, monkeypatch):
    _configure_oauth_client(logged_in_client)

    monkeypatch.setattr(
        "app.google_calendar_client.exchange_code",
        lambda **kw: {"access_token": "at-123", "refresh_token": "rt-456", "expires_in": 3600},
    )
    monkeypatch.setattr(
        "app.google_calendar_client.list_calendars",
        lambda access_token: [{"id": "primary", "summary": "Primary", "primary": True}],
    )

    connect = logged_in_client.get("/admin/api/calendar-sync/connect", follow_redirects=False)
    from urllib.parse import urlparse, parse_qs
    state = parse_qs(urlparse(connect.headers["location"]).query)["state"][0]

    callback = logged_in_client.get(f"/admin/api/calendar-sync/callback?code=abc123&state={state}")
    assert callback.status_code == 200, callback.text
    body = callback.json()
    assert body["calendars"] == [{"id": "primary", "summary": "Primary", "primary": True}]
    credential_id = body["credential_id"]

    status_before = logged_in_client.get("/admin/api/calendar-sync/status").json()
    assert status_before["connected"] is False  # calendar not chosen yet

    select = logged_in_client.post("/admin/api/calendar-sync/select", json={
        "credential_id": credential_id, "calendar_id": "primary",
    })
    assert select.status_code == 200

    status_after = logged_in_client.get("/admin/api/calendar-sync/status").json()
    assert status_after["connected"] is True
    assert status_after["calendar_id"] == "primary"


def test_callback_without_refresh_token_rejected(logged_in_client, monkeypatch):
    _configure_oauth_client(logged_in_client)
    monkeypatch.setattr(
        "app.google_calendar_client.exchange_code",
        lambda **kw: {"access_token": "at-only", "expires_in": 3600},  # no refresh_token
    )
    connect = logged_in_client.get("/admin/api/calendar-sync/connect", follow_redirects=False)
    from urllib.parse import urlparse, parse_qs
    state = parse_qs(urlparse(connect.headers["location"]).query)["state"][0]

    callback = logged_in_client.get(f"/admin/api/calendar-sync/callback?code=abc&state={state}")
    assert callback.status_code == 400


def test_disconnect_removes_credential_even_if_revoke_fails(logged_in_client, monkeypatch):
    monkeypatch.setattr("app.google_calendar_client.revoke_token", lambda token: False)
    _create_active_credential()

    resp = logged_in_client.post("/admin/api/calendar-sync/disconnect")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    status = logged_in_client.get("/admin/api/calendar-sync/status").json()
    assert status["connected"] is False


def test_disconnect_with_nothing_connected_404(logged_in_client):
    resp = logged_in_client.post("/admin/api/calendar-sync/disconnect")
    assert resp.status_code == 404


def test_calendar_sync_endpoints_require_auth(client):
    assert client.get("/admin/api/calendar-sync/status").status_code == 401


# ── Busy-time blocking in slot generation ───────────────────────────

def test_busy_block_removes_overlapping_slot_leaves_adjacent(logged_in_client, client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(250)

    def fake_busy(access_token, *, calendar_id, time_min, time_max):
        start = dt.datetime.combine(dt.date.fromisoformat(date), dt.time(10, 0), tzinfo=time_min.tzinfo)
        end = start + dt.timedelta(minutes=30)
        return [(start.isoformat(), end.isoformat())]

    monkeypatch.setattr("app.google_calendar_client.get_busy_times", fake_busy)

    slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert "10:00" not in slots
    assert "09:30" in slots
    assert "10:30" in slots


def test_sync_disabled_ignores_busy_times(client, monkeypatch):
    # features.calendar_sync_enabled defaults False - no credential even
    # configured, so get_busy_times must never be called.
    called = []
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: called.append(1) or [])
    date = _nth_future_workday(251)
    client.get(f"/api/booking/slots?date={date}")
    assert called == []


def test_fail_closed_default_returns_no_slots_on_api_failure(client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(252)

    def boom(*a, **k):
        from app.google_calendar_client import GoogleCalendarError
        raise GoogleCalendarError("simulated outage")

    monkeypatch.setattr("app.google_calendar_client.get_busy_times", boom)
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    assert resp.json()["slots"] == []  # safe default: can't confirm real availability


def test_fail_open_setting_ignores_api_failure(logged_in_client, client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    with session_scope() as db:
        set_setting(db, "booking.calendar_sync_fail_open", True, actor_id=None, actor_username="test")
    date = _nth_future_workday(253)

    def boom(*a, **k):
        from app.google_calendar_client import GoogleCalendarError
        raise GoogleCalendarError("simulated outage")

    monkeypatch.setattr("app.google_calendar_client.get_busy_times", boom)
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    assert len(resp.json()["slots"]) > 0  # ignored the failure, fell back to normal availability


def test_no_calendar_selected_yet_does_not_block_slots(client):
    """A credential can exist mid-connect (calendar_id not chosen,
    is_active False) - that must never be treated as 'connected'."""
    _enable_sync()
    _create_active_credential(calendar_id=None)
    with session_scope() as db:
        cred = db.query(CalendarCredential).first()
        cred.is_active = False
    date = _nth_future_workday(254)
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    assert len(resp.json()["slots"]) > 0


def test_expired_token_is_refreshed_before_freebusy_call(client, monkeypatch):
    _enable_sync()
    cred_id = _create_active_credential(expires_in_future=False)
    date = _nth_future_workday(255)

    refresh_calls = []
    busy_calls = []

    def fake_refresh(*, client_id, client_secret, refresh_token):
        refresh_calls.append(refresh_token)
        return {"access_token": "refreshed-access-token", "expires_in": 3600}

    def fake_busy(access_token, *, calendar_id, time_min, time_max):
        busy_calls.append(access_token)
        return []

    with session_scope() as db:
        set_setting(db, "calendar_sync.google_client_id", "cid", actor_id=None, actor_username="test")
        set_setting(db, "calendar_sync.google_client_secret", "csecret", actor_id=None, actor_username="test")

    monkeypatch.setattr("app.google_calendar_client.refresh_access_token", fake_refresh)
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", fake_busy)

    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    assert len(refresh_calls) == 1
    assert busy_calls == ["refreshed-access-token"]

    with session_scope() as db:
        cred = db.get(CalendarCredential, cred_id)
        expires_at = cred.token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=dt.timezone.utc)
        assert expires_at > dt.datetime.now(dt.timezone.utc)


# ── Event creation on confirm ────────────────────────────────────────

def test_event_created_on_confirmed_booking(client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(256)

    created = []
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: [])
    monkeypatch.setattr("app.google_calendar_client.create_event", lambda *a, **kw: created.append(kw) or "gcal-evt-1")

    resp = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    body = resp.json()
    assert body["ok"] is True
    assert body["appointment"]["external_event_id"] == "gcal-evt-1"
    assert len(created) == 1


def test_event_creation_failure_does_not_break_booking(client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(257)

    def boom(*a, **k):
        from app.google_calendar_client import GoogleCalendarError
        raise GoogleCalendarError("simulated failure")

    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: [])
    monkeypatch.setattr("app.google_calendar_client.create_event", boom)

    resp = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    body = resp.json()
    assert body["ok"] is True
    assert body["appointment"]["external_event_id"] is None


def test_event_created_only_on_confirmation_accept_not_on_pending_request(logged_in_client, client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    svc = logged_in_client.post("/admin/api/services", json={
        "name": "Sync Confirmation Service", "duration_minutes": 30, "requires_confirmation": True,
    }).json()
    date = _nth_future_workday(258)

    created = []
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: [])
    monkeypatch.setattr("app.google_calendar_client.create_event", lambda *a, **kw: created.append(kw) or "gcal-evt-2")

    booked = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"], **VALID_APPT,
    }).json()["appointment"]
    assert booked["external_event_id"] is None
    assert len(created) == 0  # pending - no event yet

    logged_in_client.post(f"/admin/api/booking/appointments/{booked['id']}/accept")
    assert len(created) == 1  # now confirmed


def test_event_deleted_on_self_service_cancel(client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(259)

    deleted = []
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: [])
    monkeypatch.setattr("app.google_calendar_client.create_event", lambda *a, **k: "gcal-evt-3")
    monkeypatch.setattr("app.google_calendar_client.delete_event", lambda *a, **kw: deleted.append(kw))

    created = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT}).json()

    resp = client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert resp.json()["ok"] is True
    assert len(deleted) == 1
    assert deleted[0]["event_id"] == "gcal-evt-3"


def test_event_recreated_on_reschedule(client, monkeypatch):
    _enable_sync()
    _create_active_credential()
    date = _nth_future_workday(260)
    new_date = _nth_future_workday(261)

    create_calls = []
    delete_calls = []
    monkeypatch.setattr("app.google_calendar_client.get_busy_times", lambda *a, **k: [])
    monkeypatch.setattr("app.google_calendar_client.create_event",
                         lambda *a, **kw: create_calls.append(kw) or f"gcal-evt-{len(create_calls)}")
    monkeypatch.setattr("app.google_calendar_client.delete_event", lambda *a, **kw: delete_calls.append(kw))

    created = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT}).json()
    assert created["appointment"]["external_event_id"] == "gcal-evt-1"

    resp = client.post("/api/booking/appointments/reschedule", json={
        "id": created["id"], "email": VALID_APPT["email"], "date": new_date, "time": "10:00",
    })
    body = resp.json()
    assert body["ok"] is True
    assert len(delete_calls) == 1
    assert delete_calls[0]["event_id"] == "gcal-evt-1"
    assert len(create_calls) == 2
    assert body["appointment"]["external_event_id"] == "gcal-evt-2"
