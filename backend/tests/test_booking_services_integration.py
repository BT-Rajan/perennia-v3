"""Pass 8 — wiring the Service catalog into the public booking flow.
See docs/CALENDAR_MODULE_PLAN.md."""
import datetime as dt

import pytest

from app.db import session_scope
from app.settings_service import set_setting


@pytest.fixture(autouse=True)
def _widen_booking_window():
    """This file's dates start at nth-workday 15 (see
    _nth_future_workday below) specifically to stay clear of
    test_booking.py's own fixed dates (day-offsets 3, 4, and 10 -
    verified via reversed test-file-order runs during Pass 9 not to
    collide). That pushes some dates past the default 30-day
    booking.max_days_ahead, so it's widened for the duration of this
    file and restored after."""
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 90, actor_id=None, actor_username="test-setup")
    yield
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 30, actor_id=None, actor_username="test-teardown")


def _nth_future_workday(n: int) -> str:
    """The n-th weekday (Mon-Fri) strictly after today, n=1 being the
    very next one. Distinct n -> guaranteed-distinct dates, unlike
    picking by raw day-offset (a raw offset can alias onto the same
    next weekday as a neighboring offset whenever a weekend sits
    between them). Callers in this file start at n=15 (see
    _widen_booking_window above) to stay clear of test_booking.py's
    own dates regardless of which file happens to run first."""
    d = dt.date.today()
    found = 0
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            found += 1
            if found == n:
                return d.isoformat()


def _create_service(logged_in_client, **overrides):
    body = {"name": "Booking Integration Base Service", "duration_minutes": 30, **overrides}
    return logged_in_client.post("/admin/api/services", json=body).json()


VALID_APPT = {"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-0100"}


def test_public_services_lists_only_active(logged_in_client, client):
    active = _create_service(logged_in_client, name="Active One")
    inactive = _create_service(logged_in_client, name="Inactive One")
    logged_in_client.delete(f"/admin/api/services/{inactive['id']}")  # soft delete -> inactive

    resp = client.get("/api/booking/services")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_slots_without_service_id_unchanged_default_behavior(client):
    """No service_id at all -> byte-identical to pre-Pass-8 behavior."""
    date = _nth_future_workday(15)
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    slots = resp.json()["slots"]
    assert slots[0] == "09:00"
    assert slots[-1] == "16:30"
    assert len(slots) == 16


def test_slots_for_unknown_service_404(client):
    date = _nth_future_workday(15)
    resp = client.get(f"/api/booking/slots?date={date}&service_id=does-not-exist")
    assert resp.status_code == 404


def test_slots_for_inactive_service_404(logged_in_client, client):
    svc = _create_service(logged_in_client)
    logged_in_client.delete(f"/admin/api/services/{svc['id']}")
    date = _nth_future_workday(15)
    resp = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}")
    assert resp.status_code == 404


def test_longer_service_duration_produces_fewer_fitting_slots(logged_in_client, client):
    # 90-minute service on the default 9-17 grid: last slot must still
    # finish by 17:00, so 15:30 is the last valid start (ends 17:00);
    # 16:00/16:30 would run past closing and must be excluded.
    svc = _create_service(logged_in_client, name="Deep Dive", duration_minutes=90)
    date = _nth_future_workday(19)
    slots = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}").json()["slots"]
    assert "15:30" in slots
    assert "16:00" not in slots
    assert "16:30" not in slots


def test_service_with_buffer_blocks_adjacent_slots(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Buffered", duration_minutes=30,
                           buffer_before_minutes=15, buffer_after_minutes=15)
    date = _nth_future_workday(20)

    book = client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:00", "service_id": svc["id"], **VALID_APPT,
    })
    assert book.json()["ok"] is True

    slots = client.get(f"/api/booking/slots?date={date}&service_id={svc['id']}").json()["slots"]
    # 10:00-10:30 booked, +-15min buffer on each side blocks 09:30-10:45
    assert "09:30" not in slots
    assert "10:00" not in slots
    assert "10:30" not in slots
    # 09:00 (ends 09:30, cand_end with buffer 09:45) vs blocked (09:45,10:45) -> touches, not overlapping (09:45==09:45)
    assert "09:00" in slots
    assert "11:00" in slots


def test_two_services_different_durations_dont_falsely_collide(logged_in_client, client):
    short = _create_service(logged_in_client, name="Quick Chat", duration_minutes=15)
    long = _create_service(logged_in_client, name="Deep Dive", duration_minutes=60)
    date = _nth_future_workday(21)

    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": short["id"], **VALID_APPT,
    })
    # A 60-minute service starting at 09:30 doesn't overlap a 15-minute
    # booking that ended at 09:15.
    slots = client.get(f"/api/booking/slots?date={date}&service_id={long['id']}").json()["slots"]
    assert "09:30" in slots


def test_create_appointment_with_invalid_service_rejected(client):
    date = _nth_future_workday(15)
    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": "not-a-real-service", **VALID_APPT,
    })
    assert resp.json() == {"ok": False, "error": "invalid_service"}


def test_appointment_records_service_and_answers(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Consult")
    q = logged_in_client.post(f"/admin/api/services/{svc['id']}/questions",
                               json={"kind": "text", "label": "What's the issue?", "required": True}).json()
    date = _nth_future_workday(22)

    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"],
        "answers": [{"question_id": q["id"], "answer": "Leaky faucet"}], **VALID_APPT,
    })
    body = resp.json()
    assert body["ok"] is True
    assert body["appointment"]["service_id"] == svc["id"]
    assert body["appointment"]["service_name"] == "Consult"
    assert body["appointment"]["answers"] == [{"question_id": q["id"], "label": "What's the issue?", "answer": "Leaky faucet"}]


def test_missing_required_answer_rejected(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Consult")
    logged_in_client.post(f"/admin/api/services/{svc['id']}/questions",
                           json={"kind": "text", "label": "Required Q", "required": True})
    date = _nth_future_workday(23)

    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"], "answers": [], **VALID_APPT,
    })
    assert resp.json() == {"ok": False, "error": "missing_required_answer"}


def test_answer_to_unknown_question_rejected(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Consult")
    date = _nth_future_workday(24)

    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"],
        "answers": [{"question_id": "bogus-id", "answer": "x"}], **VALID_APPT,
    })
    assert resp.json() == {"ok": False, "error": "invalid_question"}


def test_appointment_without_service_id_still_works(client):
    """No service_id -> legacy free-text booking path, unaffected."""
    date = _nth_future_workday(25)
    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service": "General enquiry", **VALID_APPT,
    })
    body = resp.json()
    assert body["ok"] is True
    assert body["appointment"]["service_id"] is None
    assert body["appointment"]["service_name"] is None
    assert body["appointment"]["answers"] == []


def test_reschedule_keeps_original_service_slot_math(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Consult", duration_minutes=45)
    date = _nth_future_workday(26)
    created = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"], **VALID_APPT,
    }).json()

    new_date = _nth_future_workday(27)
    resp = client.post("/api/booking/appointments/reschedule", json={
        "id": created["id"], "email": VALID_APPT["email"], "date": new_date, "time": "10:00",
    })
    assert resp.json()["ok"] is True
    assert resp.json()["appointment"]["service_id"] == svc["id"]


def test_admin_appointment_list_includes_service_name(logged_in_client, client):
    svc = _create_service(logged_in_client, name="Consult")
    date = _nth_future_workday(28)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"], **VALID_APPT,
    })
    resp = logged_in_client.get(f"/admin/api/booking/appointments?date_from={date}&date_to={date}")
    assert any(a["service_name"] == "Consult" for a in resp.json())
