import datetime as dt


def _future_workday(min_days_ahead=3, weekdays=(0, 1, 2, 3, 4)):
    """A date far enough ahead to clear the default 6-hour notice
    window regardless of what time tests happen to run, and that falls
    on a default working day (Mon-Fri) — deterministic across test runs
    without hardcoding an actual calendar date."""
    d = dt.date.today()
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() in weekdays and (d - dt.date.today()).days >= min_days_ahead:
            return d.isoformat()


def _next_weekend_date():
    d = dt.date.today()
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() >= 5:
            return d.isoformat()


VALID_APPT = {
    "name": "Jamie Rivera", "email": "jamie@example.com",
    "phone": "555-0100", "service": "Consulting", "notes": "First call",
}


def test_slots_default_hours_workdays(client):
    date = _future_workday()
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.status_code == 200
    slots = resp.json()["slots"]
    # 09:00 to 17:00 in 30-minute steps = 16 slots
    assert slots[0] == "09:00"
    assert slots[-1] == "16:30"
    assert len(slots) == 16


def test_slots_weekend_is_empty(client):
    date = _next_weekend_date()
    resp = client.get(f"/api/booking/slots?date={date}")
    assert resp.json()["slots"] == []


def test_slots_too_far_ahead_is_empty(client):
    far = (dt.date.today() + dt.timedelta(days=400)).isoformat()
    resp = client.get(f"/api/booking/slots?date={far}")
    assert resp.json()["slots"] == []


def test_slots_invalid_date_rejected(client):
    resp = client.get("/api/booking/slots?date=not-a-date")
    assert resp.status_code == 400


def test_create_appointment_success(client):
    date = _future_workday()
    resp = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["id"].startswith("PRN-")


def test_create_appointment_invalid_email(client):
    date = _future_workday()
    resp = client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:00", **{**VALID_APPT, "email": "not-an-email"},
    })
    assert resp.json()["ok"] is False
    assert resp.json()["error"] == "invalid_email"


def test_create_appointment_slot_becomes_unavailable(client):
    date = _future_workday()
    first = client.post("/api/booking/appointments", json={"date": date, "slot": "11:00", **VALID_APPT})
    assert first.json()["ok"] is True

    second = client.post("/api/booking/appointments", json={"date": date, "slot": "11:00", **VALID_APPT})
    assert second.json()["ok"] is False
    assert second.json()["error"] == "slot_unavailable"

    slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert "11:00" not in slots


def test_create_appointment_when_booking_disabled(logged_in_client, client):
    resp = logged_in_client.put("/admin/api/settings/features", json={"features.booking_enabled": False})
    assert resp.status_code == 200
    try:
        date = _future_workday()
        create = client.post("/api/booking/appointments", json={"date": date, "slot": "12:00", **VALID_APPT})
        assert create.json() == {"ok": False, "error": "booking_disabled"}
        assert client.get(f"/api/booking/slots?date={date}").json()["slots"] == []
    finally:
        logged_in_client.put("/admin/api/settings/features", json={"features.booking_enabled": True})


