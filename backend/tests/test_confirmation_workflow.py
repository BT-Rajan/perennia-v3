"""Pass 10 — confirmation workflow. A Service with
requires_confirmation=True produces a "pending" appointment instead of
an immediately "confirmed" one; an admin then accepts or declines it.
See docs/CALENDAR_MODULE_PLAN.md and PASS10_NOTES.md."""
import datetime as dt

import pytest

from app.settings_service import set_setting
from app.db import session_scope


@pytest.fixture(autouse=True)
def _widen_booking_window():
    """This file's dates start at nth-workday 100 to stay clear of
    every other booking-related test file's date window (see
    PASS9_NOTES.md for the collision class this avoids), which pushes
    some dates past the default 30-day booking.max_days_ahead."""
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 365, actor_id=None, actor_username="test-setup")
    yield
    with session_scope() as db:
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
    body = {"name": "Confirmation Test Service", "duration_minutes": 30, "requires_confirmation": True, **overrides}
    return logged_in_client.post("/admin/api/services", json=body).json()


VALID_APPT = {"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-0100"}


def _book(client, date, service_id, slot="09:00"):
    return client.post("/api/booking/appointments", json={
        "date": date, "slot": slot, "service_id": service_id, **VALID_APPT,
    })


# ── Creation ─────────────────────────────────────────────────────────

def test_confirmation_required_service_creates_pending(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(100)
    resp = _book(client, date, svc["id"])
    body = resp.json()
    assert body["ok"] is True
    assert body["pending"] is True
    assert body["appointment"]["status"] == "pending"
    assert body["appointment"]["confirmed_at"] is None


def test_non_confirmation_service_unaffected(logged_in_client, client):
    svc = _create_service(logged_in_client, requires_confirmation=False)
    date = _nth_future_workday(101)
    resp = _book(client, date, svc["id"])
    body = resp.json()
    assert body["pending"] is False
    assert body["appointment"]["status"] == "confirmed"


def test_appointment_without_service_unaffected(client):
    date = _nth_future_workday(102)
    resp = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    body = resp.json()
    assert body["pending"] is False
    assert body["appointment"]["status"] == "confirmed"


def test_pending_appointment_holds_its_slot(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(103)
    first = _book(client, date, svc["id"])
    assert first.json()["ok"] is True

    second = _book(client, date, svc["id"])
    assert second.json() == {"ok": False, "error": "slot_unavailable"}


# ── Admin accept ─────────────────────────────────────────────────────

def test_admin_accept_confirms_and_stamps_confirmed_at(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(104)
    created = _book(client, date, svc["id"]).json()["appointment"]

    resp = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/accept")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["appointment"]["status"] == "confirmed"
    assert body["appointment"]["confirmed_at"] is not None


def test_accept_non_pending_appointment_rejected(logged_in_client, client):
    svc = _create_service(logged_in_client, requires_confirmation=False)
    date = _nth_future_workday(105)
    created = _book(client, date, svc["id"]).json()["appointment"]  # already confirmed

    resp = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/accept")
    assert resp.status_code == 409


def test_double_accept_is_rejected_not_silently_repeated(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(106)
    created = _book(client, date, svc["id"]).json()["appointment"]

    first = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/accept")
    assert first.status_code == 200
    second = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/accept")
    assert second.status_code == 409


def test_accept_unknown_appointment_404(logged_in_client):
    resp = logged_in_client.post("/admin/api/booking/appointments/PRN-DOESNOTEXIST/accept")
    assert resp.status_code == 404


def test_accept_requires_auth(client):
    resp = client.post("/admin/api/booking/appointments/PRN-XXXXXXXX/accept")
    assert resp.status_code == 401


# ── Admin reject ─────────────────────────────────────────────────────

def test_admin_reject_cancels_with_reason_in_notes(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(107)
    created = _book(client, date, svc["id"]).json()["appointment"]

    resp = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/reject",
                                  json={"reason": "fully booked that week"})
    assert resp.status_code == 200
    body = resp.json()["appointment"]
    assert body["status"] == "cancelled"
    assert body["notes"].startswith("[declined] fully booked that week")


def test_admin_reject_without_reason(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(108)
    created = _book(client, date, svc["id"]).json()["appointment"]

    resp = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/reject", json={})
    assert resp.status_code == 200
    assert resp.json()["appointment"]["notes"] == "[declined]"


def test_reject_non_pending_appointment_rejected(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(109)
    created = _book(client, date, svc["id"]).json()["appointment"]
    logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/reject", json={})  # now cancelled

    again = logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/reject", json={})
    assert again.status_code == 409


def test_reject_unknown_appointment_404(logged_in_client):
    resp = logged_in_client.post("/admin/api/booking/appointments/PRN-DOESNOTEXIST/reject", json={})
    assert resp.status_code == 404


def test_rejecting_frees_the_slot(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(110)
    created = _book(client, date, svc["id"]).json()["appointment"]

    logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/reject", json={})
    second = _book(client, date, svc["id"])
    assert second.json()["ok"] is True


# ── Self-service on pending rows ─────────────────────────────────────

def test_self_service_cancel_works_on_pending(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(111)
    created = _book(client, date, svc["id"]).json()["appointment"]

    resp = client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert resp.status_code == 200
    assert resp.json()["appointment"]["status"] == "cancelled"


def test_self_service_reschedule_works_on_pending_and_stays_pending(logged_in_client, client):
    svc = _create_service(logged_in_client)
    date = _nth_future_workday(112)
    created = _book(client, date, svc["id"]).json()["appointment"]

    new_date = _nth_future_workday(113)
    resp = client.post("/api/booking/appointments/reschedule", json={
        "id": created["id"], "email": VALID_APPT["email"], "date": new_date, "time": "10:00",
    })
    assert resp.status_code == 200
    body = resp.json()["appointment"]
    assert body["status"] == "pending"  # reschedule doesn't itself confirm it
    assert body["date"] == new_date
    assert body["time"] == "10:00"


# ── Admin listing ────────────────────────────────────────────────────

def test_admin_list_filters_to_pending_only(logged_in_client, client):
    pending_svc = _create_service(logged_in_client, name="Needs Approval")
    auto_svc = _create_service(logged_in_client, name="Auto Confirms", requires_confirmation=False)
    date = _nth_future_workday(114)

    pending_appt = _book(client, date, pending_svc["id"], slot="09:00").json()["appointment"]
    _book(client, date, auto_svc["id"], slot="11:00")

    resp = logged_in_client.get(f"/admin/api/booking/appointments?date_from={date}&date_to={date}&status_filter=pending")
    ids = [a["id"] for a in resp.json()]
    assert pending_appt["id"] in ids
    assert all(a["status"] == "pending" for a in resp.json())
