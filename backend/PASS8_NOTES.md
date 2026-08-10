# Pass 8 — Services in the public booking flow

## What this pass adds

The piece Pass 0 deliberately deferred: the Service catalog (Pass 0)
now actually drives the booking a visitor makes. `Appointment` gains a
`service_id`, slot generation uses each service's own duration and
buffer time instead of the one global slot length, a visitor can
answer a service's custom intake questions, and the public booking
form + admin appointment list both surface it.

```
backend/app/models.py           + Appointment.service_id, AppointmentQuestionAnswer
backend/app/booking_service.py    rewritten: buffer/overlap-based slot math, service-aware
backend/app/routers/public_booking.py  + GET /services, service_id + answers on booking
backend/tests/test_booking_services_integration.py  14 new tests

src/api/client.js                 + getServices(), getSlots(date, serviceId)
src/components/booking/SlotPicker.jsx   + serviceId prop
src/components/booking/NewAppointmentForm.jsx  service picker + dynamic question fields
src/data/content.js               new copy keys, en + ar

admin/src/pages/AppointmentsPage.jsx   service_name column, expandable answers row
```

## The slot-math change, and why it had to be a real rewrite

Before this pass, `available_slots` didn't do interval math at all — it
generated a fixed grid from `booking.slot_minutes` and checked for an
*exact time-string match* against already-booked appointments. That
only worked because every booking was, structurally, the same length.
The moment a service can have its own duration and buffer, "is 10:00
free" stops being a set-membership question and becomes "does a
10:00-10:45 booking, with its buffers, overlap anything else that
day" — so `booking_service.py` now tracks each booked appointment as a
`(start, end)` interval in minutes (buffers baked in) and checks
real overlap, not string equality.

**This was written to be provably backward-compatible, not just
probably.** When `service_id` is omitted, `_duration_and_buffers`
returns exactly what the old code effectively assumed
(`booking.slot_minutes`, 0, 0) — and with equal-length back-to-back
grid slots and zero buffer, the new overlap check reduces to exactly
the old exact-match check (two grid-aligned slots of the same length
either coincide exactly or don't overlap at all). `test_booking.py`'s
entire existing suite — written against the old exact-match behavior —
passes unmodified against the new implementation, and
`test_slots_without_service_id_unchanged_default_behavior` in the new
test file asserts the same 16-slot, 09:00–16:30 result directly. The
new interval math earns its keep once buffers or non-default durations
enter the picture (Deep Dive vs Quick Chat, buffer-blocking tests), but
introduces zero behavior change when they don't.

A closing-time check was added alongside this
(`end_min > day_end_minutes` is skipped) that didn't exist before —
harmless for the default case (grid step already guarantees this) but
now actually matters once a service's duration can outgrow the
step it's offered on (a 90-minute service starting at 15:30 with a
30-minute grid step correctly disappears once it would run past
17:00).

## `service_id` is optional everywhere, on purpose

Every public endpoint still works with no `service_id` at all — a
booking made this way behaves exactly as Pass 7 and earlier left it:
one grid-length slot, the old free-text "service" field, no custom
questions. This isn't a compatibility shim to be removed later; it's
the permanent behavior for a site that has never defined a Service,
mirroring the same "works with zero configuration" principle the rest
of this codebase follows (e.g. `SiteSetting` rows only exist once
something's actually been configured).

## Custom-question answers

`AppointmentQuestionAnswer` stores a **denormalized copy of the
question's label** at booking time (`question_label`), not just a
`question_id` foreign key. If an admin later edits or deletes that
question, the historical answer on an old appointment still reads
sensibly instead of turning into a dangling id or a blank field —
the same reasoning `ContentPageVersion` already applies to content
edits. `question_id` is kept too (nullable, `SET NULL` on delete) so a
future UI *can* still cross-reference the live question when it still
exists, but nothing depends on it being present.

Validation happens once, server-side, in `create_appointment` — never
trusting that the public form enforced `required` correctly: unknown
`question_id`s are rejected (`invalid_question`), and any required
question without a non-empty answer is rejected
(`missing_required_answer`), regardless of what the client sent.

## Public booking form

`NewAppointmentForm.jsx` fetches the service catalog on mount. If it's
empty (a site that hasn't defined any services yet), the form falls
back to exactly its old shape — free-text "service" field, no
questions — so an existing install isn't forced to configure services
before booking works again. If there's exactly one service, it's
pre-selected rather than making the visitor choose from a list of one.
Switching services clears any already-picked date/slot, since a
different service can mean different duration/buffers and a
previously valid slot may no longer be — silently keeping a stale slot
selection would be worse than asking the visitor to repick.

`SlotPicker.jsx` takes an optional `serviceId` and refetches whenever
either it or the date changes.

## Admin appointment list

`AppointmentsPage.jsx`'s Service column now prefers `service_name`
(the catalog name) over the legacy free-text `service` field, falling
back to it when there's no `service_id`. Rows with custom-question
answers become clickable, expanding an inline row rather than opening
a modal — kept lightweight since this is supplementary detail, not the
primary thing an admin scans the table for.

## Tests

`tests/test_booking_services_integration.py` (14 tests) covers: public
service listing excludes inactive services, unmodified default slot
behavior with no `service_id`, 404 on unknown/inactive `service_id`,
longer-duration services correctly losing slots that would run past
closing, buffer time blocking adjacent slots on both sides, two
different-duration services not falsely colliding, invalid-service
rejection on create, full question-answer round-trip, missing-required
and unknown-question rejection, the legacy no-`service_id` path still
working, reschedule preserving the original service, and the admin
list surfacing `service_name`. Full suite: **174 passed** (up from
160), run three times back-to-back to confirm no order-dependent
flakiness.

One thing this surfaced worth naming: the new test file initially had
two bugs from date-handling and test-isolation assumptions —
neighboring `min_days_ahead` values aliasing onto the same following
Monday across a weekend gap, and a default service name colliding with
`test_services.py`'s slug-uniqueness assumption across the shared
session-scoped test database. Both are fixed (a `_nth_future_workday`
generator replacing offset-based dates; a file-local default name that
doesn't collide with other test files), but they're a reminder that
this test suite's session-scoped shared database means new test files
implicitly share state with every other test file — something to
watch for in future passes.

## Explicitly not in this pass

Everything from Pass 9 onward in `docs/CALENDAR_MODULE_PLAN.md` —
real `AvailabilityRule`-based hours (still the four global `booking.*`
settings), the confirmation workflow (`requires_confirmation` is
stored on `Service` but not yet enforced — every booking is still
`confirmed` immediately), webhooks, and calendar sync. Payment
(`payment_required`) likewise remains stored-but-unenforced.
