# Pass 11 — webhooks

## What this pass adds

Lets the business wire external systems (a CRM, a spreadsheet
automation, Slack, ...) into calendar events without polling —
matching Pass 11 in `docs/CALENDAR_MODULE_PLAN.md`.

```
backend/app/models.py              + Webhook, WebhookDelivery
backend/app/webhook_service.py       CRUD + HMAC-signed delivery
backend/app/routers/admin_webhooks.py  admin CRUD, deliveries, test-send
backend/app/routers/public_booking.py  + dispatch_event at 4 trigger points
backend/app/routers/admin_booking.py   + dispatch_event at 2 trigger points
backend/tests/test_webhooks.py       19 new tests
```

## The six events, wired at the exact six existing trigger points

The event allow-list — `booking.confirmed`, `booking.cancelled`,
`booking.rescheduled`, `booking.requested`, `booking.accepted`,
`booking.declined` — maps one-to-one onto `notification_service.py`'s
six `notify_booking_*` functions, and `webhook_service.dispatch_event`
is called immediately alongside each existing `notify_booking_*` call
site (`public_booking.py`'s create/cancel/reschedule handlers,
`admin_booking.py`'s accept/reject handlers). No new trigger points
were invented and no existing trigger point's surrounding logic
changed — exactly what the plan's Definition of Done asks for.
`admin_cancel_appointment` (the admin-initiated cancel) was deliberately
left alone: it doesn't call any `notify_booking_*` today either, so
there was no existing trigger point there to hook into without
inventing new scope beyond what this pass asked for.

## Secret handling

`Webhook.secret` gets the same at-rest treatment as
`SiteSetting.is_secret` rows: Fernet-encrypted via the existing
`app/security.py` helpers (`encrypt_secret`/`decrypt_secret`), no new
crypto path introduced. The plaintext is generated once at creation
(`secrets.token_urlsafe(32)`) and returned exactly once, in the
creation response — `WebhookOut` (used by every other read) has no
`secret` field at all, so there's no masking logic that could have a
bug; the field simply doesn't exist outside the one response shape
(`WebhookCreateOut`) that's allowed to carry it.
`POST /{id}/regenerate-secret` is the only other way to see a
plaintext secret, and only the new one — there's no way to retrieve an
existing webhook's current secret through any endpoint.

## Delivery mechanics

- **Signature**: `X-Perennia-Signature: sha256=<hmac-hex>`, computed
  with `hmac.new(secret, raw_body, sha256)` over the *exact bytes*
  sent as the request body — the payload is serialized to JSON once
  and that same `bytes` object is both signed and sent via `httpx`'s
  `content=` parameter (not `json=`, which would re-serialize and
  risk a signature/body mismatch from Python dict key ordering or
  float formatting differences between two separate `json.dumps`
  calls).
- **One delivery per matching event per webhook** — `dispatch_event`
  loops over every active webhook subscribed to the event and calls
  `_deliver_one` for each, never batching multiple webhooks' payloads
  into one call.
- **No automatic retries**, per the plan's explicit scope decision.
  A failed delivery — non-2xx response, or the request never
  completing at all (DNS failure, connection refused, timeout) — is
  logged to `WebhookDelivery` with its outcome and surfaced for the
  admin to see; `response_status` is `null` specifically to
  distinguish "never got a response" from "got an error response,"
  since those are different failure modes an admin debugging their
  own endpoint needs to tell apart.
- **Never raises into the booking action that triggered it.**
  `_deliver_one` catches `httpx.HTTPError` and records `response_status
  = None`; `dispatch_event` wraps each webhook's delivery in a second,
  broader `try/except` as a last-resort guard (e.g. a corrupted secret
  failing to decrypt) so one broken webhook configuration can never
  prevent delivery to the others, matching
  `notification_service.py`'s own best-effort philosophy exactly.

## API

`admin_webhooks.py` implements every endpoint from the plan: `GET /`,
`POST /` (returns `secret` once), `PATCH /{id}` (cannot touch
`secret`), `DELETE /{id}`, `POST /{id}/regenerate-secret`,
`GET /{id}/deliveries` (paginated, most recent first, `limit` clamped
to 1–200), and `POST /{id}/test` — which fires a synthetic
`booking.confirmed` payload built from a fabricated fixture appointment
(not a real one) at exactly the one webhook being tested, using the
same `_deliver_one` machinery the real dispatch path uses, so testing
an endpoint before going live exercises the identical signing and
delivery code.

## Tests, and a second real cross-test pollution bug

`tests/test_webhooks.py` (19 tests) uses a small stdlib
`http.server.HTTPServer` stub receiver bound to `127.0.0.1` on an
ephemeral port — no new test dependency — recording every request it
gets so the signature can be independently recomputed and compared.
Covers: secret returned once and never again, invalid event name
rejected, `https://` enforced in production
(`monkeypatch`-ed `settings.ENVIRONMENT`) but `http://` allowed
outside it, full CRUD lifecycle, regeneration, auth enforcement, the
`/test` endpoint's signature round-trip, a real booking actually
firing `dispatch_event` end-to-end, a webhook subscribed to only one
event never receiving another, an inactive webhook receiving nothing,
a non-2xx response recorded accurately (not swallowed into a fake
success), an unreachable URL recording `null` rather than raising, all
three Pass-10 confirmation-workflow events firing in sequence, and
delivery-log ordering/404s.

**Writing these tests surfaced a second instance of the exact
cross-test pollution pattern documented in Pass 9's notes**, this time
with a new and more expensive failure mode: a `Webhook` row left in
the database by one test — pointing at a stub server that's since been
shut down — gets dispatched to by *every subsequent real booking made
anywhere in the suite*, in this file and every other test file. Since
`httpx.post` has to actually attempt the connection before failing,
each leftover webhook adds real wall-clock time to every booking made
afterward; two of this file's own tests were measured at 10–20 seconds
each before the fix (against a wider suite still nominally "passing,"
just slowly and with unnecessary network attempts) purely from
accumulated stale webhooks left behind by earlier tests in the same
file. Fixed the same way Pass 9 fixed its analogous leak: an autouse
fixture that deletes every `Webhook` row straight from the DB after
each test in this file (bypassing the HTTP API, so cleanup never
depends on auth state) — confirmed by re-timing: 12.97s for the whole
file afterward, versus 43–103s (noisy, but consistently much worse)
before.

Following the same discipline as Passes 9 and 10: full suite run four
times in default execution order — **230 passed** consistently
(211 + 19) — and, unlike Passes 9 and 10, **also fully clean three
times in reversed file order**. That's new: Passes 9 and 10 each
closed with one remaining, documented, pre-existing collision between
`test_leads.py` and `test_notifications.py`, deliberately left as
out-of-scope follow-up. While doing the final pre-commit verification
for *this* pass, that collision actually fired — not under reversed
order this time, but in plain default order, because the container's
real clock crossed a day boundary partway through this project and
"today" became a weekday where several of those two files' fixed
`min_days_ahead` values happened to alias onto the same calendar date
(offsets 4, 5, and 6 all landing on the same following Monday is
exactly the bug class documented in `PASS9_NOTES.md` for this
project's own test files — `test_leads.py` and `test_notifications.py`
just never happened to hit it before, because it depends on which
weekday the suite happens to run on). Traced to ground via `git stash`
(confirmed present at the Pass 10 commit, so not something this pass
introduced) and a scripted reproduction outside pytest, then fixed the
same way this project's own files were fixed in Pass 9: replaced the
raw-day-offset `_future_workday` helper in both files with the
`_nth_future_workday` counted-workday approach (guaranteed-distinct
dates regardless of which weekday "today" is), each file's date window
widened via the same autouse-fixture pattern already established.
This was a pre-existing bug in files neither Pass 9, 10, nor 11 wrote,
fixed here because it was fully diagnosed, cheap to fix correctly, and
actively blocking a clean verification run — leaving it for a future
pass once already root-caused would have been the wrong call.

## Explicitly not in this pass

Retry/backoff logic for failed deliveries (explicitly deferred by the
plan — "until there's evidence it's needed"), and the admin UI
(`WebhooksPage.jsx` — bundled into Pass 13 alongside Availability's UI
and Calendar Sync, per the plan, once all three have stable APIs to
build against).
