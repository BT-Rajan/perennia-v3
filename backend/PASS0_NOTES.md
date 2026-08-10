# Pass 0 — Calendar module: Services in the admin

## What this pass adds

The first slice of the calendar module described in
`docs/CALENDAR_MODULE_PLAN.md` (Pass 8 there — this is the admin-only
foundation it depends on, done first and named Pass 0 since it precedes
and unblocks that numbered plan). An admin can now define **Services**
— Cal.com/`calendar-sample` calls these "event types" — each with its
own duration, buffer time, location type, confirmation requirement, and
a set of custom intake questions:

```
backend/app/models.py               + Service, ServiceCustomQuestion
backend/app/services_service.py       business logic (mirrors content_service.py)
backend/app/routers/admin_services.py admin CRUD, prefix /admin/api/services
backend/tests/test_services.py        17 tests

admin/src/pages/ServicesPage.jsx       list + create/select
admin/src/components/ServiceDetailPanel.jsx  edit form + question editor
```

## Scope: admin-only, on purpose

This pass adds the **Service catalog**, not a booking flow change.
`app/booking_service.py` and the public `/api/booking/*` routes are
untouched — the public site still books against the single implicit
service it always has. `Appointment` does not yet have a `service_id`.
That wiring is deliberately deferred to its own follow-up slice rather
than bundled here, for the same reason every other pass in this
codebase stays narrow: a schema change to `Appointment` (even an
additive, nullable one) touches the booking flow every visitor goes
through, and deserves its own migration, its own test pass against
`booking_service.py`'s slot math, and its own review — not to ride
along with an admin-only CRUD screen. `docs/CALENDAR_MODULE_PLAN.md`
§2.4 (Pass 8) still describes that follow-up in full; nothing in it
changes as a result of this pass except that its foundation now exists.

## What was built, and why it looks like the rest of the codebase

- **`Service`** carries `duration_minutes`, `buffer_before_minutes`,
  `buffer_after_minutes`, `requires_confirmation`, `payment_required`
  (stored, not yet enforced — see the plan's Pass 10/payment notes),
  `location_type` (`in_person | phone | link_provided` — no
  video-conferencing integration; that was evaluated and dropped from
  the whole plan, see `docs/CALENDAR_MODULE_PLAN.md` §2.5), `is_active`,
  `position`, and a `translations` JSON blob following the exact
  `{lang_code: {field_key: str}}` shape `ContentPage` already uses, so
  a later pass can surface a public-facing name/description in the
  same admin pattern editors already know.
- **`ServiceCustomQuestion`** is its own table, not a JSON column on
  `Service` — matches `EventTypeCustomInput` in `calendar-sample`, and,
  same as `FaqItem`/`ContentPage`, needs independent add/remove/reorder
  and a stable id for a future `AppointmentQuestionAnswer` to reference.
- **`services_service.py`** is the only thing that touches these models
  — `admin_services.py` never queries the ORM directly, matching
  `content_service.py`'s split from `admin_content.py`. Every write
  logs to `AuditLog` with `service.*` / `service.question.*` actions,
  the same convention as `content_page.*` / `faq.*`.
- **Slugs** auto-generate from `name` (or an explicit override) via a
  small `slugify()` — no dependency added for something this small —
  and de-duplicate with a `-2`, `-3`, … suffix rather than erroring on
  collision, so an admin naming two services similarly doesn't have to
  hand-pick a slug just to save.
- **Delete is soft-delete only** (`is_active = False`), decided now
  rather than left ambiguous, specifically because the very next slice
  of this plan adds an `Appointment.service_id` FK — a hard-delete
  endpoint added today would just have to be removed once that FK
  exists. `DELETE /admin/api/services/{id}` deactivates; a service and
  its questions stay queryable (`GET /{id}` still 200s) so its history
  isn't lost.
- **Validation lives in two layers on purpose**: Pydantic field
  constraints (`ge=5, le=480` on duration, etc.) reject malformed
  requests at the API boundary with a 422 before any DB work happens;
  `services_service._validate_service_fields` re-checks the same rules
  server-side on every create *and* update (including when a field
  isn't being changed) so a partial `PATCH` can never leave a service
  in an inconsistent state — e.g. shrinking `duration_minutes` below a
  buffer that wasn't touched in that same request.
- **Every route requires `get_current_admin` + `require_csrf`**, same
  as every other admin router — no new auth path introduced.

## Admin UI

`ServicesPage.jsx` follows the `LeadsPage.jsx` master/detail layout:
a table on the left, a sticky detail panel on the right
(`ServiceDetailPanel.jsx`, styled after `LeadDetailPanel.jsx`) for
both creating a new service and editing a selected one. The question
editor lives inside the same panel, only once a service exists (a
question needs a `service_id`) — add/edit/delete plus up/down reorder
buttons rather than a drag library, matching the plan's "list, not a
fancy widget" scope for a first cut (`docs/CALENDAR_MODULE_PLAN.md`
explicitly makes the same call for Availability in Pass 9).

`DashboardLayout.jsx` gains a "Services" nav entry between Appointments
and Leads; `App.jsx` gains the `/services` route. No changes to
`AuthContext.jsx` or the API client's request wrapper — `adminApi`
just grows nine new methods following the exact fetch-wrapper pattern
every other resource uses.

## Tests

`tests/test_services.py` (17 tests, all passing alongside the existing
143) covers: creation and listing, slug auto-generation and
de-duplication, explicit-slug slugification, Pydantic-level and
service-layer validation rejection (duration/buffer bounds, invalid
`location_type`, blank name), get/update/soft-delete, 404s on unknown
ids, auth enforcement, and the full custom-question lifecycle (add,
update, delete, reorder, reorder-with-unknown-id rejection,
deactivation leaving questions intact). Full suite: **160 passed**.

## Explicitly not in this pass

Public booking-flow integration, `Appointment.service_id`, custom
question answers, and everything from Pass 9 onward in
`docs/CALENDAR_MODULE_PLAN.md` (availability rules, confirmation
workflow, webhooks, calendar sync, the admin UI catch-up for those) —
each stays its own pass, unstarted until this one is reviewed.
