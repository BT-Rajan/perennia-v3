# Pass 7 — Admin dashboard UI

## What this pass adds

The first real admin-facing UI — everything before this pass was API
only, verified with curl and pytest. An admin can now actually log in
and manage the site's day-to-day activity: appointments and leads.

```
backend/app/routers/admin_stats.py   GET /admin/api/stats/overview —
                                       aggregates over existing data,
                                       no new tables

admin/                                a SEPARATE Vite + React app
├── src/api/client.js                 session cookie + CSRF header
├── src/context/AuthContext.jsx        login state, session-expiry handling
├── src/pages/
│   ├── LoginPage.jsx
│   ├── DashboardLayout.jsx            sidebar + topbar shell
│   ├── OverviewPage.jsx               stat cards + recent activity
│   ├── AppointmentsPage.jsx           filterable table, cancel action
│   └── LeadsPage.jsx                  filterable table + detail panel
└── src/components/
    ├── StatCard.jsx, PageHeader.jsx
    └── LeadDetailPanel.jsx            status/notes editing, transcript view
```

## Why a separate app instead of a route inside the public site

The public site (`src/`) has no URL-based routing at all — `App.jsx`
just swaps components via `useState`, which is fine for a handful of
marketing pages but wrong for an admin tool that needs deep-linkable
URLs, browser back/forward, and a bookmark-able `/leads`. Rather than
retrofitting real routing onto the public site just for this, `admin/`
is its own Vite project with `react-router-dom` — clean separation,
and a data-dense internal tool has no reason to ship inside the public
marketing bundle anyway. It talks to the exact same backend, just
through its own dev-server proxy (`admin/vite.config.js`, mirroring
the pattern from the public site's `vite.config.js`).

**Production note:** like Pass 3's upload-serving caveat, this needs
the same origin as the backend when deployed (a reverse proxy path
like `/admin/` or a subdomain routed to the same origin) — not solved
yet, tracked for Pass 10 alongside the rest of the deployment topology.

## Design: distinct from the public site, still unmistakably Perennia

The public site is dark, atmospheric, chat-first. An admin tool spends
its time on dense tables and forms, which read far better on a light
surface — so this pass deliberately breaks from the public site's
all-dark look: a fixed navy sidebar for orientation and brand
continuity, a light content area for the actual work. The signature
touch carried through from the public site: appointment and lead IDs
render in a monospace chip everywhere they appear, echoing the
`PRN-XXXXXXXX` confirmation codes visitors receive — a small, quiet,
genuinely useful convention for someone scanning a table of them.

## What each page does

- **Overview** — total leads/appointments, this-week count, and a
  five-item preview of each, linking through to the full lists.
- **Appointments** — status and date-range filters, cancel action (goes
  through the same admin-override endpoint from Pass 4 — no notice-
  window restriction, since an admin cancelling is often exactly a
  late-notice situation).
- **Leads** — status/source filters, click a row to open a detail panel:
  change status, save internal notes, read the full chat/booking
  transcript that captured them, delete the record.

## Verified end to end, in a real browser

Not just built and linted — actually logged in and used:
- Unauthenticated visit correctly redirects to `/login`; login
  succeeds and lands on `/`; the session persists across a full page
  reload (proving the cookie-based session works, not just in-memory
  React state); deep-linking straight to `/leads` via URL works
  without going through the login flow first (real routing); logout
  clears the session and protected routes correctly bounce back to
  `/login` afterward.
- Seeded 3 real appointments and 1 real chat-sourced lead through the
  actual API, then confirmed the Overview page's stat cards and
  activity previews reflect that real data exactly.
- On the Appointments page, cancelled a real appointment through the
  UI and confirmed it dropped out of the "Confirmed" filter view
  immediately — the action round-trips to the backend and the list
  re-fetches correctly.
- On the Leads page, opened the chat lead's detail panel, confirmed
  its transcript shows the actual message that captured it, changed
  its status (watched both the panel and the table row update live),
  and saved notes.
- `npm run build` succeeds for the admin app; lint is completely clean
  (0 warnings — the one long-standing trivial warning in the public
  site's `client.js` doesn't exist here since this is a fresh client).

## Deliberately deferred to later passes

- No settings/content editing UI yet — that's Pass 8's generic,
  registry-driven form renderer. This pass is booking/leads management
  only.
- Only one admin role is meaningfully supported in the UI (role is
  displayed but nothing is gated by it yet) — RBAC enforcement UI is
  Pass 9.
- No audit log viewer, even though every write has been logged since
  Pass 1 — also Pass 9.
- No pagination on the appointments/leads tables — fine at current
  data volumes, worth revisiting if either grows large.
