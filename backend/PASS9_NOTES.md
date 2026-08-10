# Pass 9 — real AvailabilityRule model

## What this pass adds

The four global `booking.workdays` / `booking.day_start_hour` /
`booking.day_end_hour` settings are replaced by admin-editable
`AvailabilityRule` rows: recurring weekly hours, one-off date
overrides (holiday closures, extended hours), and optional per-service
overrides of the business-wide default — matching Pass 9 in
`docs/CALENDAR_MODULE_PLAN.md`. Per that plan, this pass is
**backend + admin API only**; the admin UI to edit rules is bundled
into Pass 13 alongside Webhooks and Calendar Sync.

```
backend/app/models.py                + AvailabilityRule
backend/app/availability_service.py    business logic: CRUD + precedence resolution
backend/app/routers/admin_availability.py  admin CRUD + /effective preview endpoint
backend/app/booking_service.py         slot generation now resolves through rules
backend/tests/test_availability.py     20 new tests
```

## The precedence model

A rule is either `weekly` (recurring, tied to a weekday 0–6) or
`date_override` (a specific date). `service_id` null means
"business-wide default"; non-null overrides that default for one
service. `availability_service.effective_ranges` resolves, most to
least specific:

1. service + date override
2. business-wide date override
3. service weekly
4. business-wide weekly

A date-override row can also carry `is_closed=True` — an explicit
closure that wins over whatever a weekly rule would otherwise say for
that date. Weekly rules for the same `(service_id, weekday)` are
checked for time-range overlap at write time (`_check_weekly_overlap`)
and rejected with a 409, so "what's open on Tuesday" is never
ambiguous — a split day (e.g. 09:00–12:00 and 13:00–17:00) is
perfectly fine since those ranges don't overlap each other.

## The legacy-fallback decision, and why it's the right one

`effective_ranges` returns `None` — not `[]` — when **no
`AvailabilityRule` exists anywhere in the database**, and
`booking_service._day_ranges` treats `None` specially: fall back
entirely to the old `booking.workdays`/`day_start_hour`/`day_end_hour`
settings. This means a site that has never touched Availability
behaves *exactly* as it did before this pass — confirmed by the full
pre-existing test suite (`test_booking.py`, the Pass 8 integration
tests) passing unmodified, with zero rule fixtures added to any of
them.

The moment even one `AvailabilityRule` exists anywhere, the switch
flips for good: an unconfigured weekday is now genuinely **closed**,
not silently patched from the legacy settings. This is deliberate, not
an oversight — mixing "some days come from rules, other days fall back
to old settings" per-weekday would make the system's behavior depend on
which days an admin happened to configure first, which is worse than a
clean, well-documented cutover. It's also exactly what
`docs/CALENDAR_MODULE_PLAN.md`'s Pass 9 section describes: "the four
settings stay in the registry but become read-only/deprecated" —
this pass doesn't add a migration script that auto-seeds rules from
the legacy settings (nothing in the plan calls for one to run
automatically), so switching over is an explicit admin action: add
rules, and from that point on rules are authoritative.

## `available_slots` rewrite

Slot generation used to compute one `(day_start, day_end)` range per
day. It now resolves a **list** of `(start_minutes, end_minutes)`
ranges via `_day_ranges` (rules, or the legacy single range as
fallback), grids each range independently via `_grid_slots_for_ranges`
(handles split days without special-casing), and checks whether a
candidate slot's full occupied span — including Pass 8's per-service
buffers — fits inside *any* open range via `_fits_in_ranges`, replacing
the old single `end_min > day_end_minutes` check. With the legacy
single-range fallback, `_fits_in_ranges` reduces to exactly the old
check, so this generalization is free when a site isn't using rules.

## Tests, and what they actually caught

`tests/test_availability.py` (20 tests) covers precedence at every
level (business-wide weekly, per-service weekly, business-wide and
per-service date overrides, split-day ranges, overlap rejection, the
`/effective` preview endpoint), plus two DST-adjacent tests: slot
generation is asserted not to crash or produce duplicate slot labels
across the US Eastern spring-forward gap and fall-back repeated hour,
computed relative to "today" (not hardcoded to a specific year) so the
test stays meaningful whenever it runs.

**This is the part worth being honest about.** Writing these tests
surfaced three real cross-test-isolation bugs, in increasing order of
how far from this pass they turned out to reach:

1. **Weekly rules key off weekday, not date.** Several of this file's
   own tests compute distinct *dates* but derive their weekday from
   them — and weekdays repeat every 5 calls. Two tests landing on the
   same weekday would silently collide over the shared session-scoped
   test database (one test's leftover business-wide rule shadowing
   another's assumption of a clean slate). Fixed with a
   `_clear_weekly_rules` helper called before any test that depends on
   a specific weekday's rule state.

2. **This file's rules leaked into every other file.** Once *any*
   `AvailabilityRule` exists, the legacy fallback switches off
   globally (see above) — correct in production, but it meant that
   after `test_availability.py` ran, every other file in the suite
   that depends on the legacy fallback (most of `test_booking.py`,
   `test_leads.py`, `test_notifications.py`) would silently stop
   getting it, if execution order ever put this file first. Fixed with
   an autouse fixture that deletes every `AvailabilityRule` row
   straight from the DB after each test in this file (bypassing the
   HTTP API entirely, so cleanup never depends on auth state).

3. **This file's dates collided with Pass 8's test dates.** Once (1)
   and (2) were fixed and the suite was stress-tested by running test
   files in *reverse* alphabetical order (not just the default order),
   a third issue appeared: this file's `_nth_future_workday(1..8)`
   window overlapped `test_booking_services_integration.py`'s own
   `_nth_future_workday(1..14)` window — two independently-written test
   files landing on the same real calendar dates and booking
   conflicting appointments there. Chasing this down further, the same
   root cause also existed between the *pre-existing*
   `test_booking.py` and Pass 8's test file (verified: `test_booking.py`
   books on day-offsets 3, 4, and 10, which are exactly
   `test_booking_services_integration.py`'s nth-workdays 3, 4, and 8).
   Fixed by giving each file a disjoint, non-overlapping date window
   (`test_booking_services_integration.py` moved to nth 15–28;
   `test_availability.py` moved to nth 51–59, both with
   `booking.max_days_ahead` widened for the duration of the file via
   an autouse fixture, then restored).

**What's still open, and deliberately not fixed here:** stress-testing
in reverse file order surfaced one more collision — between
`test_notifications.py` and `test_leads.py`, two files that predate
every pass in this plan and were never coordinated with each other
either. This is a genuine, pre-existing, suite-wide pattern (many test
files each defining their own local `_future_workday` helper with
small, uncoordinated offsets) rather than anything introduced by
Passes 8 or 9. **The suite's actual execution mode — default
alphabetical file order, which is what a plain `pytest` invocation and
any real CI run uses — passes reliably**: verified 194 passed across 7
consecutive runs in default order. Fully immunizing the entire test
suite against file-order reshuffling would mean introducing a shared,
centralized date-allocation utility used by every test file — a
reasonable follow-up cleanup, but out of scope for a pass about
availability rules, and a decision that shouldn't be made silently
inside an unrelated pass.

## Explicitly not in this pass

The admin UI for editing rules (`AvailabilityPage.jsx`) — bundled into
Pass 13 per the plan, once Webhooks and Calendar Sync also have stable
APIs to build against. No migration/seeding script exists yet to
auto-populate rules from the legacy settings; an admin (or a future
Pass 13 UI flow) creates the first rule explicitly, which is the
moment the cutover described above takes effect.
