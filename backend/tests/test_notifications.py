import datetime as dt


def _future_workday(min_days_ahead=3):
    d = dt.date.today()
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and (d - dt.date.today()).days >= min_days_ahead:
            return d.isoformat()


VALID_APPT = {"name": "Notify Test", "phone": "555-0177", "service": "Consulting", "notes": ""}


def _enable_email(logged_in_client, **overrides):
    payload = {
        "notifications.email_enabled": True,
        "notifications.smtp_host": "smtp.example.com",
        "notifications.smtp_port": 587,
        "notifications.smtp_username": "",
        "notifications.smtp_use_tls": True,
        "notifications.from_email": "noreply@example.com",
        "notifications.from_name": "Perennia Test",
        **overrides,
    }
    resp = logged_in_client.put("/admin/api/settings/notifications", json=payload)
    assert resp.status_code == 200, resp.text


def _disable_email(logged_in_client):
    logged_in_client.put("/admin/api/settings/notifications", json={"notifications.email_enabled": False})


# ── Low-level render/send unit tests ──────────────────────────────────

def test_render_fills_placeholders():
    from app.notification_service import render
    template = {"en": {"subject": "Hi {name}", "body": "Code: {id}"}}
    out = render(template, "en", name="Jamie", id="PRN-ABC12345", date="", time="", service="")
    assert out["subject"] == "Hi Jamie"
    assert out["body"] == "Code: PRN-ABC12345"


def test_render_falls_back_to_english_for_missing_language():
    from app.notification_service import render
    template = {"en": {"subject": "Hi {name}", "body": "ok"}}
    out = render(template, "fr", name="Jamie", id="", date="", time="", service="")
    assert out["subject"] == "Hi Jamie"


def test_send_email_noop_when_disabled(client, monkeypatch):
    calls = []
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: calls.append(1) or _FakeSMTP())
    from app.notification_service import send_email
    from app.db import session_scope
    with session_scope() as db:
        result = send_email(db, to_email="x@example.com", subject="s", body_text="b")
    assert result is False
    assert calls == []


class _FakeSMTP:
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def starttls(self):
        pass
    def login(self, u, p):
        pass
    def send_message(self, msg):
        pass


def test_send_email_sends_when_configured(logged_in_client, monkeypatch):
    sent = {}

    class FakeSMTP(_FakeSMTP):
        def __init__(self, host, port, timeout=None):
            sent["host"] = host
            sent["port"] = port
        def send_message(self, msg):
            sent["subject"] = msg["Subject"]
            sent["to"] = msg["To"]

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    _enable_email(logged_in_client)
    try:
        from app.notification_service import send_email
        from app.db import session_scope
        with session_scope() as db:
            result = send_email(db, to_email="recipient@example.com", subject="Test Subject", body_text="Body")
        assert result is True
        assert sent["host"] == "smtp.example.com"
        assert sent["to"] == "recipient@example.com"
        assert sent["subject"] == "Test Subject"
    finally:
        _disable_email(logged_in_client)


def test_send_email_returns_false_on_smtp_failure(logged_in_client, monkeypatch):
    import smtplib

    class FailingSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def __enter__(self):
            raise smtplib.SMTPConnectError(421, "connection refused")

    monkeypatch.setattr("smtplib.SMTP", FailingSMTP)
    _enable_email(logged_in_client)
    try:
        from app.notification_service import send_email
        from app.db import session_scope
        with session_scope() as db:
            result = send_email(db, to_email="x@example.com", subject="s", body_text="b")
        assert result is False  # never raises
    finally:
        _disable_email(logged_in_client)


def test_send_whatsapp_noop_when_disabled(client, monkeypatch):
    called = []
    monkeypatch.setattr("app.notification_service.whatsapp_client.send_message", lambda **kw: called.append(kw))
    from app.notification_service import send_whatsapp
    from app.db import session_scope
    with session_scope() as db:
        result = send_whatsapp(db, to_number="+15551234567", message="hi")
    assert result is False
    assert called == []


def test_send_whatsapp_sends_when_configured(logged_in_client, monkeypatch):
    called = []
    monkeypatch.setattr("app.notification_service.whatsapp_client.send_message", lambda **kw: called.append(kw))
    resp = logged_in_client.put("/admin/api/settings/notifications", json={
        "notifications.whatsapp_enabled": True, "notifications.whatsapp_provider": "twilio",
        "notifications.whatsapp_account_id": "ACxxxx", "notifications.whatsapp_api_key": "secrettoken",
        "notifications.whatsapp_from_number": "+15550000000",
    })
    assert resp.status_code == 200
    try:
        from app.notification_service import send_whatsapp
        from app.db import session_scope
        with session_scope() as db:
            result = send_whatsapp(db, to_number="+15551234567", message="Hello!")
        assert result is True
        assert called[0]["to_number"] == "+15551234567"
        assert called[0]["provider"] == "twilio"
    finally:
        logged_in_client.put("/admin/api/settings/notifications", json={"notifications.whatsapp_enabled": False})


# ── Booking trigger tests (via the real HTTP flow) ─────────────────────

def test_booking_confirmation_email_sent_when_enabled(logged_in_client, monkeypatch):
    sent = {}

    class FakeSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def send_message(self, msg):
            sent["subject"] = msg["Subject"]
            sent["to"] = msg["To"]

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    _enable_email(logged_in_client)
    try:
        date = _future_workday(min_days_ahead=11)
        resp = logged_in_client.post("/api/booking/appointments", json={
            "date": date, "slot": "09:00", "email": "confirmtest@example.com", "lang": "en", **VALID_APPT,
        })
        body = resp.json()
        assert body["ok"] is True
        assert sent["to"] == "confirmtest@example.com"
        assert body["id"] in sent["subject"]
    finally:
        _disable_email(logged_in_client)


