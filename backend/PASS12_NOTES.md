# Pass 12 — external calendar sync (Google, opt-in)

## What this pass adds

Lets the business connect one real Google Calendar so that busy time
on it blocks booking slots, and (optionally) so a confirmed booking
creates a matching event there — matching Pass 12 in
`docs/CALENDAR_MODULE_PLAN.md`. Entirely behind
`features.calendar_sync_enabled` (default `False`): with sync off,
every code path in this pass is a no-op and behavior is byte-identical
to Pass 11 — verified by the full pre-existing suite (230 tests)
passing unmodified.

```
backend/app/models.py                + CalendarCredential, Appointment.external_event_id
backend/app/google_calendar_client.py  thin, fully mockable Google OAuth/Calendar API client
backend/app/calendar_sync_service.py   connection lifecycle, busy-time lookup, event create/delete
backend/app/routers/admin_calendar_sync.py  connect/callback/select/disconnect/status
backend/app/security.py              + sign_oauth_state/unsign_oauth_state
backend/app/settings_registry.py     + features.calendar_sync_enabled, booking.calendar_sync_fail_open, calendar_sync.*
backend/app/booking_service.py         available_slots subtracts Google busy time
backend/tests/test_calendar_sync.py    19 new tests, no live Google account
```

## Google/Office 365/CalDAV scope

Only Google, only one connected account for the whole business (not
per-admin-user — `get_active_credential` is the single lookup every
other module needs). `CalendarCredential.provider` is a plain string
rather than a hardcoded enum specifically so a second provider
wouldn't need a schema migration, but no second provider is built in
this pass, per the plan.

## OAuth flow and secret handling

`access_token`/`refresh_token` get the identical at-rest treatment as
`Webhook.secret` and `SiteSetting.is_secret` rows: Fernet-encrypted via
`app/security.py`, no new crypto path. The OAuth `state` parameter —
the only CSRF/tampering defense across the redirect round-trip to
Google and back — is a signed, timestamped token (new
`sign_oauth_state`/`unsign_oauth_state` in `security.py`, same
`itsdangerous` pattern the session cookie already uses, its own salt
and a 10-minute expiry) carrying the initiating admin's id, so the
callback can confirm the same admin who started the connection is the
one completing it.

A `CalendarCredential` can exist mid-connect: tokens stored,
`calendar_id` still `None`, `is_active` still `False` — that's the
state right after `/callback` and before `/select`. Every other part
of the system (`get_active_credential`, busy-time lookup, event
creation) only ever looks at `is_active=True` rows, so a connection
that's been started but not finished never accidentally starts
blocking slots or creating events.

Google only returns a `refresh_token` on the *first* consent for a
given account+app — `access_type=offline` and `prompt=consent` are
both set on the auth URL specifically to maximize the chance of
getting one every time, but if Google still doesn't return one (a
previous, unrevoked grant), `complete_oauth_callback` raises rather
than silently storing a credential that will stop working the moment
the short-lived access token expires — with a message pointing at
where to revoke the stale prior grant.

## Busy-time blocking, and the fail-open/fail-closed decision

`booking_service.available_slots` fetches busy ranges for the day in
one call (`calendar_sync_service.busy_minutes_for_date`, one Free/Busy
API request regardless of how many candidate slots exist that day) and
folds them into the exact same overlap-check list Pass 8's
`_booked_intervals` already populates — no special-casing needed in
the slot loop itself, since "blocked" is already a generic list of
`(start, end)` minute ranges from multiple sources.

