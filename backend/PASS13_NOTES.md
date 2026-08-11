# Pass 13 — admin UI catch-up

## What this pass adds

The admin surface for everything Passes 9–12 built API-only:
availability, confirmation, webhooks, and calendar sync. Per explicit
direction on this pass, the functional scope follows the plan's own
notes, but the *shape* of the UI deliberately deviates from a literal
reading of "one page per pass" — see below.

```
admin/src/pages/WebhooksPage.jsx + .css          new page + nav item
admin/src/components/WebhookDetailPanel.jsx/.css  CRUD + secret reveal + delivery log
admin/src/components/CalendarSyncConnector.jsx/.css  embedded in Settings, not a standalone page
admin/src/pages/SettingsPage.jsx                  + calendar_sync label, renders the connector
admin/src/pages/AppointmentsPage.jsx/.css         pending filter + accept/decline
admin/src/styles/global.css                       + status-pill.pending
admin/src/api/client.js                           + webhooks, calendar-sync, accept/reject methods

backend/app/settings_registry.py    + notifications.admin_alert_whatsapp_number, its template
backend/app/notification_service.py  notify_booking_requested sends via whichever channel(s) configured
backend/tests/test_confirmation_workflow.py  + 1 test for the above
```

## Four specific requirements, and how each was resolved

