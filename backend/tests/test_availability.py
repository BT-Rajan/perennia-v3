"""Pass 9 — real AvailabilityRule model replacing the global
booking.workdays/day_start_hour/day_end_hour settings.
See docs/CALENDAR_MODULE_PLAN.md."""
import datetime as dt

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models import AvailabilityRule
from app.settings_service import set_setting


@pytest.fixture(autouse=True)
def _clear_availability_rules_after_test():
    """Every other test file in this suite relies on "no AvailabilityRule
    exists" to get the legacy booking.* settings fallback
    (booking_service.py). This file is the only one that creates rules,
    so it's responsible for leaving none behind — deleting straight
    from the DB (not via the HTTP API) so this cleanup never depends on
    auth state or interferes with the auth-behavior tests below.

    This file's dates deliberately live far out (see
    _nth_future_workday usage below, offset well clear of
    test_booking_services_integration.py's own date window) so a
    booking another test file made on a shared date can never collide
    with one made here, regardless of execution order — which is
    exactly the kind of cross-file collision that surfaced during
    Pass 9 work and is documented in PASS9_NOTES.md. That means every
    date here needs booking.max_days_ahead widened for the duration of
    this file."""
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 365, actor_id=None, actor_username="test-setup")
    yield
    with session_scope() as db:
        db.execute(delete(AvailabilityRule))
        set_setting(db, "booking.max_days_ahead", 30, actor_id=None, actor_username="test-teardown")


def _nth_future_workday(n: int) -> str:
    d = dt.date.today()
    found = 0
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            found += 1
            if found == n:
                return d.isoformat()


def _create_service(logged_in_client, **overrides):
    body = {"name": "Availability Test Service", "duration_minutes": 30, **overrides}
    return logged_in_client.post("/admin/api/services", json=body).json()


def _weekday_of(date_str: str) -> int:
    return dt.date.fromisoformat(date_str).weekday()


def _clear_weekly_rules(logged_in_client, service_id, weekday):
    """Weekly rules key off weekday, not date, and weekdays repeat
    every 5 calls to _nth_future_workday — so two tests picking
    different dates can still land on the same weekday and collide
    over a shared session-scoped test database. Each test that's about
    to assert something about a specific (service_id, weekday) clears
    whatever weekly rules already exist there first, making it
    self-contained regardless of what ran before it or what order
    tests execute in."""
    qs = f"?service_id={service_id}" if service_id else ""
    existing = logged_in_client.get(f"/admin/api/availability/rules{qs}").json()
    for r in existing:
        if r["kind"] == "weekly" and r["weekday"] == weekday:
            logged_in_client.delete(f"/admin/api/availability/rules/{r['id']}")


# ── Legacy fallback (no rules configured at all) ────────────────────

def test_legacy_fallback_matches_settings_when_no_rules_exist(client):
    date = _nth_future_workday(51)
    resp = client.get(f"/api/booking/slots?date={date}")
    slots = resp.json()["slots"]
    assert slots[0] == "09:00"
    assert slots[-1] == "16:30"
    assert len(slots) == 16


def test_effective_endpoint_reports_legacy_source_when_no_rules(logged_in_client):
    date = _nth_future_workday(51)
    resp = logged_in_client.get(f"/admin/api/availability/effective?date={date}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "legacy_settings"
    assert body["is_closed"] is False
    assert body["ranges"] == [{"start": "09:00", "end": "17:00"}]


# ── Weekly rules ─────────────────────────────────────────────────────

def test_create_weekly_rule_requires_auth(client):
    resp = client.post("/admin/api/availability/rules", json={"kind": "weekly", "weekday": 0,
                                                                "start_time": "09:00", "end_time": "17:00"})
    assert resp.status_code == 401


def test_business_wide_weekly_rule_switches_off_legacy_fallback(logged_in_client, client):
    date = _nth_future_workday(52)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "10:00", "end_time": "12:00",
    })
    resp = client.get(f"/api/booking/slots?date={date}")
    slots = resp.json()["slots"]
    assert slots == ["10:00", "10:30", "11:00", "11:30"]


def test_overlapping_weekly_rules_rejected(logged_in_client):
    _clear_weekly_rules(logged_in_client, None, 0)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": 0, "start_time": "09:00", "end_time": "12:00",
    })
    resp = logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": 0, "start_time": "11:00", "end_time": "13:00",
    })
    assert resp.status_code == 409


