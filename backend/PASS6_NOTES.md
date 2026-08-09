# Pass 6 — Notifications

## What this pass adds

Real outbound email and WhatsApp notifications for booking events, plus
internal staff alerts for new bookings and new chat leads — all
template-driven and off by default.

```
backend/app/
├── settings_registry.py    + notifications.* (SMTP config, WhatsApp
│                              provider config, internal alert address)
│                            + templates.* (bilingual, editable subject/
│                              body for every notification this pass sends)
├── whatsapp_client.py        provider-abstracted (Twilio/Meta Cloud API),
│                              plain HTTP, no vendor SDK
├── notification_service.py   renders templates, sends email (smtplib)
│                              and WhatsApp, always best-effort
├── models.py                 Appointment + lang (picks template language)
├── booking_service.py        cancel_appointment now reports whether it
│                              was a fresh cancel vs. already-cancelled
│                              (prevents duplicate cancellation emails
│                              on idempotent re-calls)
├── leads_service.py           capture_lead now reports (lead, created)
│                              so callers can alert only on new contacts
└── routers/public_booking.py  triggers notifications after each
                                 successful create/cancel/reschedule
```

No new admin API endpoints were needed — `notifications.*` and
`templates.*` are just new categories in Pass 1's generic settings
CRUD. This is the registry design paying for itself again: a whole new
subsystem's configuration surface, and the only new "admin API code"
required was zero.

## Notifications are structurally unable to break the thing that triggered them

Every send path — SMTP, WhatsApp, template rendering — is wrapped so a
failure degrades to "notification didn't go out" rather than "the
booking failed" or "the chat reply didn't come back." This mattered
enough to test explicitly: a test intentionally makes `smtplib.SMTP`
raise on every call and confirms the booking API still returns
`ok: true`. It also matters for template editing specifically — an
admin can edit `templates.booking_confirmed_email` through the generic
settings API and enter a malformed `{placeholder}`; `_notify_booking`
catches that (a `KeyError`/`ValueError` from `.format()`) the same way
it catches a real network failure, logs it, and moves on.

## A real bug caught by testing this against an actual SMTP server

Cancelling an already-cancelled appointment is deliberately idempotent
at the API level (Pass 4) — calling cancel twice returns `ok: true`
both times. Without a fix, that idempotency would have meant a second,
identical cancellation email on every repeat call (e.g., a person
double-tapping "Cancel," or a client retrying after a timeout).
`cancel_appointment` now returns `already_cancelled: true/false` so the
router only fires the notification on the call that actually changed
something. Covered by `test_cancellation_email_sent_and_not_duplicated_on_repeat_cancel`.

## Verified end to end — including a real SMTP transaction

- 104 backend tests pass (17 new): template rendering and language
  fallback, mocked email/WhatsApp send paths, booking-triggered
  notifications (confirm/cancel/reschedule), the no-duplicate-on-
  idempotent-cancel fix, admin alerts firing once per new lead (not
  once per message), and settings validation.
- Went further than mocking for email specifically: **stood up a real
  local SMTP server** (Python's `aiosmtpd`), pointed the backend's
  actual SMTP settings at it through the live admin API, and booked
  real appointments through the running server. Captured and decoded
  the actual wire-format emails — confirmed both the visitor
  confirmation (correct name/date/time/code substituted into the
  template) and the internal staff alert arrived as separate,
  correctly-addressed messages, and that suppressing the alert address
  correctly suppressed only that email.
- Also incidentally re-confirmed the graceful-degradation behavior for
  real: mid-testing, the debug SMTP server had died without my
  noticing, and a booking made while `notifications.email_enabled` was
  on still returned `ok: true` — the exact behavior the tests assert,
  now also seen happening by accident against a truly unreachable
  server, not just a mocked one.
- WhatsApp sending is verified via mocked-network tests only —
  `api.twilio.com` and `graph.facebook.com` aren't reachable from this
  environment's network egress rules (unlike `api.anthropic.com` in
  Pass 5), so there was no way to repeat the "real transaction" check
  for that channel here. The plumbing (provider selection, request
  shape per provider, graceful failure) is exercised the same way the
  LLM client was in Pass 5.

## Deliberately deferred to later passes

- No admin UI for composing/previewing templates yet — API-only,
  fully tested, same pattern as every pass before Pass 8.
- No delivery status tracking (bounced emails, failed WhatsApp sends
  aren't recorded anywhere beyond a server log line) — worth adding
  once there's an admin UI to actually show that history in.
- No retry/queue for failed sends — a failure is logged and dropped,
  not retried. Fine for a low-volume booking site; would need
  revisiting for higher volume.
