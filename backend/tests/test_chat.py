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

        # The category-level endpoint (what the settings UI's edit form
        # reads from) must ALSO never return the plaintext value — only
        # a masked placeholder, same rule as the all-settings endpoint.
        category = logged_in_client.get("/admin/api/settings/chat").json()
        assert category["values"]["chat.llm_api_key"] != "super-secret-value"
        assert category["values"]["chat.llm_api_key"] == "••••••••"
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_api_key": ""})


def test_secret_placeholder_reflects_unset_state(logged_in_client):
    logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_api_key": ""})
    category = logged_in_client.get("/admin/api/settings/chat").json()
    assert category["values"]["chat.llm_api_key"] == ""


def test_resubmitting_secret_placeholder_does_not_overwrite_it(logged_in_client):
    """Simulates the settings UI's edit form: fetch the category (gets
    the masked placeholder back for the secret field), then save the
    form as-is without touching that field. The real secret must
    survive — this is the write-path half of the masking fix."""
    logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_api_key": "real-secret-key"})
    try:
        category = logged_in_client.get("/admin/api/settings/chat").json()
        assert category["values"]["chat.llm_api_key"] == "••••••••"

        resp = logged_in_client.put("/admin/api/settings/chat", json=category["values"])
        assert resp.status_code == 200

        still_masked = logged_in_client.get("/admin/api/settings/chat").json()
        assert still_masked["values"]["chat.llm_api_key"] == "••••••••"
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


def test_chat_calls_configured_deepseek_provider(logged_in_client, client, monkeypatch):
    """Same plumbing check as test_chat_calls_configured_llm_provider,
    but for the 'deepseek' provider — confirms it's accepted by the
    chat.llm_provider enum and correctly passed through to
    llm_client.generate_reply."""
    captured = {}

    def fake_generate_reply(**kwargs):
        captured.update(kwargs)
        return "This is a canned DeepSeek reply."

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)

    resp = logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "deepseek", "chat.llm_api_key": "ds-fake-test-key",
        "chat.llm_model": "deepseek-chat",
    })
    assert resp.status_code == 200
    try:
        chat_resp = client.post("/api/chat", json={
            "message": "What services do you offer?", "lang": "en", "history": [],
        })
        assert chat_resp.status_code == 200
        assert chat_resp.json()["reply"] == "This is a canned DeepSeek reply."
        assert captured["provider"] == "deepseek"
        assert captured["api_key"] == "ds-fake-test-key"
        assert captured["model"] == "deepseek-chat"
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_lead_tag_is_captured_and_stripped_from_reply(logged_in_client, client, monkeypatch):
    """The assistant's hidden [[LEAD_CAPTURED ...]] tag must produce a
    real lead with name/phone/email and never reach the visitor."""
    def fake_generate_reply(**kwargs):
        return 'Great to meet you! [[LEAD_CAPTURED name="Sara" phone="+96599999999" email="sara@example.com"]]'

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)

    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    try:
        resp = client.post("/api/chat", json={"message": "sara@example.com", "lang": "en", "history": []})
        assert resp.status_code == 200
        body = resp.json()
        assert "LEAD_CAPTURED" not in body["reply"]
        assert body["leadCaptured"] is True

        leads = logged_in_client.get("/admin/api/leads").json()
        lead = next(l for l in leads if l["email"] == "sara@example.com")
        assert lead["name"] == "Sara"
        assert lead["phone"] == "+96599999999"
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_malformed_lead_tag_is_stripped_but_not_captured(logged_in_client, client, monkeypatch):
    def fake_generate_reply(**kwargs):
        return 'Thanks! [[LEAD_CAPTURED name="" phone="???" email="not-an-email"]]'

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    try:
        resp = client.post("/api/chat", json={"message": "hi", "lang": "en", "history": []})
        body = resp.json()
        assert "LEAD_CAPTURED" not in body["reply"]
        assert body["leadCaptured"] is False
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_leadcaptured_flag_skips_lead_instructions_next_turn(logged_in_client, client, monkeypatch):
    captured = {}

    def fake_generate_reply(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return "ok"

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    try:
        client.post("/api/chat", json={"message": "hi", "lang": "en", "history": [], "leadCaptured": True})
        assert "LEAD_CAPTURED" not in captured["system_prompt"]

        client.post("/api/chat", json={"message": "hi", "lang": "en", "history": [], "leadCaptured": False})
        assert "LEAD_CAPTURED" in captured["system_prompt"]
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})


def test_chat_turn_limit_returns_configured_message_without_calling_llm(logged_in_client, client, monkeypatch):
    def unexpected_call(**kwargs):
        raise AssertionError("LLM should not be called once the turn limit is exceeded")

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", unexpected_call)
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key", "chat.max_turns": 2,
    })
    try:
        long_history = [{"from": "user", "text": "hi"}, {"from": "ai", "text": "hello"}] * 2
        resp = client.post("/api/chat", json={"message": "one more", "lang": "en", "history": long_history})
        assert resp.status_code == 200
        assert resp.json()["reply"]  # the configured turn-limit message, not a crash
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none", "chat.max_turns": 15})


def test_chat_contact_info_reaches_system_prompt(logged_in_client, client, monkeypatch):
    captured = {}

    def fake_generate_reply(**kwargs):
        captured["system_prompt"] = kwargs["system_prompt"]
        return "ok"

    monkeypatch.setattr("app.chat_service.llm_client.generate_reply", fake_generate_reply)
    logged_in_client.put("/admin/api/settings/contact", json={"contact.email": "hello@perennia.example"})
    logged_in_client.put("/admin/api/settings/chat", json={
        "chat.llm_provider": "anthropic", "chat.llm_api_key": "sk-fake-test-key",
    })
    try:
        client.post("/api/chat", json={"message": "how can we reach you?", "lang": "en", "history": []})
        assert "hello@perennia.example" in captured["system_prompt"]
    finally:
        logged_in_client.put("/admin/api/settings/chat", json={"chat.llm_provider": "none"})
        logged_in_client.put("/admin/api/settings/contact", json={"contact.email": ""})


def test_llm_client_treats_ai_history_role_as_assistant():
    """Regression: frontend history entries use {from: 'ai', ...}, not
    'assistant' — the role mapper must not silently relabel the
    assistant's own prior turns as 'user' messages."""
    from app.llm_client import _history_to_messages

    history = [{"from": "user", "text": "hi"}, {"from": "ai", "text": "hello there"}]
    messages = _history_to_messages(history)
    assert messages == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello there"},
    ]
