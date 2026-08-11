"""Pass 11 — webhooks. A local stub HTTP receiver (stdlib http.server,
no new dependency) plays the role of the "Flask/FastAPI stub receiver"
the plan calls for, on 127.0.0.1 so it never leaves the test process.
See docs/CALENDAR_MODULE_PLAN.md and PASS11_NOTES.md."""
import datetime as dt
import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from sqlalchemy import delete

from app.db import session_scope
from app.models import Webhook
from app.settings_service import set_setting


@pytest.fixture(autouse=True)
def _widen_booking_window():
    """This file's dates start at nth-workday 150 to stay clear of
    every other booking-related test file's date window (see
    PASS9_NOTES.md for the collision class this avoids)."""
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 365, actor_id=None, actor_username="test-setup")
    yield
    with session_scope() as db:
        set_setting(db, "booking.max_days_ahead", 30, actor_id=None, actor_username="test-teardown")


@pytest.fixture(autouse=True)
def _clear_webhooks_after_test():
    """Every real booking created anywhere in the suite dispatches to
    every active Webhook row that exists — a webhook left behind by an
    earlier test, pointing at a now-shut-down stub server, silently
    slows down (connection-refused is fast, but not free) or worse
    hangs every booking made by *any other test file* for the rest of
    the session. Deleting straight from the DB (not via the HTTP API)
    so cleanup never depends on auth state."""
    yield
    with session_scope() as db:
        db.execute(delete(Webhook))  # cascades to WebhookDelivery


def _nth_future_workday(n: int) -> str:
    d = dt.date.today()
    found = 0
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            found += 1
            if found == n:
                return d.isoformat()


VALID_APPT = {"name": "Jamie Rivera", "email": "jamie@example.com", "phone": "555-0100"}


class _StubReceiver:
    """A tiny local HTTP server recording every request it gets, with a
    configurable response status. Used instead of mocking httpx so the
    test exercises a real request/response round trip, matching how
    the plan describes verifying the signature."""

    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.requests: list[dict] = []
        handler = self._make_handler()
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def _make_handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                outer.requests.append({
                    "body": body,
                    "signature": self.headers.get("X-Perennia-Signature"),
                    "content_type": self.headers.get("Content-Type"),
                })
                self.send_response(outer.status_code)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A002 - silence stdlib's default stderr logging
                pass

        return Handler

    @property
    def url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}/hook"

    def shutdown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)


@pytest.fixture
def receiver():
    r = _StubReceiver(status_code=200)
    yield r
    r.shutdown()


# ── CRUD ─────────────────────────────────────────────────────────────

def test_create_webhook_returns_secret_once(logged_in_client, receiver):
    resp = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "secret" in body
    assert len(body["secret"]) > 20
    assert body["events"] == ["booking.confirmed"]
    assert body["is_active"] is True


def test_get_and_list_never_include_secret(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()

    listed = logged_in_client.get("/admin/api/webhooks").json()
    match = next(w for w in listed if w["id"] == created["id"])
    assert "secret" not in match


def test_invalid_event_name_rejected(logged_in_client, receiver):
    resp = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.teleported"],
    })
    assert resp.status_code == 400


def test_https_required_in_production(logged_in_client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    try:
        resp = logged_in_client.post("/admin/api/webhooks", json={
            "url": "http://example.com/hook", "events": ["booking.confirmed"],
        })
        assert resp.status_code == 400
    finally:
        monkeypatch.setattr(settings, "ENVIRONMENT", "development")


def test_http_allowed_outside_production(logged_in_client, receiver):
    # receiver.url is already http://127.0.0.1:.../hook, and the test
    # suite runs with ENVIRONMENT=development (see conftest.py)
    resp = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    })
    assert resp.status_code == 200


