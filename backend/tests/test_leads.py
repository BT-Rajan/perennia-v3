import datetime as dt

import pytest

from app.db import session_scope
from app.settings_service import set_setting


@pytest.fixture(autouse=True)
def _widen_booking_window():
    """This file's dates start at nth-workday 200 to stay clear of
    every other booking-related test file's date window. Also fixes a
    real, date-dependent bug found in this file: the old
    `_future_workday(min_days_ahead=N)` helper picked dates by raw day
    offset, which can alias two different N values onto the exact same
    calendar date whenever a weekend falls between them (e.g. N=4, 5,
    and 6 all landing on the same following Monday) — several tests in
    this file used to collide on both date *and* the same 09:00 slot as
    a result, intermittently, depending on which weekday "today"
    happened to be when the suite ran. See PASS9_NOTES.md for the same
    bug class caught earlier in this project's own new test files."""
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


def test_booking_captures_a_lead(logged_in_client, client):
    date = _nth_future_workday(200)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "name": "Lead Test", "email": "leadtest@example.com",
        "phone": "555-0199", "service": "Consulting", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    assert any(l["email"] == "leadtest@example.com" and l["name"] == "Lead Test" for l in leads)


def test_repeated_touches_consolidate_into_one_lead(logged_in_client, client):
    date = _nth_future_workday(201)
    client.post("/api/chat", json={
        "message": "hi, I'm interested — reach me at consolidated@example.com", "lang": "en", "history": [],
    })
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "name": "Consolidated Person", "email": "consolidated@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads").json()
    matches = [l for l in leads if l["email"] == "consolidated@example.com"]
    assert len(matches) == 1
    lead = matches[0]
    assert lead["name"] == "Consolidated Person"  # booking's name filled in what chat didn't have
    assert len(lead["transcript"]) == 2  # one entry from chat, one from booking


def test_admin_lead_update_status_and_notes(logged_in_client, client):
    date = _nth_future_workday(202)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:00", "name": "Update Me", "email": "updateme@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    lead_id = next(l["id"] for l in leads if l["email"] == "updateme@example.com")

    resp = logged_in_client.patch(f"/admin/api/leads/{lead_id}", json={"status": "contacted", "notes": "Called, left voicemail"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "contacted"
    assert resp.json()["notes"] == "Called, left voicemail"


def test_admin_lead_update_invalid_status_rejected(logged_in_client, client):
    date = _nth_future_workday(203)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:30", "name": "Bad Status", "email": "badstatus@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    lead_id = next(l["id"] for l in leads if l["email"] == "badstatus@example.com")

    resp = logged_in_client.patch(f"/admin/api/leads/{lead_id}", json={"status": "not_a_real_status"})
    assert resp.status_code == 400


def test_admin_lead_delete(logged_in_client, client):
    date = _nth_future_workday(204)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "11:00", "name": "Delete Me", "email": "deleteme@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    lead_id = next(l["id"] for l in leads if l["email"] == "deleteme@example.com")

    resp = logged_in_client.delete(f"/admin/api/leads/{lead_id}")
    assert resp.status_code == 200
    assert logged_in_client.get(f"/admin/api/leads/{lead_id}").status_code == 404


def test_leads_require_auth(client):
    assert client.get("/admin/api/leads").status_code == 401


def test_leads_filter_by_status(logged_in_client, client):
    date = _nth_future_workday(205)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "11:30", "name": "Status Filter", "email": "statusfilter@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    lead_id = next(l["id"] for l in leads if l["email"] == "statusfilter@example.com")
    logged_in_client.patch(f"/admin/api/leads/{lead_id}", json={"status": "qualified"})

    qualified = logged_in_client.get("/admin/api/leads?status_filter=qualified").json()
    assert any(l["id"] == lead_id for l in qualified)
    new_only = logged_in_client.get("/admin/api/leads?status_filter=new").json()
    assert not any(l["id"] == lead_id for l in new_only)
