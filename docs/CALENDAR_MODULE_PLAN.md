# Calendar Module — Feature Inventory & Build Plan

Reference app: [`BT-Rajan/calendar-sample`](https://github.com/BT-Rajan/calendar-sample)
(a Cal.com / Calendso fork — Next.js + Prisma + tRPC)
Target app: `perennia-v2` (FastAPI + SQLAlchemy + Pydantic backend, Vite + React
public site, separate Vite + React admin dashboard)

This document has two parts:

1. **What `calendar-sample` actually does** — a feature inventory, read directly
   out of its Prisma schema, routers, and pages.
2. **How we bring the useful parts into `perennia-v2`** — mapped onto our stack
   and our existing `booking.*` module, delivered as a sequence of passes in
   the style of `backend/PASS1_NOTES.md` … `PASS7_NOTES.md`.

---

## 1. Feature inventory — `calendar-sample`

Derived from `prisma/schema.prisma` (models: `EventType`, `User`, `Team`,
`Membership`, `Booking`, `Attendee`, `BookingReference`, `Schedule`,
`Availability`, `SelectedCalendar`, `EventTypeCustomInput`, `Payment`,
`Webhook`, `ReminderMail`, `Credential`, `DailyEventReference`), the
`server/routers/` tRPC routers, and `pages/`.

### 1.1 Event types
- A user (or team) defines one or more **event types**: title, slug,
  description, length in minutes, a **scheduling type**
  (`ROUND_ROBIN` / `COLLECTIVE` for team events), position/ordering.
- **Period type** controls how far the booking window extends:
  `UNLIMITED`, `ROLLING` (N days from today), or `RANGE` (fixed start/end
  date) — `EventType.periodType` / `periodDays` / `periodStartDate` /
  `periodEndDate`.
- **Buffer time** before/after a booking (`beforeEventBuffer`,
  `afterEventBuffer`), **minimum booking notice**
  (`minimumBookingNotice`), and configurable **slot interval**.
- **Custom booking questions** (`EventTypeCustomInput`): per event type,
  admin-defined extra fields (text / textlong / number / bool / phone),
  each markable required, shown on the public booking page.
- **Location** options per event type (in-person address, phone, Zoom,
  Daily.co video, etc. — `lib/location.ts`), and a **hidden/placeholder**
  flag so an event type can exist without being publicly bookable.
- **Custom event name** template, **custom brand color**,
  **hide-branding** toggle — light per-tenant white-labeling.

### 1.2 Availability
- A **Schedule** is a named, reusable set of weekly working hours; a user
  can have several (e.g. "Default", "Sales hours") and assign a specific
  one per event type, or fall back to their default.
- **Availability** rows are `(day-of-week or date, start time, end time)`
  ranges — supports both recurring weekly rules and one-off date
  overrides.
- Slot generation (`lib/slots.ts`, `pages/api/availability/*`) combines:
  the schedule's open hours, minus already-booked times, minus buffer
  time, minus anything blocked by a **connected external calendar**
  (busy-time lookup), respecting the event type's own timezone and the
  viewer's browser timezone.
- `test/lib/slots.test.ts` / `getWorkingHours.test.ts` cover the slot math
  directly — this is the part of the reference app worth the most care to
  port correctly, since it's pure timezone/interval arithmetic and easy to
  get subtly wrong (DST edges, cross-midnight ranges, etc).

### 1.3 Bookings
- `Booking` records the confirmed appointment: event type, organizer,
  one or more `Attendee`s (each with their own name/email/timezone —
  supports guests), start/end time, `uid` (public confirmation code),
  title, description, `BookingStatus` (`ACCEPTED` / `PENDING` /
  `CANCELLED` / `REJECTED`), and a `rescheduled` link back to the prior
  booking it replaced.
- **Booking requests**: an event type can require organizer confirmation
  before a booking is `ACCEPTED` (vs. auto-confirm) — `PENDING` status +
  organizer accept/reject flow, with its own email templates
  (`organizer-request-email`, `organizer-request-reminder-email`).
- Self-service **cancel** and **reschedule** by the attendee, gated by the
  same notice-window logic as the original booking.
- `BookingReference` rows link a `Booking` to the external artifacts it
  created — a Google Calendar event ID, a Zoom meeting ID — so those can
  be cleaned up / updated on cancel or reschedule.

### 1.4 Team scheduling
- `Team`, `Membership` (`role`: OWNER / MEMBER, plus invite-accepted
  flag), team-level event types with `ROUND_ROBIN` (distributes across
  available members) or `COLLECTIVE` (requires all members free)
  scheduling.
- Team branding: slug, logo, bio, custom brand color; a public
  `/team/[slug]` booking page separate from individual `/[user]` pages.

### 1.5 Calendar & conferencing integrations
- `lib/integrations/`: Google Calendar, Office 365 Calendar, Apple
  Calendar (CalDAV), generic CalDAV — each an adapter implementing
  "list calendars," "get busy times," "create/update/delete event."
- `SelectedCalendar` — which of a user's connected calendars are checked
  for conflicts vs. purely available for writing new events to.
- Video: Zoom and Daily.co adapters (`DailyVideoApiAdapter`,
  `ZoomVideoApiAdapter`) auto-create a meeting link on booking and store
  it on the `Booking`/`DailyEventReference`.
- OAuth `Credential` model stores per-user tokens for each connected
  service; add/callback routes live under
  `pages/api/integrations/{service}/{add,callback}.ts`.

### 1.6 Payments (enterprise/`ee/` folder)
- Stripe: `Payment` model, `PaymentType` enum, checkout + webhook
  handling (`ee/pages/api/integrations/stripepayment/*`) — a paid event
  type isn't confirmed until payment succeeds; refund-on-cancel handling
  with its own failure-notification email.

### 1.7 Notifications
- `lib/emails/templates/`: scheduled / rescheduled / cancelled /
  declined / awaiting-payment, one pair each for attendee and organizer,
  plus a forgot-password email and a team-invite email — all built on a
  shared `lib/emails/templates/common/` layout.
- `ReminderMail` + `pages/api/cron/bookingReminder.ts` — a cron-triggered
  reminder sent ahead of the appointment, deduplicated via a
  `ReminderType` + booking pairing.

### 1.8 Webhooks
- `Webhook` model: per-user, a target URL + subscribed
  `WebhookTriggerEvents` (booking created / cancelled / rescheduled).
  `lib/webhooks/subscriptions.tsx` fires an HMAC-signed payload
  (`lib/webhooks/sendPayload.tsx`) on each event — lets a tenant wire the
  calendar into their own systems without polling.

### 1.9 Account / security
- Auth via `next-auth` (`pages/api/auth/[...nextauth].tsx`), email
  verification, forgot/reset password, **TOTP two-factor auth**
  (`otplib`, `pages/api/auth/two-factor/*`).
- `UserPlan` (FREE / TRIAL / PRO) and a `downgradeUsers` cron —
  subscription-gating that doesn't apply to us but is worth naming so we
  consciously *don't* port it.

### 1.10 Everything intentionally out of scope for us
Multi-tenant SaaS billing (`UserPlan`, Stripe *subscriptions* as opposed
to one-off event payments), the `ee/` licensing split itself, and
`next-auth` as an auth system (we already have our own admin session
model in `app/security.py`) are all artifacts of "this is a
multi-tenant, sign-up-your-own-account product." Perennia is a single
business's site; there's one calendar, not one per signed-up user. We
port the *scheduling* feature set, not the SaaS shell around it.

---

## 2. Mapping onto `perennia-v2`

### 2.1 What we already have
`app/models.py::Appointment` + `app/booking_service.py` is a *complete but
minimal* version of §1.1–1.3 collapsed into a single implicit event type:
one global slot length, one set of business hours, no per-service
duration or location, no organizer confirmation step, no external
calendar sync. `booking.*` in `settings_registry.py` holds the config
that in `calendar-sample` would live on `EventType` + `Schedule`. This is
good news — the slot-generation core (`available_slots`), the
notice-window math, and the confirmation-code pattern don't need to be
rebuilt, only generalized.

### 2.2 Design decisions (deliberately narrower than the reference app)
- **No multi-tenant `User`/`Team` layer.** "Organizer" stays implicit —
  it's the business. What generalizes is **`Service`** (≈ `EventType`
  without the per-user ownership): name, duration, buffer, its own
  optional hours override, its own custom questions, its own
  confirm-required flag. No round-robin/collective scheduling — there's
  one calendar.
