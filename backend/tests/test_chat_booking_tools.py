"""
Covers two layers of the "book a real appointment from inside chat"
feature:

1. app.chat_tools — the tool executor itself, exercised directly
   against a real db session (no LLM involved).
2. app.llm_client — the provider-agnostic tool-call loop, exercised
   against a fake httpx transport that simulates a model calling a
   tool once, then returning a final text reply.

test_chat.py separately covers the /api/chat endpoint's plumbing.
"""
from __future__ import annotations

import datetime as dt
import json as json_module

import httpx
import pytest

from app import chat_tools, llm_client
from app.db import session_scope


def _next_workday(n: int = 1) -> str:
    d = dt.date.today()
    found = 0
    while True:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            found += 1
            if found == n:
                return d.isoformat()


def _create_service(logged_in_client, **overrides):
    body = {"name": "Tool Test Service", "duration_minutes": 30, **overrides}
    return logged_in_client.post("/admin/api/services", json=body).json()


# ── chat_tools executor ──────────────────────────────────────────────

def test_list_services_tool_returns_active_services_only(logged_in_client):
    active = _create_service(logged_in_client, name="Active Tool Service")
    inactive = _create_service(logged_in_client, name="Inactive Tool Service")
    logged_in_client.delete(f"/admin/api/services/{inactive['id']}")

    with session_scope() as db:
        result = chat_tools.make_executor(db, lang="en")("list_services", {})

    ids = [s["id"] for s in result["services"]]
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_check_availability_tool_returns_real_slots(logged_in_client):
    date = _next_workday(20)
    with session_scope() as db:
        result = chat_tools.make_executor(db, lang="en")("check_availability", {"date": date})
    assert result["ok"] is True
    assert result["slots"], "expected at least one open slot on a plain future workday"


def test_check_availability_tool_bad_date_is_a_tool_error_not_an_exception(logged_in_client):
    with session_scope() as db:
        result = chat_tools.make_executor(db, lang="en")("check_availability", {"date": "not-a-date"})
    assert result == {"ok": False, "error": "invalid_date"}


def test_book_appointment_tool_creates_a_real_appointment(logged_in_client):
    date = _next_workday(21)
    with session_scope() as db:
        executor = chat_tools.make_executor(db, lang="en")
        slots = executor("check_availability", {"date": date})["slots"]
        result = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "Chat Tool Tester", "email": "chattool@example.com",
        })
    assert result["ok"] is True
    assert result["appointment"]["status"] in ("confirmed", "pending")

    # It's a real appointment - the admin API sees it too.
    resp = logged_in_client.get("/admin/api/booking/appointments")
    ids = [a["id"] for a in resp.json()]
    assert result["id"] in ids


def test_book_appointment_tool_rejects_unavailable_slot(logged_in_client):
    date = _next_workday(22)
    with session_scope() as db:
        result = chat_tools.make_executor(db, lang="en")("book_appointment", {
            "date": date, "slot": "03:00", "name": "Someone", "email": "someone@example.com",
        })
    assert result == {"ok": False, "error": "slot_unavailable"}


def test_unknown_tool_name_is_a_tool_error() -> None:
    with session_scope() as db:
        result = chat_tools.make_executor(db, lang="en")("delete_everything", {})
    assert result == {"ok": False, "error": "unknown_tool"}


def test_lookup_appointment_tool_finds_a_real_booking(logged_in_client):
    date = _next_workday(8)
    with session_scope() as db:
        executor = chat_tools.make_executor(db, lang="en")
        slots = executor("check_availability", {"date": date})["slots"]
        booked = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "Lookup Tester", "email": "lookup@example.com",
        })
        result = executor("lookup_appointment", {"id": booked["id"], "email": "lookup@example.com"})
    assert result["ok"] is True
    assert result["appointment"]["id"] == booked["id"]