def test_no_email_sent_when_notifications_disabled(logged_in_client, monkeypatch):
    calls = []
    monkeypatch.setattr("smtplib.SMTP", lambda *a, **k: calls.append(1))
    date = _future_workday(min_days_ahead=12)
    resp = logged_in_client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "email": "noemail@example.com", "lang": "en", **VALID_APPT,
    })
    assert resp.json()["ok"] is True
    assert calls == []  # notifications.email_enabled defaults to False


def test_admin_alert_sent_on_new_booking(logged_in_client, monkeypatch):
    sent = []

    class FakeSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def send_message(self, msg):
            sent.append(msg["To"])

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    _enable_email(logged_in_client, **{})
    logged_in_client.put("/admin/api/settings/notifications", json={"notifications.admin_alert_email": "staff@example.com"})
    try:
        date = _future_workday(min_days_ahead=13)
        logged_in_client.post("/api/booking/appointments", json={
            "date": date, "slot": "09:00", "email": "leadgen@example.com", "lang": "en", **VALID_APPT,
        })
        assert "staff@example.com" in sent  # admin alert
        assert "leadgen@example.com" in sent  # visitor confirmation
    finally:
        _disable_email(logged_in_client)
        logged_in_client.put("/admin/api/settings/notifications", json={"notifications.admin_alert_email": ""})


def test_cancellation_email_sent_and_not_duplicated_on_repeat_cancel(logged_in_client, monkeypatch):
    sent = []

    class FakeSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def send_message(self, msg):
            sent.append(msg["Subject"])

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    date = _future_workday(min_days_ahead=14)
    created = logged_in_client.post("/api/booking/appointments", json={
        "date": date, "slot": "11:00", "email": "canceltest@example.com", "lang": "en", **VALID_APPT,
    }).json()

    _enable_email(logged_in_client)
    try:
        r1 = logged_in_client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": "canceltest@example.com"})
        assert r1.json()["ok"] is True
        first_count = len(sent)
        assert first_count == 1

        # idempotent re-cancel must NOT send a second cancellation email
        r2 = logged_in_client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": "canceltest@example.com"})
        assert r2.json()["ok"] is True
        assert len(sent) == first_count
    finally:
        _disable_email(logged_in_client)


def test_reschedule_email_sent(logged_in_client, monkeypatch):
    sent = []

    class FakeSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def send_message(self, msg):
            sent.append(msg["Subject"])

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    date = _future_workday(min_days_ahead=15)
    created = logged_in_client.post("/api/booking/appointments", json={
        "date": date, "slot": "12:00", "email": "reschedtest@example.com", "lang": "en", **VALID_APPT,
    }).json()

    _enable_email(logged_in_client)
    try:
        new_date = _future_workday(min_days_ahead=16)
        resp = logged_in_client.post("/api/booking/appointments/reschedule", json={
            "id": created["id"], "email": "reschedtest@example.com", "date": new_date, "time": "10:00",
        })
        assert resp.json()["ok"] is True
        assert len(sent) == 1
    finally:
        _disable_email(logged_in_client)


def test_notification_failure_never_breaks_booking_response(logged_in_client, monkeypatch):
    """A malformed template (bad placeholder) must not turn a
    successful booking into a 500 or an ok:false."""
    def boom(*a, **k):
        raise ValueError("simulated smtp explosion")
    monkeypatch.setattr("smtplib.SMTP", boom)
    _enable_email(logged_in_client)
    try:
        date = _future_workday(min_days_ahead=17)
        resp = logged_in_client.post("/api/booking/appointments", json={
            "date": date, "slot": "09:00", "email": "resilient@example.com", "lang": "en", **VALID_APPT,
        })
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        _disable_email(logged_in_client)


# ── Lead alert tests ─────────────────────────────────────────────────

def test_admin_alert_on_new_chat_lead_only_once(logged_in_client, client, monkeypatch):
    sent = []

    class FakeSMTP(_FakeSMTP):
        def __init__(self, *a, **k):
            pass
        def send_message(self, msg):
            sent.append(msg["Subject"])

    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)
    _enable_email(logged_in_client)
    logged_in_client.put("/admin/api/settings/notifications", json={"notifications.admin_alert_email": "staff2@example.com"})
    try:
        client.post("/api/chat", json={"message": "reach me at newlead@example.com please", "lang": "en", "history": []})
        assert len(sent) == 1

        # a second message from the SAME lead must not alert again
        client.post("/api/chat", json={"message": "following up, still newlead@example.com", "lang": "en", "history": []})
        assert len(sent) == 1
    finally:
        _disable_email(logged_in_client)
        logged_in_client.put("/admin/api/settings/notifications", json={"notifications.admin_alert_email": ""})


# ── Settings validation ────────────────────────────────────────────

def test_smtp_port_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/notifications", json={"notifications.smtp_port": 99999})
    assert resp.status_code == 400


def test_whatsapp_provider_enum_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/notifications", json={"notifications.whatsapp_provider": "carrier_pigeon"})
    assert resp.status_code == 400


def test_smtp_password_never_exposed(logged_in_client, client):
    logged_in_client.put("/admin/api/settings/notifications", json={"notifications.smtp_password": "hunter2"})
    try:
        public = client.get("/api/config/public").json()
        assert "notifications.smtp_password" not in public
        admin_all = logged_in_client.get("/admin/api/settings").json()
        assert admin_all["notifications.smtp_password"] != "hunter2"
    finally:
        logged_in_client.put("/admin/api/settings/notifications", json={"notifications.smtp_password": ""})
