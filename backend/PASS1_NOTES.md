# Pass 1 — Backend foundation

## What this pass adds

A new `backend/` — a Python (FastAPI) service that sits alongside the
existing React frontend and replaces the PHP stubs referenced in
`src/api/client.js`. Nothing in the frontend is wired up to it yet —
that starts in Pass 2, once there's real content to connect it to.

```
backend/
├── app/
│   ├── config.py            infra-only settings (secrets, DB URL) — env-sourced
│   ├── db.py                 SQLAlchemy engine/session, dialect-agnostic
│   ├── models.py              AdminUser, AdminSession, SiteSetting, AuditLog
│   ├── settings_registry.py  ★ single source of truth for every configurable field
│   ├── settings_service.py   get/set settings through the registry
│   ├── security.py            bcrypt, session signing, CSRF, Fernet encryption
│   ├── deps.py                 auth/CSRF FastAPI dependencies
│   ├── rate_limit.py
│   ├── main.py                 app factory, middleware, router wiring
│   └── routers/
│       ├── admin_auth.py       login / logout / me
│       ├── admin_settings.py   generic settings CRUD (category-based)
│       └── public_config.py    read-only, non-secret config for the frontend
├── scripts/
│   ├── gen_secrets.py          generates SECRET_KEY / ENCRYPTION_KEY / admin hash
│   └── init_db.py               creates tables + bootstraps first admin
└── tests/                       16 passing tests + a standalone rate-limit check
```

## The core idea: one registry, not N features

The reference repo hardcodes each setting as its own env var / JSON field
/ admin form field / route — which is why `main.py` is 57KB and
`admin.html` is 100KB of repeated patterns. Here, **every** configurable
value (this pass: branding, contact, locale, base theme colors, feature
toggles — more arrive each pass) is one entry in
`app/settings_registry.py`:

```python
SettingDef("branding.site_name", "branding", "Site name", SettingType.STRING, "Perennia")
```

That single line is enough to get, automatically, with no other code
written:
- storage (as a row in `site_setting`, sparse — only overridden values are stored)
- type validation on write (`SettingDef.validate`)
- a generic admin GET/PUT under `/admin/api/settings/{category}`
- automatic inclusion (or correct exclusion, if `secret=True`) in the
  public config API at `/api/config/public`

Later passes (theming, booking hours, chat, notifications) add entries
and categories here — they should almost never need a new route.

## What's genuinely configurable after Pass 1

Branding (site name, tagline, logo, favicon), locale (default + supported
languages), contact info, base theme colors, and three feature toggles.
More arrives every pass — by Pass 10 nothing described in the reference
repo's `admin.html` should still be a hardcoded literal in the codebase.

## Security decisions worth flagging

- **Sessions are server-side, not JWT.** The cookie only carries a signed
  opaque id; the session row in the DB is what actually grants access,
  so revoking a session (logout, an admin disabling an account) takes
  effect immediately — no waiting out a token's expiry.
- **CSRF token required on every mutating admin request**, checked with a
  constant-time comparison, on top of `SameSite=Lax` cookies.
- **Secrets (API keys, SMTP passwords, etc. in later passes) are
  encrypted at rest** with Fernet, keyed by `ENCRYPTION_KEY` — a DB dump
  alone doesn't leak them — and are structurally excluded from the
  public config API rather than filtered by convention.
- **Login is rate-limited** (5/minute/IP by default) and the failure path
  is constant-shape (same status/body for "wrong password" and "unknown
  username", checked against a dummy hash either way) to resist
  enumeration and timing attacks.
- **Bulk settings updates are all-or-nothing**: every key in a `PUT` is
  validated before any of them are written, so a bad field can't leave
  the rest half-applied.
- Every setting write is appended to `audit_log` (actor, IP, old→new key)
  — Pass 9 builds the UI for it, but the trail starts now so there's
  nothing to backfill.

## Running it

```bash
cd backend
pip install -r requirements-dev.txt
cp .env.example .env
python scripts/gen_secrets.py --password 'your-admin-password'   # paste output into .env
python scripts/init_db.py
uvicorn app.main:app --reload --port 8001

pytest -q                       # 16 tests
python tests/test_rate_limit.py # real 5/minute login limit, isolated process
```

## Deliberately deferred to later passes

- Nothing frontend-facing changed yet (Pass 2 wires the React app to
  `/api/config/public` and removes hardcoded content).
- Image upload for logo/favicon (Pass 3).
- Multiple admin users / role management UI, full audit log viewer (Pass 9).
- MySQL/Postgres migration tooling — SQLAlchemy already supports both via
  `DATABASE_URL`, this pass just hasn't needed a real migration yet.
