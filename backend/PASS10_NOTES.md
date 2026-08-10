# Pass 10 — confirmation workflow

## What this pass adds

`Service.requires_confirmation` (stored since Pass 0, unenforced until
now) finally does something: a booking against such a service lands as
`pending` instead of immediately `confirmed`, and an admin explicitly
accepts or declines it — matching Pass 10 in
`docs/CALENDAR_MODULE_PLAN.md`.

```
backend/app/models.py             + Appointment.confirmed_at, status gains "pending"
backend/app/booking_service.py      pending on create; admin_accept/reject_appointment
backend/app/routers/admin_booking.py  + /accept, /reject endpoints
backend/app/routers/public_booking.py  branches notification on pending vs confirmed
backend/app/notification_service.py  + notify_booking_requested/accepted/declined
backend/app/settings_registry.py    + 5 new editable notification templates
backend/tests/test_confirmation_workflow.py  17 new tests
```

## The slot-holding decision (documented per the plan's requirement)

**A `pending` appointment holds its slot**, exactly like a `confirmed`
one. `booking_service._booked_intervals` now selects
`status IN ("confirmed", "pending")` instead of just `"confirmed"`.

This was a decision to make explicitly, not assume silently, and the
plan's own recommendation is the one implemented here: the alternative
— letting a second visitor book the same slot while the first request
is still awaiting approval — is a worse failure mode for a small
business than a slot briefly looking unavailable while a request is
pending. A slot looking taken costs at most a moment of visitor
friction ("that time isn't available, try another"); a slot that
turns out to be double-booked once an admin gets around to reviewing
the pending request costs an actual scheduling conflict, with two
people showing up expecting the same appointment. The former is
strictly the safer default to build in without a specific reason to
choose otherwise, and no such reason surfaced while implementing this
pass.

One consequence worth naming: **rejecting a pending request frees the
slot** (verified by `test_rejecting_frees_the_slot`) — there's no
separate "hold released" step, since a `cancelled` appointment was
never included in `_booked_intervals` to begin with.

## State machine

- `create_appointment`: `status = "pending"` iff a `Service` is given
  and `requires_confirmation` is true; otherwise unchanged
  (`"confirmed"`, byte-identical to Pass 8/9 behavior — the whole
  pre-Pass-10 suite passes with zero fixture changes, confirming this).
  The response gains a top-level `"pending": bool` alongside the
  existing `"ok"`/`"appointment"` keys, so the public form can show
  "request sent" messaging instead of "confirmed" without having to
  infer it from `appointment.status` itself.
- `admin_accept_appointment` / `admin_reject_appointment`: **both valid
  only from `pending`** — anything else (already `confirmed`, already
  `cancelled`) comes back as a typed `"invalid_state"` error, which the
  router turns into a `409 Conflict`, never a generic 500 or a silent
  no-op. This makes a double-accept (e.g. an admin double-clicking, or
  two admins racing on the same request) safe: the second call fails
  cleanly and — since the router only sends a notification after a
  successful state transition — never double-sends the
  accepted/declined email either. That's the concrete mechanism behind
  the plan's "no double-send on retry" requirement; it isn't a
  separate idempotency-key system, it's simply that the notification
  call is downstream of, and gated by, the state transition succeeding
  exactly once.
- `admin_accept_appointment` sets `confirmed_at` to the current UTC
  time. It stays `null` for anything auto-confirmed, so "was this ever
  pending" is reconstructable from the data alone without a separate
  history table — matching how `AppointmentQuestionAnswer` and other
  additions in this plan avoid adding audit tables where the existing
  columns already carry enough signal.
- `admin_reject_appointment` folds an optional `reason` into `notes`
  with a `"[declined] {reason}"` prefix (or bare `"[declined]"` when no
  reason is given) rather than adding a new column — the plan calls
  this out explicitly as "consistent with keeping the schema lean," and
  a decline reason genuinely is just another note on the appointment,
  not a new first-class concept that needs its own field, index, or API
  shape.
- **Self-service cancel and reschedule work unchanged on `pending`
  rows** — neither `cancel_appointment` nor `reschedule_appointment`
  needed any code change at all, since neither ever gated on
  `status == "confirmed"` specifically; they already only special-cased
  `"cancelled"`. A visitor can still withdraw or move a request they
  haven't heard back on. Rescheduling a pending appointment leaves it
  pending — reschedule isn't itself an implicit acceptance.

## Notifications

Three new triggers, following the existing template-driven,
best-effort-and-never-raises convention:

- `notify_booking_requested` — **organizer-facing only**. Reuses the
  same internal-alert channel as the existing new-booking staff alert
  (`templates.booking_requested_admin_alert`, English-only by default,
  same as `templates.new_booking_admin_alert`) — nothing goes to the
  attendee yet, since nothing about their appointment is settled.
- `notify_booking_accepted` — attendee-facing, i18n, follows the exact
  same `_notify_booking` helper as confirmed/cancelled/rescheduled.
- `notify_booking_declined` — attendee-facing, i18n, but **couldn't**
  reuse `_notify_booking` as-is: it's the only booking notification
  whose template needs an extra `{reason}` placeholder. Rather than add
  an optional `reason` parameter to the shared helper (which every
  other call site would need to remember to omit), it's a small
  dedicated function. The reason is pre-formatted into a ready-to-drop
  clause (`" Reason: {reason}"` or `""`) before templating, so the
  template itself stays a plain `.format()` target with no conditional
  logic embedded in admin-editable copy.

All three, plus the two new email/WhatsApp template pairs, are added to
`settings_registry.py` following the exact existing pattern — nothing
about a template's wording is hardcoded in Python.

## Tests

`tests/test_confirmation_workflow.py` (17 tests) covers: pending
creation and its `confirmed_at=null`/`pending=true` shape, a
non-confirmation service and a no-service booking both staying
byte-identical to Pass 8/9, a pending appointment holding its slot
(second booking on the same slot rejected), accept transitioning to
confirmed with `confirmed_at` stamped, reject transitioning to
cancelled with the `[declined]` note (with and without a reason),
both accept and reject rejecting non-pending state with a 409 (covering
double-accept, double-reject, and accept-on-an-already-confirmed
appointment as three separate cases), 404s on unknown appointment ids,
auth enforcement, rejecting freeing the slot back up, self-service
cancel and reschedule both working on a pending row (reschedule
confirmed to leave it pending, not silently confirm it), and the admin
list's `status_filter=pending` returning only pending rows alongside a
confirmed one from a different service.

Following the same discipline established in Pass 9: full suite run
four times in default (alphabetical) execution order — **211 passed**
consistently (194 + 17 new) — and once more in reversed file order to
check for new cross-file collisions. None were introduced by this
pass; the only failure in reversed order is the same pre-existing
`test_notifications.py`/`test_leads.py` collision already documented
in `PASS9_NOTES.md` as a known, unrelated, out-of-scope issue.

## Explicitly not in this pass

Pass 11 (webhooks — `booking.accepted`/`booking.declined`/
`booking.requested` are already on the planned event allow-list from
the original design), Pass 12 (calendar sync), and Pass 13 (the admin
UI for accept/reject — `AppointmentsPage.jsx` doesn't yet show a
pending queue or accept/reject buttons; that's bundled into Pass 13
alongside Availability, Webhooks, and Calendar Sync UI, per the plan).
