# Pass 4 — Appointment booking

## What this pass adds

A real booking backend replacing the frontend's in-memory mock, plus
the settings that make every business rule of it admin-configurable.

```
backend/app/
├── settings_registry.py    + booking.* (timezone, slot length, hours,
│                              workdays, max days ahead, notice window)
├── models.py                 + Appointment
├── booking_service.py        slot generation, availability, create/
│                              lookup/cancel/reschedule, all driven by
│                              booking.* settings
└── routers/
    ├── public_booking.py      /api/booking/slots, /appointments,
    │                            /lookup, /cancel, /reschedule
    └── admin_booking.py       /admin/api/booking/appointments (list,
                                 filter), admin-override cancel

src/
├── api/client.js             booking calls now hit the real backend
│                              (same function signatures — no component
│                              changes needed), mock kept as offline fallback
├── data/siteContent.js       + features.* (booking/chat/whatsapp
│                              enabled flags) exposed to components
└── components/
    ├── chat/ChatPage.jsx      "Talk to Us" hidden when booking disabled
    └── pages/ContactPage.jsx  same
```

## Business-logic decisions worth flagging

- **Expected outcomes vs actual errors.** Booking actions (create,
  cancel, reschedule) return HTTP 200 with `{ok: false, error: "..."}`
  for anything a normal user might hit — a slot just taken, insufficient
  notice, appointment not found — because those are expected, common
  outcomes, not exceptional ones. Only genuinely malformed requests
  (bad JSON, missing fields) or rate-limit hits use real HTTP error
  codes. This matters concretely for the frontend: `api/client.js`'s
  existing fallback pattern treats any non-2xx response as "backend
  unreachable, use the mock" — if slot-taken were a 409, a real
  business rejection would get silently swallowed into a fake mock
  success instead of showing the person what actually happened.
- **Notice window applies to the OLD appointment for reschedule**, not
  the new one — you need enough lead time to change your existing
  booking, same as cancelling it; the new slot's own future-dated
  availability is checked separately.
- **Admin cancel bypasses the notice window** on purpose — the whole
  point of an admin needing to cancel is often exactly a late-notice
  situation the visitor can no longer self-serve.
- **Confirmation codes exclude `0/O/1/I`** (`PRN-XXXXXXXX` from a
  32-character alphabet) so a code read aloud or typed by hand doesn't
  hit visually-ambiguous characters.
- `day_start_hour`/`day_end_hour` aren't cross-validated against each
  other at write time (the settings registry validates one key at a
  time). If an admin somehow leaves end ≤ start, `booking_service`
  treats that day as having zero slots rather than crashing a request —
  documented directly in the registry entry.

## Verified end to end

- 68 backend tests pass (22 new): slot math for the default schedule,
  weekend/too-far-ahead exclusion, double-booking prevention, notice-
  window enforcement on cancel/reschedule, idempotent cancel, admin
  override, and settings validation (bad timezone, out-of-range
  workdays, slot length).
- A standalone test (own process, real rate limit) confirms booking
  endpoints actually 429 after 6 requests/hour.
- **Full real-browser test**, not just API calls: opened the chat page,
  clicked "Talk to Us," picked a date, watched the slot picker fetch
  real availability from the backend, filled out and submitted the
  form, and got back an actual confirmation code rendered through the
  templated success message from Pass 2 — zero console errors.
- Same for the manage-booking flow: looked up that real appointment by
  code + email, cancelled it, watched the slot re-appear in
  availability.
- Toggled `features.booking_enabled` off via the admin API mid-session
  and confirmed the "Talk to Us" button disappeared from the chat page
  on reload — the feature flag genuinely gates the UI, not just the API.

## Deliberately deferred to later passes

- No admin UI for viewing/managing the calendar yet — `/admin/api/
  booking/appointments` is fully functional and tested, just API-only
  until Pass 7's dashboard.
- Google Calendar sync and email/WhatsApp confirmations (the reference
  app has both) are Pass 6's job — right now a booking is confirmed
  in-app only, no external notification fires yet.
- No admin UI for entering leave days / holidays on top of the regular
  weekly `workdays` pattern — worth a future pass if needed; the
  current model only expresses a repeating weekly schedule.