def test_split_day_two_non_overlapping_weekly_rules(logged_in_client, client):
    date = _nth_future_workday(53)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "09:00", "end_time": "12:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "13:00", "end_time": "15:00",
    })
    slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert "11:30" in slots
    assert "12:00" not in slots  # gap between the two ranges
    assert "12:30" not in slots
    assert "13:00" in slots
    assert "14:30" in slots
    assert "15:00" not in slots  # would end at 15:30, past this range's close


def test_weekly_rule_end_before_start_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": 1, "start_time": "12:00", "end_time": "09:00",
    })
    assert resp.status_code == 400


def test_weekly_rule_missing_weekday_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "start_time": "09:00", "end_time": "17:00",
    })
    assert resp.status_code == 400


# ── Date overrides ───────────────────────────────────────────────────

def test_date_override_closure_suppresses_otherwise_open_weekday(logged_in_client, client):
    date = _nth_future_workday(54)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "date_override", "date": date, "is_closed": True,
    })
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.json()["slots"] == []


def test_date_override_extended_hours_wins_over_weekly(logged_in_client, client):
    date = _nth_future_workday(55)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "date_override", "date": date, "start_time": "08:00", "end_time": "10:00",
    })
    slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert slots == ["08:00", "08:30", "09:00", "09:30"]


def test_date_override_missing_date_rejected(logged_in_client):
    resp = logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "date_override", "start_time": "09:00", "end_time": "17:00",
    })
    assert resp.status_code == 400


# ── Per-service overrides ────────────────────────────────────────────

def test_service_specific_weekly_overrides_business_wide(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(56)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)

    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "service_id": svc["id"], "kind": "weekly", "weekday": weekday,
        "start_time": "14:00", "end_time": "16:00",
    })

    generic_slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    service_slots = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}").json()["slots"]
    assert generic_slots[0] == "09:00"
    assert service_slots == ["14:00", "14:30", "15:00", "15:30"]


def test_service_specific_date_override_wins_over_everything(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(57)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)

    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "service_id": svc["id"], "kind": "weekly", "weekday": weekday,
        "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "service_id": svc["id"], "kind": "date_override", "date": date, "is_closed": True,
    })

    service_slots = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}").json()["slots"]
    assert service_slots == []
    # business-wide (no service_id) is untouched by the service-specific override
    generic_slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert generic_slots[0] == "09:00"


def test_service_with_no_rules_falls_back_to_business_wide(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(58)
    weekday = _weekday_of(date)
    _clear_weekly_rules(logged_in_client, None, weekday)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": weekday, "start_time": "10:00", "end_time": "11:00",
    })
    slots = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}").json()["slots"]
    assert slots == ["10:00", "10:30"]


# ── CRUD lifecycle ───────────────────────────────────────────────────

def test_update_and_delete_rule(logged_in_client):
    _clear_weekly_rules(logged_in_client, None, 2)
    created = logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": 2, "start_time": "09:00", "end_time": "17:00",
    }).json()

    updated = logged_in_client.patch(f"/admin/api/availability/rules/{created['id']}",
                                      json={"start_time": "08:00"})
    assert updated.status_code == 200
    assert updated.json()["start_time"] == "08:00"

    deleted = logged_in_client.delete(f"/admin/api/availability/rules/{created['id']}")
    assert deleted.status_code == 200
    again = logged_in_client.delete(f"/admin/api/availability/rules/{created['id']}")
    assert again.status_code == 404


def test_update_unknown_rule_404(logged_in_client):
    resp = logged_in_client.patch("/admin/api/availability/rules/not-real", json={"start_time": "08:00"})
    assert resp.status_code == 404


def test_list_rules_filters_by_service(logged_in_client):
    svc = _create_service(logged_in_client)
    _clear_weekly_rules(logged_in_client, None, 3)
    logged_in_client.post("/admin/api/availability/rules", json={
        "kind": "weekly", "weekday": 3, "start_time": "09:00", "end_time": "17:00",
    })
    logged_in_client.post("/admin/api/availability/rules", json={
        "service_id": svc["id"], "kind": "weekly", "weekday": 3, "start_time": "09:00", "end_time": "17:00",
    })

    business_wide = logged_in_client.get("/admin/api/availability/rules").json()
    service_specific = logged_in_client.get(f"/admin/api/availability/rules?service_id={svc['id']}").json()
    assert all(r["service_id"] is None for r in business_wide)
    assert all(r["service_id"] == svc["id"] for r in service_specific)


