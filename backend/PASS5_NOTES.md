# Pass 5 — Chat & leads

## What this pass adds

A real LLM-backed chat endpoint replacing the frontend's canned mock
reply, and a leads CRM that captures contacts automatically from real
signals rather than a dedicated capture form.

```
backend/app/
├── settings_registry.py    + chat.* (provider, model, API key [secret],
│                              temperature, max tokens, bilingual system
│                              prompt, bilingual fallback message)
├── llm_client.py            provider-abstracted (Anthropic/OpenAI),
│                              plain HTTP calls, no vendor SDK
├── chat_service.py           orchestrates a turn: config → LLM call →
│                              graceful fallback → opportunistic lead capture
├── leads_service.py          capture (upsert-by-email)/list/update/delete
├── models.py                 + Lead
├── booking_service.py        + captures a lead on every booking
└── routers/
    ├── public_chat.py         POST /api/chat
    └── admin_leads.py         /admin/api/leads CRUD

src/api/client.js             chat() now calls the real /api/chat endpoint
```

## Why leads are captured, not submitted

There's no "leave your email" form anywhere in this app, on purpose.
Two things already produce a name+email with real commercial intent —
booking a call, and volunteering an email mid-chat — so leads are
captured from those instead of asking for the same information twice.
`leads_service.capture_lead` upserts by email, so a visitor who chats
first and books later ends up as **one** lead with both touches in its
transcript, not two disconnected records — verified with a test that
does exactly that sequence and checks the merge.

## The LLM call: real, provider-abstracted, and safe to leave unconfigured

`llm_client.py` calls Anthropic's or OpenAI's REST API directly with
`httpx` — no SDK dependency, since both are a single JSON POST. But the
default `chat.llm_provider` is `"none"`, and every failure mode (no
key configured, provider unreachable, malformed response, wrong key)
funnels into the same `chat.unavailable_message` — the same message
text, in fact, that used to be the frontend's hardcoded mock reply, now
admin-editable and bilingual. A chat visitor never sees a raw error or
a 500; the assistant just says its regular "someone will follow up"
line and keeps working.

Verified three ways: unit tests mock the network call to check the
system-prompt/history/message plumbing without hitting a real API; a
separate test configures a real provider with a syntactically-plausible
but invalid key and confirms `LLMError` triggers the fallback; and — as
an extra check beyond what previous passes did — I actually pointed a
live server at the real `api.anthropic.com` with an invalid key and
confirmed the graceful degradation over an actual network round trip,
not just a mocked one.

## Secret handling

`chat.llm_api_key` is the first secret-typed setting actually exercised
end-to-end since Pass 1's encryption groundwork: encrypted at rest with
Fernet, absent from `/api/config/public` by construction (not
filtered — the public-config code path structurally can't return
secret-typed values), and masked rather than decrypted in the
admin "all settings" overview.

## Verified end to end

- 87 backend tests pass (19 new): fallback behavior (no provider,
  disabled feature, LLM failure), mocked-network plumbing test, secret
  exclusion/masking, lead capture from both booking and chat, upsert
  consolidation across sources, admin CRUD, and settings validation
  (temperature range, max tokens range, provider enum).
- **Live browser test**: opened the chat page, typed a message
  containing an email address into the actual chat input, watched the
  real reply come back from the running backend, then confirmed via
  the admin API that a lead was captured with the correct email and
  the exact message in its transcript — zero console errors.
- Caught and fixed a real bug in this process: the email-detection
  regex was including trailing punctuation (`"my email is x@y.com, ..."`
  was capturing `"x@y.com,"` with the comma attached). Fixed, covered
  by a new regression test, and reconfirmed live.

## Deliberately deferred to later passes

- No admin UI for the leads CRM yet — full CRUD via API, tested, same
  as every other pass until Pass 7.
- No streaming responses — the chat reply is a single request/response
  round trip. Worth revisiting for perceived latency once the app has
  a real provider key in regular use.
- No conversation persistence server-side beyond what a lead's
  transcript captures (only messages containing an email get stored).
  A visitor's full chat history currently lives only in the browser
  tab's React state, same as before this pass.