**"Create settings in admin section."** Wherever a requirement was
genuinely a configuration value rather than a resource to manage, it
went into the settings registry, not a bespoke page — the existing
generic `SettingsPage.jsx` already renders any `SettingDef` with zero
per-field code (that's the whole point of the registry architecture
described in `settings_registry.py`'s own module docstring). Nothing
new had to be built for `features.calendar_sync_enabled`,
`booking.calendar_sync_fail_open`, or the `calendar_sync.*` OAuth
credentials — they started showing up in Settings the moment Pass 12
registered them.

**"Working days & hours as total available days & hours."** This pass
deliberately does **not** build a per-weekday `AvailabilityRule` editor
(no `AvailabilityPage.jsx`, contrary to what the original plan
sketched for this pass). The existing `booking.workdays` /
`day_start_hour` / `day_end_hour` settings — already rendering in
Settings → Booking since Pass 1 — are treated as the entire admin
surface for hours. This isn't a shortcut so much as a direct
consequence of Pass 9's own fallback design: `booking_service.py`
only switches to the `AvailabilityRule`-based model once at least one
rule exists anywhere; as long as the admin UI never creates one, the
system stays on the simple "one set of total open days and hours"
path for good, which is exactly what was asked for. The
`AvailabilityRule` backend (weekly overrides, date closures,
per-service hours) still exists and is still fully usable via the API
for anyone who needs it later — this pass just doesn't expose a UI for
it, on purpose.

**"Google Calendar sync is optional."** `features.calendar_sync_enabled`
defaults to `False` and is a plain settings toggle, same as
`features.booking_enabled`. The connection itself lives inside the
Settings page too — `CalendarSyncConnector.jsx` renders below the
`calendar_sync.*` fields when that category is open, following the
*exact* pattern `ThemePresetPicker.jsx` already established for the
`theme` category: a composite widget embedded in the generic settings
form, not a parallel page competing with it. The OAuth round-trip
itself needed one real design decision:

- `calendar_sync.google_redirect_uri` is configured to point at the
  Settings page itself (`/admin/settings/calendar_sync`), not at the
  raw backend `/admin/api/calendar-sync/callback` endpoint. Google
  redirects the browser back into the SPA with `?code=&state=` still
  attached to a normal admin route; `CalendarSyncConnector` picks
  those up on mount and completes the exchange with a same-origin
  `fetch()` call to the (unchanged, already-tested) backend `/callback`
  endpoint, then strips the query params from the URL so a page
  refresh can never try to reuse Google's single-use authorization
  code. This means the admin never lands on a raw JSON response after
  authorizing with Google — they stay inside the dashboard the whole
  time, and no backend endpoint or its test coverage needed to change
  to make that true.
- Disconnect, status, and the calendar picker (shown once, right after
  a successful connect) reuse existing button/pill/select styles —
  `status-pill confirmed`/`cancelled` for connection state,
  `row-action danger` for disconnect, `btn-primary` for the two
  primary actions — nothing new invented.

**"Confirmation is configurable."** Already true before this pass —
`Service.requires_confirmation` has had a checkbox in
`ServiceDetailPanel.jsx` since Pass 0. Nothing changed here; it's
called out because it's easy to assume this pass needed to add it and
it didn't.

**"Confirmation is either by email or WhatsApp, whichever is
configured."** This was a genuine backend gap, not a UI one:
`notify_booking_requested` (the staff-facing "a booking needs your
confirmation" alert) only ever supported email —
`notifications.admin_alert_email` was the sole channel, with no
WhatsApp equivalent even though every *attendee*-facing notification
already had both. Fixed by adding
`notifications.admin_alert_whatsapp_number` and a matching WhatsApp
template, then rewriting `notify_booking_requested` to attempt each
channel independently: email if `admin_alert_email` is set, WhatsApp
if `admin_alert_whatsapp_number` is set (and
`notifications.whatsapp_enabled`), either, both, or neither — never
an all-or-nothing choice, and one channel failing or being
unconfigured never blocks the other. Both settings already render
automatically in Settings → Notifications, no new frontend code
required for the toggle itself.

## Webhooks page

`WebhooksPage.jsx` + `WebhookDetailPanel.jsx` follow the
`ServicesPage.jsx`/`ServiceDetailPanel.jsx` master-detail layout
exactly (same grid proportions, same sticky detail panel, same
create/edit split) — deliberately not a new layout paradigm for a
resource that's structurally identical in shape (a list you select
into, with a form and some sub-list underneath). The event checklist
uses the fixed six-string allow-list from `webhook_service.py`
directly rather than free text, so an admin can't create a
subscription to a typo'd event name that will silently never fire.
The one-time secret is shown in a highlighted banner (gold, matching
the site's own accent color — reusing `--gold`/`--gold-dim` rather
than introducing a new "success" or "warning" semantic for something
that's neither) with the raw value in a monospace, select-all-on-click
`<code>` block; it disappears the moment the admin navigates away or
selects something else, matching the backend's own "never returned
again" guarantee.

## Appointments: pending queue

`AppointmentsPage.jsx` gained a "Pending confirmation" entry in the
existing status filter dropdown — no new filter UI, just a new valid
value for the one that already existed — and Accept/Decline buttons
that appear only on `pending` rows, styled with the same
`row-action`/`row-action primary`/`row-action danger` classes every
other action button in this app already uses (the `.primary` variant
existed only in `ServicesPage.css` before this pass; moved to the
shared `AppointmentsPage.css` base since three pages now depend on it,
rather than each page maintaining its own copy). Declining prompts for
an optional reason via the browser's native `prompt()` — the same
minimal-native-dialog approach `confirm()` is already used for
elsewhere in this codebase (cancel, deactivate, delete), not a new
modal component for a single optional text field.

## Tests

One new backend test
(`test_pending_request_alert_sent_via_whichever_channel_is_configured`)
covers the WhatsApp-alert channel-selection logic directly — configures
WhatsApp only (email explicitly blank) and asserts exactly one
WhatsApp send with no email attempt. Full suite: **250 passed**
(249 + 1), verified in both default and reversed file execution order.

No new frontend tests — this project has no admin-frontend test
harness (Vitest/RTL) established in any prior pass, so adding one
here would be introducing new testing infrastructure inside a UI pass
rather than exercising an existing one. Correctness here rests on:
`npm run build` succeeding for both the admin and public apps
(catches every real compile/type error), `oxlint` clean except for two
pre-existing, unrelated warnings, and the backend contract these
components call against being already covered by Passes 9–12's own
test suites.

## Explicitly not in this pass

Per-weekday/date-override availability UI (see above — a deliberate,
reasoned scope cut, not a deferral); Office 365/CalDAV (still
unbuilt on the backend, per Pass 12); webhook delivery retry UI (no
retries exist to show — Pass 11's own scope decision); any change to
the public-facing booking site (this pass is admin-only, matching
every prior admin-UI-focused pass in this plan).
