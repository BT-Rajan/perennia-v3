def test_chat_falls_back_when_no_provider_configured(client):
    resp = client.post("/api/chat", json={"message": "Hello there", "lang": "en", "history": []})
    assert resp.status_code == 200
    body = resp.json()
    assert "follow up" in body["reply"] or "team" in body["reply"]


def test_chat_fallback_in_arabic(client):
    resp = client.post("/api/chat", json={"message": "مرحبا", "lang": "ar", "history": []})
    assert resp.status_code == 200
    assert "بيرينيا" in resp.json()["reply"] or len(resp.json()["reply"]) > 0


def test_chat_disabled_feature_returns_fallback(logged_in_client, client):
    logged_in_client.put("/admin/api/settings/features", json={"features.chat_enabled": False})
    try:
        resp = client.post("/api/chat", json={"message": "hi", "lang": "en", "history": []})
        assert resp.status_code == 200
        assert resp.json()["reply"]  # still gets the fallback message, not an error
    finally:
        logged_in_client.put("/admin/api/settings/features", json={"features.chat_enabled": True})


def test_chat_calls_configured_llm_provider(logged_in_client, client, monkeypatch):
    """Configures a fake provider + key, monkeypatches the actual
    network call, and confirms the chat endpoint correctly plumbs
    system prompt / history / message through to it — without ever
    making a real network request."""
    captured = {}

    def fake_generate_reply(**kwargs):
        captured.update(kwargs)
        return "This is a canned LLM reply."

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)

    resp = logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    assert resp.status_code == 200
    try:
        chat_resp = client.post("/api/chat", json={
            "message": "What services do you offer?", "lang": "en",
            "history": [{"from": "assistant", "text": "Hi! How can I help?"}],
        })
        assert chat_resp.status_code == 200
        assert chat_resp.json()["reply"] == "This is a canned LLM reply."
        assert captured["provider"] == "anthropic"
        assert captured["api_key"] == "sk-fake-test-key"
        assert captured["message"] == "What services do you offer?"
        assert captured["history"] == [{"from": "assistant", "text": "Hi! How can I help?"}]
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_falls_back_when_llm_call_fails(logged_in_client, client, monkeypatch):
    from app.llm_client import LLMError

    def failing(**kwargs):
        raise LLMError("simulated failure")

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", failing)

    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake",
    })
    try:
        resp = client.post("/api/chat", json={"message": "test", "lang": "en", "history": []})
        assert resp.status_code == 200
        assert resp.json()["reply"]  # gracefully degraded to the fallback message, no 500
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_api_key_never_exposed_publicly(logged_in_client, client):
    logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_api_key": "super-secret-value"})
    try:
        public = client.get("/api/config/public").json()
        assert "chat.llm_api_key" not in public

        admin_all = logged_in_client.get("/admin/api/settings").json()
        assert admin_all["chat.llm_api_key"] != "super-secret-value"
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_api_key": ""})


def test_chat_message_with_email_captures_a_lead(logged_in_client, client):
    client.post("/api/chat", json={
        "message": "You can reach me at prospect@example.com if you have questions",
        "lang": "en", "history": [],
    })
    leads = logged_in_client.get("/admin/api/leads").json()
    assert any(l["email"] == "prospect@example.com" and l["source"] == "chat" for l in leads)


def test_chat_email_with_trailing_punctuation_is_captured_cleanly(logged_in_client, client):
    """A comma right after the email (very common natural phrasing)
    must not get swept into the captured address."""
    client.post("/api/chat", json={
        "message": "Hi, my email is punctuation-test@example.com, tell me about your services",
        "lang": "en", "history": [],
    })
    leads = logged_in_client.get("/admin/api/leads").json()
    assert any(l["email"] == "punctuation-test@example.com" for l in leads)
    assert not any(l["email"].endswith(",") for l in leads)


def test_chat_message_without_email_does_not_capture_a_lead(logged_in_client, client):
    before = len(logged_in_client.get("/admin/api/leads").json())
    client.post("/api/chat", json={"message": "just saying hello, no contact info here", "lang": "en", "history": []})
    after = len(logged_in_client.get("/admin/api/leads").json())
    assert after == before


def test_temperature_setting_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/chat", json={"chat.temperature": 1.5})
    assert resp.status_code == 400


def test_max_tokens_setting_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/chat", json={"chat.max_tokens": 10})
    assert resp.status_code == 400


def test_llm_provider_enum_validation(logged_in_client):
    resp = logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "made_up_provider"})
    assert resp.status_code == 400