def test_update_webhook_events_and_active(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()

    resp = logged_in_client.patch(f"/admin/api/webhooks/{created['id']}", json={
        "events": ["booking.confirmed", "booking.cancelled"], "is_active": False,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["events"]) == {"booking.confirmed", "booking.cancelled"}
    assert body["is_active"] is False


def test_update_unknown_webhook_404(logged_in_client):
    resp = logged_in_client.patch("/admin/api/webhooks/not-real", json={"is_active": False})
    assert resp.status_code == 404


def test_delete_webhook(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()
    resp = logged_in_client.delete(f"/admin/api/webhooks/{created['id']}")
    assert resp.status_code == 200
    again = logged_in_client.delete(f"/admin/api/webhooks/{created['id']}")
    assert again.status_code == 404


def test_regenerate_secret_returns_new_plaintext_once(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()
    resp = logged_in_client.post(f"/admin/api/webhooks/{created['id']}/regenerate-secret")
    assert resp.status_code == 200
    assert resp.json()["secret"] != created["secret"]


def test_webhooks_require_auth(client):
    assert client.get("/admin/api/webhooks").status_code == 401


# ── Delivery & signature ─────────────────────────────────────────────

def test_test_endpoint_delivers_and_signature_verifies(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()

    resp = logged_in_client.post(f"/admin/api/webhooks/{created['id']}/test")
    assert resp.status_code == 200
    delivery = resp.json()
    assert delivery["response_status"] == 200
    assert delivery["event"] == "booking.confirmed"

    assert len(receiver.requests) == 1
    received = receiver.requests[0]
    expected_sig = "sha256=" + hmac.new(created["secret"].encode(), received["body"], hashlib.sha256).hexdigest()
    assert received["signature"] == expected_sig
    body = json.loads(received["body"])
    assert body["event"] == "booking.confirmed"
    assert body["appointment"]["id"] == "PRN-TESTTEST"


def test_real_booking_confirmed_fires_webhook(logged_in_client, receiver, client):
    logged_in_client.post("/admin/api/webhooks", json={"url": receiver.url, "events": ["booking.confirmed"]})
    date = _nth_future_workday(150)

    resp = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    assert resp.json()["ok"] is True

    assert len(receiver.requests) == 1
    body = json.loads(receiver.requests[0]["body"])
    assert body["event"] == "booking.confirmed"
    assert body["appointment"]["email"] == VALID_APPT["email"]


def test_webhook_only_receives_subscribed_events(logged_in_client, receiver, client):
    logged_in_client.post("/admin/api/webhooks", json={"url": receiver.url, "events": ["booking.cancelled"]})
    date = _nth_future_workday(151)

    created = client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT}).json()
    assert len(receiver.requests) == 0  # subscribed only to cancelled, not confirmed

    client.post("/api/booking/appointments/cancel", json={"id": created["id"], "email": VALID_APPT["email"]})
    assert len(receiver.requests) == 1
    body = json.loads(receiver.requests[0]["body"])
    assert body["event"] == "booking.cancelled"


def test_inactive_webhook_receives_nothing(logged_in_client, receiver, client):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"], "is_active": False,
    }).json()
    date = _nth_future_workday(152)

    client.post("/api/booking/appointments", json={"date": date, "slot": "09:00", **VALID_APPT})
    assert len(receiver.requests) == 0


def test_non_2xx_response_recorded_not_swallowed(logged_in_client):
    bad_receiver = _StubReceiver(status_code=500)
    try:
        created = logged_in_client.post("/admin/api/webhooks", json={
            "url": bad_receiver.url, "events": ["booking.confirmed"],
        }).json()
        resp = logged_in_client.post(f"/admin/api/webhooks/{created['id']}/test")
        assert resp.status_code == 200  # the ADMIN request succeeds...
        assert resp.json()["response_status"] == 500  # ...and records the real failure status, not a fake 200
    finally:
        bad_receiver.shutdown()


def test_unreachable_url_records_null_status_not_error(logged_in_client):
    # Port 1 on loopback: nothing listens there, connection refused
    # immediately rather than timing out (keeps the test fast).
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": "http://127.0.0.1:1/hook", "events": ["booking.confirmed"],
    }).json()
    resp = logged_in_client.post(f"/admin/api/webhooks/{created['id']}/test")
    assert resp.status_code == 200
    assert resp.json()["response_status"] is None


def test_confirmation_workflow_events_fire(logged_in_client, receiver, client):
    """booking.requested and booking.accepted/declined — the three
    events Pass 10 added to the allow-list."""
    svc = logged_in_client.post("/admin/api/services", json={
        "name": "Webhook Confirmation Service", "duration_minutes": 30, "requires_confirmation": True,
    }).json()
    logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.requested", "booking.accepted", "booking.declined"],
    })
    date = _nth_future_workday(153)

    created = client.post("/api/booking/appointments", json={
        "date": date, "slot": "09:00", "service_id": svc["id"], **VALID_APPT,
    }).json()["appointment"]
    assert len(receiver.requests) == 1
    assert json.loads(receiver.requests[0]["body"])["event"] == "booking.requested"

    logged_in_client.post(f"/admin/api/booking/appointments/{created['id']}/accept")
    assert len(receiver.requests) == 2
    assert json.loads(receiver.requests[1]["body"])["event"] == "booking.accepted"


def test_deliveries_are_listed_most_recent_first(logged_in_client, receiver):
    created = logged_in_client.post("/admin/api/webhooks", json={
        "url": receiver.url, "events": ["booking.confirmed"],
    }).json()
    logged_in_client.post(f"/admin/api/webhooks/{created['id']}/test")
    logged_in_client.post(f"/admin/api/webhooks/{created['id']}/test")

    resp = logged_in_client.get(f"/admin/api/webhooks/{created['id']}/deliveries")
    assert resp.status_code == 200
    deliveries = resp.json()
    assert len(deliveries) == 2
    assert deliveries[0]["attempted_at"] >= deliveries[1]["attempted_at"]


def test_deliveries_for_unknown_webhook_404(logged_in_client):
    resp = logged_in_client.get("/admin/api/webhooks/not-real/deliveries")
    assert resp.status_code == 404