def test_create_rule_for_unknown_service_404(logged_in_client):
    resp = logged_in_client.post("/admin/api/availability/rules", json={
        "service_id": "does-not-exist", "kind": "weekly", "weekday": 0,
        "start_time": "09:00", "end_time": "17:00",
    })
    assert resp.status_code == 404


# ── DST-adjacent robustness ──────────────────────────────────────────
# US Eastern DST: springs forward on the second Sunday of March
# (02:00 -> 03:00 doesn't exist that day), falls back on the first
# Sunday of November (01:00-02:00 occurs twice). Computed relative to
# "today" rather than hardcoded so the test stays valid regardless of
# which year it runs in. These don't assert exact clock-shift semantics
# (zoneinfo handles the imaginary/ambiguous hour without our code
# needing to know) — the bar is that slot generation neither crashes
# nor silently duplicates a slot across the fold.

def _next_us_dst_start(after: dt.date) -> dt.date:
    def second_sunday_march(year: int) -> dt.date:
        d = dt.date(year, 3, 1)
        sundays = [d + dt.timedelta(days=i) for i in range(31)
                   if (d + dt.timedelta(days=i)).month == 3 and (d + dt.timedelta(days=i)).weekday() == 6]
        return sundays[1]
    candidate = second_sunday_march(after.year)
    return candidate if candidate > after else second_sunday_march(after.year + 1)


def _next_us_dst_end(after: dt.date) -> dt.date:
    def first_sunday_november(year: int) -> dt.date:
        d = dt.date(year, 11, 1)
        while d.weekday() != 6:
            d += dt.timedelta(days=1)
        return d
    candidate = first_sunday_november(after.year)
    return candidate if candidate > after else first_sunday_november(after.year + 1)


def test_slot_generation_survives_spring_forward_gap(logged_in_client, client):
    logged_in_client.put("/admin/api/settings/booking", json={"booking.timezone": "America/New_York"})
    logged_in_client.put("/admin/api/settings/booking", json={"booking.max_days_ahead": 365})
    try:
        spring_forward = _next_us_dst_start(dt.date.today()).isoformat()
        weekday = _weekday_of(spring_forward)
        _clear_weekly_rules(logged_in_client, None, weekday)
        logged_in_client.post("/admin/api/availability/rules", json={
            "kind": "weekly", "weekday": weekday, "start_time": "01:00", "end_time": "04:00",
        })
        resp = client.get(f"/api/booking/slots?date={spring_forward}")
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        assert len(slots) == len(set(slots))  # no duplicates
    finally:
        logged_in_client.put("/admin/api/settings/booking", json={"booking.timezone": "Asia/Kuwait"})
        logged_in_client.put("/admin/api/settings/booking", json={"booking.max_days_ahead": 30})
        _clear_weekly_rules(logged_in_client, None, weekday)


def test_slot_generation_survives_fall_back_duplicate_hour(logged_in_client, client):
    logged_in_client.put("/admin/api/settings/booking", json={"booking.timezone": "America/New_York"})
    logged_in_client.put("/admin/api/settings/booking", json={"booking.max_days_ahead": 365})
    try:
        fall_back = _next_us_dst_end(dt.date.today()).isoformat()
        weekday = _weekday_of(fall_back)
        _clear_weekly_rules(logged_in_client, None, weekday)
        logged_in_client.post("/admin/api/availability/rules", json={
            "kind": "weekly", "weekday": weekday, "start_time": "00:00", "end_time": "03:00",
        })
        resp = client.get(f"/api/booking/slots?date={fall_back}")
        assert resp.status_code == 200
        slots = resp.json()["slots"]
        # Exactly one grid entry per half-hour label, not two, even
        # though the underlying local clock repeats 01:00-02:00.
        assert len(slots) == len(set(slots))
    finally:
        logged_in_client.put("/admin/api/settings/booking", json={"booking.timezone": "Asia/Kuwait"})
        logged_in_client.put("/admin/api/settings/booking", json={"booking.max_days_ahead": 30})
        _clear_weekly_rules(logged_in_client, None, weekday)