def test_lookup_appointment_success_and_wrong_email(client):
    date = _future_workday()
    created = client.post("/api/booking/appointments", json={"date": date, "slot": "13:00", **VALID_APPT}).json()

    ok = client.post("/api/booking/appointments/lookup", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert ok.json()["ok"] is True
    assert ok.json()["appointment"]["date"] == date

    wrong = client.post("/api/booking/appointments/lookup", json={"id": created["id"], "email": "someone@else.com"})
    assert wrong.json() == {"ok": False, "error": "not_found"}


def test_cancel_appointment_with_sufficient_notice(client):
    date = _future_workday()
    created = client.post("/api/booking/appointments", json={"date": date, "slot": "14:00", **VALID_APPT}).json()

    resp = client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert resp.json() == {"ok": True}

    # slot should be free again
    slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert "14:00" in slots


def test_cancel_appointment_is_idempotent(client):
    date = _future_workday()
    created = client.post("/api/booking/appointments", json={"date": date, "slot": "15:00", **VALID_APPT}).json()
    client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    again = client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert again.json() == {"ok": True}


def test_cancel_appointment_not_found(client):
    resp = client.post("/api/booking/appointments/cancel", json={"id": "PRN-NOTREAL1", "email": "x@x.com"})
    assert resp.json() == {"ok": False, "error": "not_found"}


def test_reschedule_appointment_success(client):
    date = _future_workday()
    created = client.post("/api/booking/appointments", json={"date": date, "slot": "09:30", **VALID_APPT}).json()

    new_date = _future_workday(min_days_ahead=4)
    resp = client.post("/api/booking/appointments/reschedule", json={
        "id": created["id"], "email": VALID_APPT["email"], "date": new_date, "time": "10:30",
    })
    assert resp.json()["ok"] is True
    assert resp.json()["appointment"]["date"] == new_date
    assert resp.json()["appointment"]["time"] == "10:30"

    # old slot freed, new slot taken
    assert "09:30" in client.get(f"/api/booking/slots?date={date}").json()["slots"]
    assert "10:30" not in client.get(f"/api/booking/slots?date={new_date}").json()["slots"]


def test_reschedule_to_taken_slot_rejected(client):
    date = _future_workday()
    a = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT}).json()
    b = client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:00", **{**VALID_APPT, "email": "someone-else@example.com"},
    }).json()

    resp = client.post("/api/booking/appointments/reschedule", json={
        "id": b["id"], "email": "someone-else@example.com", "date": date, "time": "09:00",
    })
    assert resp.json()["ok"] is False
    assert resp.json()["error"] == "slot_unavailable"


def test_admin_list_appointments_requires_auth(client):
    assert client.get("/admin/api/booking/appointments").status_code == 401


def test_admin_list_appointments(logged_in_client, client):
    date = _future_workday()
    client.post("/api/booking/appointments", json={"date": date, "slot": "16:00", **VALID_APPT})

    resp = logged_in_client.get(f"/admin/api/booking/appointments?date_from={date}&date_to={date}")
    assert resp.status_code == 200
    assert any(a["time"] == "16:00" for a in resp.json())


def test_admin_cancel_bypasses_notice_window(logged_in_client, client):
    """Directly exercises the service layer to simulate an imminent
    appointment (the public API itself won't let you book one inside
    the notice window), then confirms the admin override can still
    cancel it where a visitor's own request would be refused."""
    from app.db import session_scope
    from app.models import Appointment
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc)
    with session_scope() as db:
        appt = Appointment(
            id="PRN-IMMINENT", date=now.date().isoformat(), time=(now + _dt.timedelta(minutes=30)).strftime("%H:%M"),
            name="Urgent Case", email="urgent@example.com",
        )
        db.add(appt)

    # a visitor's own cancel would likely be refused for lack of notice;
    # the admin's is unconditional.
    resp = logged_in_client.post("/admin/api/booking/appointments/PRN-IMMINENT/cancel")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_admin_cancel_not_found(logged_in_client):
    resp = logged_in_client.post("/admin/api/booking/appointments/PRN-NOTREAL2/cancel")
    assert resp.status_code == 404


def test_booking_timezone_setting_is_validated(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/booking", json={"booking.timezone": "Not/A_Real_Zone"})
    assert resp.status_code == 400


def test_booking_workdays_setting_validates_range(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/booking", json={"booking.workdays": [0, 1, 9]})
    assert resp.status_code == 400


def test_booking_slot_minutes_out_of_range(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/booking", json={"booking.slot_minutes": 1})
    assert resp.status_code == 400


def test_changing_slot_length_changes_availability(logged_in_client, client):
    resp = logged_in_client.put("/admin/api/settings/booking", json={"booking.slot_minutes": 60})
    assert resp.status_code == 200
    try:
        # A date not touched by any other test in this file, so no
        # earlier booking's fine-grained slot collides with the new
        # hourly grid computed here.
        date = _future_workday(min_days_ahead=10)
        slots = client.get(f"/api/booking/slots?date={date}").json()["slots"]
        assert slots == ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00"]
    finally:
        logged_in_client.put("/admin/api/settings/booking", json={"booking.slot_minutes": 30})