def test_lookup_appointment_tool_wrong_email_not_found(logged_in_client):
    date = _next_workday(9)
    with session_scope() as db:
        executor = chat_tools.make_executor(db, lang="en")
        slots = executor("check_availability", {"date": date})["slots"]
        booked = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "Wrong Email", "email": "right@example.com",
        })
        result = executor("lookup_appointment", {"id": booked["id"], "email": "wrong@example.com"})
    assert result == {"ok": False, "error": "not_found"}


def test_cancel_appointment_tool_cancels_a_real_booking(logged_in_client):
    date = _next_workday(10)
    with session_scope() as db:
        executor = chat_tools.make_executor(db, lang="en")
        slots = executor("check_availability", {"date": date})["slots"]
        booked = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "Cancel Tester", "email": "cancel@example.com",
        })
        result = executor("cancel_appointment", {"id": booked["id"], "email": "cancel@example.com"})
    assert result["ok"] is True
    assert result["appointment"]["status"] == "cancelled"

    resp = logged_in_client.get("/admin/api/booking/appointments", params={"status_filter": "cancelled"})
    ids = [a["id"] for a in resp.json()]
    assert booked["id"] in ids


def test_reschedule_appointment_tool_moves_a_real_booking(logged_in_client):
    date = _next_workday(11)
    new_date = _next_workday(12)
    with session_scope() as db:
        executor = chat_tools.make_executor(db, lang="en")
        slots = executor("check_availability", {"date": date})["slots"]
        booked = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "Reschedule Tester", "email": "reschedule@example.com",
        })
        new_slots = executor("check_availability", {"date": new_date})["slots"]
        result = executor("reschedule_appointment", {
            "id": booked["id"], "email": "reschedule@example.com", "date": new_date, "slot": new_slots[0],
        })
    assert result["ok"] is True
    assert result["appointment"]["date"] == new_date
    assert result["appointment"]["time"] == new_slots[0]


# ── llm_client tool-call loop ────────────────────────────────────────

