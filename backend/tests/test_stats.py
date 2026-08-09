import datetime as dt


def _future_workday(min_days_ahead=20):
    d = dt.date.today()
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and (d - dt.date.today()).days >= min_days_ahead:
            return d.isoformat()


def test_stats_requires_auth(client):
    assert client.get("/admin/api/stats/overview").status_code == 401


def test_stats_reflects_real_data(logged_in_client, client):
    date = _future_workday()
    client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "name": "Stats Test", "email": "statstest@example.com",
        "phone": "", "service": "Consulting", "notes": "",
    })

    resp = logged_in_client.get("/admin/api/stats/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body["leads_total"] >= 1
    assert body["appointments_total"] >= 1
    assert body["appointments_upcoming"] >= 1
    # "upcoming_appointments" is a top-5 preview ordered soonest-first —
    # other tests in this suite book plenty of earlier appointments, so
    # this one may not make the preview cut. Check the lead preview
    # instead, since leads are ordered by most-recently-created.
    assert any(l["email"] == "statstest@example.com" for l in body["recent_leads"])


def test_stats_counts_by_status(logged_in_client, client):
    resp = logged_in_client.get("/admin/api/stats/overview")
    body = resp.json()
    assert isinstance(body["leads_by_status"], dict)
    assert isinstance(body["appointments_by_status"], dict)
    assert sum(body["leads_by_status"].values()) == body["leads_total"]
    assert sum(body["appointments_by_status"].values()) == body["appointments_total"]