- **`Schedule`/`Availability` becomes a single set of weekly hours plus
  date-specific overrides** (holidays, one-off closures, one-off extra
  hours), attached to the business, with an optional per-`Service`
  override — not a per-user library of named schedules.
- **Calendar sync (Google/Office365/CalDAV) and video (Zoom/Daily) are a
  later, explicitly optional pass**, gated behind a `features.*` flag
  exactly like `features.booking_enabled` today — most of the value
  (a real scheduling module instead of a single-service slot picker) is
  delivered before we touch OAuth with a third party.
- **Payments**: only relevant if a `Service` is ever paid; kept as a
  stubbed hook (`payment_required` bool on `Service`) until there's an
  actual product need, rather than importing Stripe subscriptions
  wholesale.
- **Webhooks**: straightforward to port (HMAC-signed POST on
  created/cancelled/rescheduled) and cheap relative to its usefulness —
  early pass, reusing the existing `notification_service.py` event
  points.
- Every new table goes through the same patterns already established:
  `Base`/`Mapped[...]` in `models.py`, config through
  `settings_registry.py` (never a new hardcoded column for something an
  admin should be able to change), admin routes under `/admin/api/...`
  behind `get_current_admin` + `require_csrf`, public routes under
  `/api/...` behind `slowapi` rate limits, audit-logged writes via
  `AuditLog`, and Pydantic request models in the router (matching
  `public_booking.py`'s style) rather than a separate schemas file.

### 2.3 Proposed data model additions
```
Service                 id, name, slug, duration_minutes, buffer_before_minutes,
                         buffer_after_minutes, requires_confirmation, payment_required,
                         is_active, position, translations (JSON, i18n like ContentPage)

ServiceCustomQuestion    id, service_id FK, kind (text/textarea/number/bool/phone),
                         label, required, position

AvailabilityRule         id, kind (weekly|date_override), weekday (0-6, nullable),
                         date (nullable, for one-off overrides), start_time, end_time,
                         is_closed (bool — an override can also mark a date fully closed)
                         [replaces the single booking.workdays/day_start_hour/day_end_hour
                          settings with data an admin edits as rows, same spirit as the
                          content_page -> content_page_version pattern already in use]

Appointment              (existing table) + service_id FK, status gains "pending"
                         alongside confirmed/cancelled, confirmed_at

AppointmentQuestionAnswer id, appointment_id FK, question_id FK, answer (text)

Webhook                  id, url, secret, events (JSON list), is_active
WebhookDelivery           id, webhook_id FK, event, payload (JSON), response_status,
                         attempted_at   [audit trail for the admin UI, mirrors AuditLog]
```

### 2.4 Passes
Each pass is scoped the way the existing `PASS*_NOTES.md` files are:
backend-first, its own tests, its own `PASSn_NOTES.md` explaining what
changed and why, admin UI catching up once the API is stable. Numbering
continues from the existing `PASS7_NOTES.md` (admin dashboard UI).

**Pass 8 — Services (multi–event-type foundation)**
- `Service` + `ServiceCustomQuestion` models, admin CRUD
  (`admin_services.py`), public `GET /api/booking/services`.
- `booking_service.available_slots` gains a required `service_id`,
  duration/buffer come from the `Service` row instead of the global
  `booking.slot_minutes` setting; `booking.slot_minutes` becomes the
  *default* duration only.
- `Appointment.service_id` (nullable during migration, backfilled to a
  synthetic "General" service so existing rows stay valid).
- Custom questions rendered on the public booking form, answers stored
  in `AppointmentQuestionAnswer`, shown in the admin appointment detail.
- Tests: slot generation per service (different durations don't collide
  in ways the shared-slot model didn't have to worry about), custom
  question validation (required-field enforcement server-side, not just
  client-side).

**Pass 9 — Real availability model**
- `AvailabilityRule` replaces `booking.workdays` / `day_start_hour` /
  `day_end_hour`; migration seeds one weekly rule per current workday
  from the existing settings so behavior is unchanged on upgrade.
- Date overrides (holiday closures, one-off extended hours) — admin UI
  is a simple calendar-style list, not a full month grid yet.
- Optional per-`Service` override of the weekly rules (falls back to the
  business-wide rules when absent).
- `available_slots` rewritten against `AvailabilityRule` instead of the
  settings dict; this is the highest-risk pass for regressions, so the
  existing `test/lib/slots`-equivalent coverage (`tests/test_booking.py`)
  gets extended with explicit DST-boundary and cross-midnight cases
  before the cutover, not after.

**Pass 10 — Confirmation workflow**
- `Service.requires_confirmation`; when set, a new booking lands as
  `pending` instead of `confirmed`, doesn't occupy the slot as fully
  booked (or does, per a config choice — needs a product decision
  documented in this pass's notes), and triggers an organizer-facing
  "new request" notification instead of "booking confirmed."
- Admin accept/reject actions in `admin_booking.py`, each with its own
  notification template following the existing pattern in
  `notification_service.py`.

**Pass 11 — Webhooks**
- `Webhook` + `WebhookDelivery`, admin CRUD + delivery log view.
- Fire on the same three events `notification_service.py` already
  reacts to (booking confirmed / cancelled / rescheduled) plus the new
  request/accept/reject events from Pass 10 — HMAC-SHA256 signature
  header, matching `calendar-sample`'s pattern, verified in tests with a
  local HTTP stub rather than a real external endpoint.

**Pass 12 — External calendar sync (opt-in)**
- Google Calendar first (broadest reach), behind
  `features.calendar_sync_enabled`: OAuth credential storage (encrypted
  the same way `SiteSetting.is_secret` fields are — via
  `security.py`'s Fernet helper, not a new secret-handling path),
  busy-time lookup folded into `available_slots`, and optional
  event-creation on confirm.
- Office 365 / CalDAV considered only if there's an actual business need
  once Google sync is live — no work done speculatively.

**Pass 13 — Video conferencing (opt-in)**
- One adapter (Zoom or a simpler Jitsi/Daily link, TBD by what the
  business actually uses) auto-attached to confirmed bookings for
  services flagged as remote; link included in the confirmation email
  and the admin appointment detail.

**Pass 14 — Admin UI catch-up**
- `admin/src/pages/ServicesPage.jsx`, `AvailabilityPage.jsx`,
  `WebhooksPage.jsx`, and an upgraded `AppointmentsPage.jsx` (service
  filter, pending-confirmation queue, custom-question answers in the
  detail panel) — mirrors how Pass 7 followed the earlier
  backend-only passes once there was a stable API surface to build a UI
  against.

### 2.5 Explicitly deferred / not planned
Team/round-robin/collective scheduling, multi-tenant `User` accounts,
`UserPlan` billing tiers, and TOTP 2FA for a *booker* (as opposed to the
admin 2FA which is a separate, already-tracked backlog item) — all stay
out of scope unless a real requirement appears, per the same "don't
build the sprawl" philosophy `models.py`'s own docstring already states
for `SiteSetting`.
