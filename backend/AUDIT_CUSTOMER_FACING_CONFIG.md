# Audit — "every customer-facing item is configurable through admin"

Requested as a direct check against the original project goal, not tied
to a specific pass number. Findings below are from an actual line-by-line
sweep of every component in `src/`, not an assumption.

## What was found

A grep-driven audit of every `.jsx` file in `src/components/` for
hardcoded strings, `aria-label`/`title`/`placeholder` attributes, and
literal brand/year references turned up 8 real gaps:

1. `ChatPage.jsx` footer had a literal `© 2026 Perennia.` — missed when
   every other page's footer was converted to `branding.siteName` +
   `new Date().getFullYear()` back in Pass 3.
2. `NewAppointmentForm.jsx` — 3 client-side validation messages
   hardcoded in English, always, regardless of site language.
3. `NewAppointmentForm.jsx` — when a booking was rejected by the
   backend, the **raw error code** (e.g. `"slot_unavailable"`) was
   displayed verbatim as if it were a sentence.
4. `ManageBooking.jsx` — 3 more hardcoded validation/lookup messages.
5. `ManageBooking.jsx` — cancel and reschedule failures were **silently
   swallowed**: if `res.ok` was false, nothing happened at all. A
   visitor hitting the notice window while cancelling would see no
   feedback and could reasonably conclude the button was broken.
6. `SlotPicker.jsx` — "No availability that day..." hardcoded.
7. Eight `aria-label`/`title` accessibility strings (Close, Back, Send,
   nav landmarks, "go to home," "Assistant is typing") hardcoded in
   English regardless of language — invisible to sighted users, but
   real content read aloud to assistive-technology users.
8. Hero's auto-advance-into-chat timer was a hardcoded `7000`ms
   constant.

## What was added to make these fixable

- `theme.hero_auto_advance_seconds` (new setting).
- `copy.common` (new setting) — shared accessibility labels, bilingual.
- `copy.booking` extended with `id_placeholder`, `no_availability`,
  four `err_*` validation-message keys, and an `errors` object keyed
  by every backend error code the booking API can return
  (`slot_unavailable`, `notice_window_passed`, `not_found`,
  `invalid_email`, `invalid_name`, `invalid_date`, `already_cancelled`,
  `booking_disabled`, `generic`) — so a visitor never sees a raw error
  code again, in either language.

All of the above went into the registry defaults directly (visible via
`/api/config/public` even on a fresh, unseeded database) and into
`scripts/seed_content.py`'s bilingual seed data.

## A second bug, only caught by testing the fix

The first attempt at wiring `copy.booking.errors` through to the
frontend had a bug: `siteContent.js`'s `toCamel()` helper recursively
camelCases every key coming from the backend (so component code can
use `t.bookBtn` instead of `t.book_btn`) — but it was also converting
`errors.slot_unavailable` into `errors.slotUnavailable`. Since
`result.error` from the API is always the raw snake_case backend code,
every lookup silently missed and fell through to the generic fallback
message.

This wasn't caught by code review — it was caught by actually
triggering the failure: booking the same slot from two "visitors"
simultaneously (one via the real UI, one via a direct API call mid-form)
and watching the wrong (generic) message appear. Fixed by excluding the
`errors` object from the camelCase conversion, then re-ran the same
race condition and confirmed the correct, specific message now appears.

## Verified live, end to end

- `npm run build` succeeds, lint clean (0 new warnings).
- 107/107 backend tests still pass.
- Grep sweep across the entire `src/components/` tree for hardcoded
  `aria-label`/`title`/`placeholder`, hardcoded `setError("...")`
  strings, and literal `"Perennia"`/`2026` references: **zero hits**.
- Changed `branding.site_name` via the admin API mid-session and
  confirmed the chat page footer (previously hardcoded) updated live.
- Triggered every client-side validation error through the real UI in
  both English and Arabic.
- Manufactured a genuine slot-collision race condition and confirmed
  the specific translated error message renders (not the generic
  fallback the bug above was producing).
- Manufactured a genuine "too close to cancel" scenario (booked an
  appointment, then raised `booking.min_notice_hours` to the max) and
  confirmed the previously-silent cancel failure now shows the correct
  translated message.

## What's intentionally still static (and why)

- `index.html`'s literal `<title>Perennia</title>` and default meta
  tags — these are the pre-JavaScript fallback values, correctly
  overridden at runtime by `applyTheme.js` once real config loads
  (this was verified in Pass 3, unaffected by this audit).
- The `PRN-XXXXXXXX` placeholder shown in the appointment-lookup field
  is the same in both languages by design — it's demonstrating a
  literal code format (always Latin alphanumeric, per
  `booking_service.py`'s `_CODE_ALPHABET`), not translatable prose.
