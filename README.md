# Perennia v2

Perennia's site, rebuilt so that everything an admin should be able to
change — content, theming/branding, business hours, chat behavior,
notifications — is configurable at runtime through a Python (FastAPI)
backend, instead of hardcoded in the frontend. A real admin dashboard
UI lets staff manage bookings and leads day to day.

This is a fresh repo (not a fork of the original `perennia-production`)
so the existing stable site is untouched while this is built out.

## Structure

```
backend/    FastAPI backend — see backend/PASS*_NOTES.md for a
            pass-by-pass account of what was built and why
src/        Public React frontend (Vite)
admin/      Admin dashboard — separate React app (Vite)
```

## Status

Built in incremental passes, each with its own notes and a full test
suite:

- **Pass 1** — backend foundation: settings registry, secure admin auth
- **Pass 2** — content system (pages, FAQ) + frontend wired to the backend
- **Pass 3** — theming, branding, image uploads
- **Pass 4** — appointment booking
- **Pass 5** — chat (LLM-backed) & leads CRM
- **Pass 6** — notifications (email/WhatsApp), editable templates
- **Pass 7** — admin dashboard UI (login, overview, appointments, leads)

See `backend/PASS1_NOTES.md` through `PASS7_NOTES.md` for details on
each. Remaining passes (admin settings UI, security hardening,
deployment polish) are tracked but not yet built.

## Running it

```bash
cd backend
pip install -r requirements-dev.txt
cp .env.example .env
python scripts/gen_secrets.py --password 'your-admin-password'   # paste output into .env
python scripts/init_db.py
python scripts/seed_content.py
uvicorn app.main:app --reload --port 8001

# separate terminals
npm install && npm run dev            # public site, :5173
cd admin && npm install && npm run dev  # admin dashboard, :5174
```

`pytest -q` in `backend/` runs the full test suite (107 tests as of Pass 7).