def test_openai_compatible_loop_executes_tool_then_returns_final_text(monkeypatch):
    """Simulates: first response asks to call a tool, second response
    (after seeing the tool result) returns plain text."""
    calls = {"n": 0}

    def fake_post(url, *, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            assert any(m["role"] == "system" for m in json["messages"])
            body = {
                "choices": [{"message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{
                        "id": "call_1", "type": "function",
                        "function": {"name": "check_availability", "arguments": '{"date": "2030-01-01"}'},
                    }],
                }}]
            }
        else:
            # The tool result must have been appended as a 'tool' message.
            assert json["messages"][-1]["role"] == "tool"
            assert json["messages"][-1]["tool_call_id"] == "call_1"
            body = {"choices": [{"message": {"role": "assistant", "content": "Here's what's open."}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    def executor(name, args):
        assert name == "check_availability"
        assert args == {"date": "2030-01-01"}
        return {"ok": True, "slots": ["09:00"]}

    text = llm_client.generate_reply(
        provider="openai", api_key="sk-fake", model="gpt-test", system_prompt="sys",
        history=[], message="when are you free?", max_tokens=100, temperature=0.5,
        tools=chat_tools.BOOKING_TOOLS, tool_executor=executor,
    )
    assert text == "Here's what's open."
    assert calls["n"] == 2


def test_anthropic_loop_executes_tool_then_returns_final_text(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, *, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            body = {"content": [{"type": "tool_use", "id": "tu_1", "name": "list_services", "input": {}}]}
        else:
            assert json["messages"][-1]["role"] == "user"
            tool_result = json["messages"][-1]["content"][0]
            assert tool_result["type"] == "tool_result"
            assert tool_result["tool_use_id"] == "tu_1"
            body = {"content": [{"type": "text", "text": "We offer consultations."}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    def executor(name, args):
        assert name == "list_services"
        return {"services": [{"id": "svc_1", "name": "Consultation"}]}

    text = llm_client.generate_reply(
        provider="anthropic", api_key="sk-fake", model="claude-test", system_prompt="sys",
        history=[], message="what do you offer?", max_tokens=100, temperature=0.5,
        tools=chat_tools.BOOKING_TOOLS, tool_executor=executor,
    )
    assert text == "We offer consultations."
    assert calls["n"] == 2


def test_tool_loop_gives_up_after_max_iterations(monkeypatch):
    """A model that keeps calling tools forever must not hang the
    request - it should surface as LLMError after MAX_TOOL_ITERATIONS,
    which chat_service.py turns into the ordinary fallback message."""
    def fake_post(url, *, headers=None, json=None, timeout=None):
        body = {"choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "x", "type": "function",
                             "function": {"name": "list_services", "arguments": "{}"}}],
        }}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(llm_client.LLMError):
        llm_client.generate_reply(
            provider="openai", api_key="sk-fake", model="gpt-test", system_prompt="sys",
            history=[], message="hi", max_tokens=100, temperature=0.5,
            tools=chat_tools.BOOKING_TOOLS, tool_executor=lambda n, a: {"ok": True},
        )


def test_tool_executor_exception_becomes_a_tool_error_not_a_crash(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, *, headers=None, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            body = {"choices": [{"message": {
                "role": "assistant", "content": None,
                "tool_calls": [{"id": "x", "type": "function",
                                 "function": {"name": "book_appointment", "arguments": "{}"}}],
            }}]}
        else:
            tool_msg = [m for m in json["messages"] if m.get("role") == "tool"][-1]
            payload = json_module.loads(tool_msg["content"])
            assert payload["ok"] is False
            body = {"choices": [{"message": {"role": "assistant", "content": "Something went wrong, sorry."}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)

    def blowing_up_executor(name, args):
        raise RuntimeError("boom")

    text = llm_client.generate_reply(
        provider="openai", api_key="sk-fake", model="gpt-test", system_prompt="sys",
        history=[], message="book it", max_tokens=100, temperature=0.5,
        tools=chat_tools.BOOKING_TOOLS, tool_executor=blowing_up_executor,
    )
    assert text == "Something went wrong, sorry."


# ── end-to-end: /api/chat wires the real booking tools through ────────

def test_chat_endpoint_passes_booking_tools_and_a_working_executor(logged_in_client, client, monkeypatch):
    """chat_service.get_reply must hand llm_client a tool_executor that
    is genuinely wired to this app's booking_service — not a stub —
    so whatever the LLM decides to book for real gets booked for
    real, identically to the 'Talk to Us' form."""
    captured = {}

    def fake_generate_reply(**kwargs):
        captured.update(kwargs)
        return "Booked!"

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    try:
        resp = client.post("/api/chat", json={"message": "book me something", "lang": "en", "history": []})
        assert resp.status_code == 200
        assert resp.json()["reply"] == "Booked!"

        tool_names = {t["name"] for t in captured["tools"]}
        assert {"list_services", "check_availability", "book_appointment"} <= tool_names

        date = _next_workday(5)
        executor = captured["tool_executor"]
        slots = executor("check_availability", {"date": date})["slots"]
        booked = executor("book_appointment", {
            "date": date, "slot": slots[0], "name": "End To End", "email": "e2e@example.com",
        })
        assert booked["ok"] is True

        admin_resp = logged_in_client.get("/admin/api/booking/appointments")
        assert booked["id"] in [a["id"] for a in admin_resp.json()]
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_endpoint_omits_tools_when_booking_disabled(logged_in_client, client, monkeypatch):
    captured = {}

    def fake_generate_reply(**kwargs):
        captured.update(kwargs)
        return "OK."

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    logged_in_client.put("/admin/api/settings/features", json={"features.booking_enabled": False})
    try:
        resp = client.post("/api/chat", json={"message": "hi", "lang": "en", "history": []})
        assert resp.status_code == 200
        assert captured["tools"] is None
        assert captured["tool_executor"] is None
    finally:
        logged_in_client.put("/admin/api/settings/features", json={"features.booking_enabled": True})
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})
