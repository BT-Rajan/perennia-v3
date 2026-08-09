import datetime as dt


def _future_workday(min_days_ahead=3):
    d = dt.date.today()
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and (d - dt.date.today()).days >= min_days_ahead:
            return d.isoformat()


def test_booking_captures_a_lead(logged_in_client, client):
    date = _future_workday(min_days_ahead=4)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "name": "Lead Test", "email": "leadtest@example.com",
        "phone": "555-0199", "service": "Consulting", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    assert any(l["email"] == "leadtest@example.com" and l["name"] == "Lead Test" for l in leads)


def test_repeated_touches_consolidate_into_one_lead(logged_in_client, client):
    date = _future_workday(min_days_ahead=5)
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
    date = _future_workday(min_days_ahead=6)
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
    date = _future_workday(min_days_ahead=6)
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "10:30", "name": "Bad Status", "email": "badstatus@example.com",
        "phone": "", "service": "", "notes": "",
    })
    leads = logged_in_client.get("/admin/api/leads?source=booking").json()
    lead_id = next(l["id"] for l in leads if l["email"] == "badstatus@example.com")

    resp = logged_in_client.patch(f"/admin/api/leads/{lead_id}", json={"status": "not_a_real_status"})
    assert resp.status_code == 400


def test_admin_lead_delete(logged_in_client, client):
    date = _future_workday(min_days_ahead=6)
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
    date = _future_workday(min_days_ahead=6)
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