**On a Google API failure, the default is fail-closed** —
`booking.calendar_sync_fail_open` defaults to `False`, meaning "if we
can't confirm real availability, show no slots rather than risk a
double-booking," exactly as the plan specifies. This is implemented as
an internal `CalendarSyncUnavailableError`, raised by
`_google_busy_intervals` and caught by `available_slots` to return
`[]` for that request — deliberately *not* the same exception type as
`InvalidServiceError` (a 404-worthy client error), since an
unreachable calendar isn't the requester's fault and shouldn't surface
as an HTTP error status; it should just look like a fully-booked day.
Flipping `booking.calendar_sync_fail_open` to `True` is an explicit
admin opt-in to the opposite tradeoff (keep taking bookings, ignoring
the external calendar, while it's down).

## Token refresh, and a real bug it surfaced

`_ensure_fresh_access_token` refreshes 2 minutes before actual expiry
(`_REFRESH_SKEW`) rather than exactly at expiry, so a slow request can
never straddle the token becoming invalid mid-call. Writing this
surfaced two real bugs, both fixed:

1. **Naive/aware datetime comparison.** SQLite doesn't actually persist
   tzinfo on a `DateTime(timezone=True)` column — reads back naive —
   so comparing `credential.token_expires_at` directly against
   `datetime.now(timezone.utc)` raised `TypeError`. This project
   already has an established fix for exactly this
   (`app/deps.py`'s session-expiry check normalizes with
   `.replace(tzinfo=...)` before comparing); the identical fix is now
   applied here.

2. **A refreshed token was silently discarded.** `GET /api/booking/slots`
   is a read-only-looking endpoint and never called `db.commit()` —
   correct for a pure read, except that Pass 12 gives it a legitimate
   write side effect (caching a refreshed access token). `app/db.py`'s
   `get_db()` dependency never auto-commits, so that write was flushed
   within the request's transaction and then silently thrown away when
   the session closed uncommitted — meaning every single slots request
   against an expired token would re-refresh from Google, never
   actually caching anything. Fixed by adding an explicit `db.commit()`
   to `get_slots` after slot generation, with a comment explaining
   *why* an otherwise-read-only endpoint needs one. Caught by
   `test_expired_token_is_refreshed_before_freebusy_call`, which
   asserts the refreshed expiry is actually persisted in a fresh DB
   read, not just used within the triggering request.

## Event creation, and the stale-serialized-dict bug

On a booking's transition to `confirmed` (new booking, or Pass 10's
admin-accept), `calendar_sync_service.create_event_for_appointment`
best-effort-creates a Google Calendar event and persists its id onto
`Appointment.external_event_id`. On cancel or reschedule,
`delete_event_for_appointment` best-effort-removes it (reschedule
deletes the old event and creates a fresh one at the new time, rather
than attempting to `PATCH` an existing Google event — simpler, and this
whole sub-feature is explicitly optional per the plan). Both functions
never raise, matching `notification_service.py`'s established
philosophy: an appointment is already confirmed by the time either
runs, and a calendar-sync hiccup must never turn that into a broken
booking response.

**This surfaced a second real bug, this time in the router wiring, not
the service layer.** Every router handler builds its JSON response
from a dict returned by `booking_service.*` — serialized *before* the
calendar-sync call runs. `create_event_for_appointment` was originally
`-> None`, persisting `external_event_id` to the DB correctly but
leaving the already-built response dict stale, so a fresh booking's
own HTTP response reported `external_event_id: null` even on a request
where an event actually was just created. Fixed by having
`create_event_for_appointment` return the created id, and patching it
into the response dict at each of the three call sites (create,
reschedule, admin-accept) — `delete_event_for_appointment`'s call
sites similarly set `external_event_id: null` in their own response
dicts on cancel. Caught by
`test_event_created_on_confirmed_booking` and
`test_event_recreated_on_reschedule` asserting against the actual HTTP
response body, not just the DB row.

## Tests

`tests/test_calendar_sync.py` (19 tests, zero live Google calls) covers
the full OAuth connect→callback→select→status→disconnect flow (invalid
state rejected, missing refresh_token rejected, disconnect always
completes locally even when the mocked revoke call fails), busy-time
subtraction removing exactly the overlapping slot and leaving adjacent
ones alone, sync-disabled correctly never calling the Google client at
all, fail-closed-by-default returning zero slots on a simulated API
failure, the fail-open setting explicitly overriding that, a
mid-connect (calendar not yet selected) credential correctly not
blocking anything, token refresh actually persisting, and the full
event-creation lifecycle (created on confirm, not created while merely
pending, created on accept, deleted on cancel, deleted-and-recreated on
reschedule, and a simulated creation failure never breaking the
booking response). Every Google client function is monkeypatched
directly (`app.google_calendar_client.*`) — no live account required
to run the suite, per the plan's Definition of Done.

Following the same discipline as Passes 9–11: an autouse fixture
widens `booking.max_days_ahead` and clears every `CalendarCredential`
row after each test in this file (same pollution class as
`AvailabilityRule` and `Webhook` before it — a leftover active
credential would make every subsequent real booking in the suite try
to sync against it). Full suite verified **249 passed** (230 + 19)
across 4 runs in default order and 3 in reversed file order — still
fully clean in both, continuing from Pass 11.

## Explicitly not in this pass

Office 365 / CalDAV (only reconsidered if there's real demand once
Google sync is proven, per the plan), and the admin UI
(`CalendarSyncPage.jsx` — bundled into Pass 13 alongside Availability
and Webhooks, once all three have stable APIs to build against).
