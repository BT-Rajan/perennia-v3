# Pass 2 — Content system + frontend wiring

## What this pass adds

Pass 1 built the settings foundation. Pass 2 adds a second, complementary
system for *structured, repeatable* content (pages, FAQ), and — for the
first time — actually connects the React frontend to the backend.

```
backend/app/
├── content_schema.py      field schemas for pages & FAQ (same "declare
│                            once" idea as settings_registry.py, for
│                            list-shaped content instead of scalars)
├── content_service.py      CRUD + versioning for pages/FAQ
├── models.py                + ContentPage, ContentPageVersion, FaqItem
└── routers/
    ├── admin_content.py     admin CRUD, page version history, rollback
    └── public_content.py    read-only pages/FAQ for the frontend

backend/scripts/
└── seed_content.py          migrates the old hardcoded content.js/
                               pages.js/*.md strings into the DB once

src/
├── api/publicContent.js     calls to /api/config/public, /api/content/*
├── data/siteContent.js      normalizes API data OR bundled fallback
│                              into one shape every component consumes
├── context/LangContext.jsx  loads from the backend, instant-fallback
│                              first paint, silent upgrade on fetch
└── components/...           Hero, ContentPage, ContactPage now read
                               pages/nav/sections from useLang() only
```

## Why pages got their own system instead of more registry entries

Settings (Pass 1) are named, singular values — `branding.site_name` is
always exactly one thing. Pages and FAQ items are *lists of records* an
admin adds, removes, and reorders, and pages specifically needed
version history for safe rollback. Forcing that into the scalar
registry would mean a synthetic "list of JSON blobs" setting with no
real per-record validation or versioning — so `content_schema.py` /
`content_service.py` exist as a sibling system that reuses the same
philosophy (declare the field shape once, validate everything against
it) rather than duplicating registry code for a shape it wasn't built for.

One design consequence worth calling out: what used to be **three**
separate hardcoded JS structures for the same four pages — `NAV` (menu
label), `SECTIONS` (home-page teaser), and `PAGE_META`/`PAGE_CONTENT`
(tagline + full body) — are now **one** `ContentPage` record per page.
An admin editing "About" edits it once, not in three different places
that have to stay in sync.

## Frontend: nothing is hardcoded content anymore

Every component that used to import `COPY`, `NAV`, `SECTIONS`, `FAQ`,
`PAGE_META`, or `PAGE_CONTENT` directly now reads exclusively from
`useLang()`. `src/data/siteContent.js` is the only file that knows
those old modules still exist — it uses them purely as an **offline
fallback** (same pattern already established in `api/client.js`'s
`tryFetch`, extended here to content):

- First render is instant and uses bundled fallback content (no
  loading spinner, no flash of empty UI).
- A background fetch to `/api/config/public` + `/api/content/pages` +
  `/api/content/faq` then silently upgrades the page to live,
  admin-editable content if the backend is reachable.
- If the backend is down, the site keeps working off the fallback —
  degrades gracefully rather than breaking.

Concretely fixed hardcoded spots along the way:
- `Hero.jsx`'s quick-link cards used a hardcoded 4-id array; now
  derived from whichever pages are configured to show in the nav, in
  whatever order the admin sets.
- `App.jsx`'s page router used a hardcoded list of "content-page" ids;
  now any page id that isn't `home`/`chat`/`contact` automatically
  routes through the generic `ContentPage` — an admin adding a 5th page
  needs zero frontend code changes.
- The footer's site name and copyright now read `branding.siteName`
  instead of a literal `"Perennia"`.
- UI microcopy (chat header, booking labels, home tagline, etc.) all
  comes from the `copy.*` registry entries added this pass, including
  the booking flow's confirmation messages — stored as
  `{id}`/`{date}`/`{time}` templates server-side (functions aren't
  JSON-serializable) and rehydrated into callables client-side in
  `siteContent.js`, so `BookingPanel`/`ManageBooking` needed no changes.

## Verified working end to end

- 35 backend tests pass (19 new: page CRUD/validation/versioning/
  rollback/visibility, FAQ CRUD/reorder/active-filtering, i18n setting
  merge/validation).
- `npm run build` succeeds; `oxlint` clean.
- Headless-browser smoke test against the real dev server + real
  backend: home page renders live DB content, Arabic toggle correctly
  flips `dir`/`lang` and re-renders every string from the backend's
  Arabic translations, Products/Contact pages render live markdown,
  zero console/page errors.
- Live-edit test: changed `branding.site_name` via the admin API while
  the frontend was open, reloaded, and the new name appeared in the
  footer — confirming the pipeline is genuinely live, not just built
  against a fixture.

## Running it

```bash
# Backend
cd backend
python scripts/init_db.py       # if not already done
python scripts/seed_content.py  # idempotent — seeds pages/FAQ/copy once
uvicorn app.main:app --reload --port 8001
pytest -q                        # 35 tests

# Frontend (separate terminal)
npm install
npm run dev                      # proxies /api to the backend on :8001
```

With the backend not running, `npm run dev` still works — the frontend
falls back to bundled content automatically.

## Deliberately deferred to later passes

- Theming (colors/fonts/logo upload) is still only the two placeholder
  color settings from Pass 1 — Pass 3.
- No admin UI yet for any of this — it's all API-only until Pass 8's
  generic settings/content forms (thoroughly tested via the API in the
  meantime).
- `document.title` doesn't yet follow `branding.site_name` dynamically
  (still the static value in `index.html`) — small enough to fold into
  Pass 3 alongside favicon/logo wiring.
