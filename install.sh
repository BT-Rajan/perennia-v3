#!/usr/bin/env bash
#
# Perennia v2 — one-shot installer for macOS / Linux.
#
# Sets up the FastAPI backend (venv, deps, .env, secrets, DB, seed data)
# and builds both frontends (public site + admin dashboard) as static
# production bundles. The backend serves everything itself — public
# site at /, admin dashboard at /admin, API at /api and /admin/api —
# so the whole app runs behind a single port with no separate dev
# servers needed. Safe to re-run: every step it performs is idempotent.
#
#   ./install.sh
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
ADMIN_DIR="$ROOT_DIR/admin"

BOLD="$(tput bold 2>/dev/null || true)"
GREEN="$(tput setaf 2 2>/dev/null || true)"
YELLOW="$(tput setaf 3 2>/dev/null || true)"
RED="$(tput setaf 1 2>/dev/null || true)"
RESET="$(tput sgr0 2>/dev/null || true)"

info()  { echo "${BOLD}==>${RESET} $*"; }
ok()    { echo "${GREEN}✓${RESET} $*"; }
warn()  { echo "${YELLOW}!${RESET} $*"; }
fail()  { echo "${RED}✗ $*${RESET}" >&2; exit 1; }

# ── 1. Prerequisite checks ──────────────────────────────────────────
info "Checking prerequisites"

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PYTHON_BIN="$candidate"
        break
    fi
done
[ -n "$PYTHON_BIN" ] || fail "Python 3 is required but was not found on PATH. Install Python 3.10+ and re-run."

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
ok "Python $PY_VERSION found ($PYTHON_BIN)"

command -v node >/dev/null 2>&1 || fail "Node.js is required but was not found on PATH. Install Node 16+ and re-run."
ok "Node $(node --version) found"

command -v npm >/dev/null 2>&1 || fail "npm is required but was not found on PATH."
ok "npm $(npm --version) found"

# ── 2. Backend: venv + dependencies ─────────────────────────────────
info "Setting up backend (Python virtual environment)"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    "$PYTHON_BIN" -m venv venv
    ok "Created virtual environment at backend/venv"
else
    ok "Virtual environment already exists"
fi

# shellcheck disable=SC1091
source venv/bin/activate

pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt
ok "Backend Python dependencies installed"

# ── 3. Backend: .env + secrets ──────────────────────────────────────
info "Configuring backend environment"

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Created backend/.env from .env.example"
else
    ok "backend/.env already exists — leaving it untouched"
fi

NEEDS_SECRETS=false
if ! grep -q '^SECRET_KEY=.\+' .env || ! grep -q '^ENCRYPTION_KEY=.\+' .env || ! grep -q '^BOOTSTRAP_ADMIN_PASSWORD_HASH=.\+' .env; then
    NEEDS_SECRETS=true
fi

if [ "$NEEDS_SECRETS" = true ]; then
    echo ""
    echo "No admin secrets found yet in backend/.env — let's generate them."
    ADMIN_USERNAME="admin"
    read -r -p "Bootstrap admin username [admin]: " INPUT_USERNAME
    if [ -n "$INPUT_USERNAME" ]; then
        ADMIN_USERNAME="$INPUT_USERNAME"
    fi

    ADMIN_PASSWORD=""
    while [ -z "$ADMIN_PASSWORD" ]; do
        read -r -s -p "Bootstrap admin password (min 12 chars recommended): " ADMIN_PASSWORD
        echo ""
        if [ -z "$ADMIN_PASSWORD" ]; then
            warn "Password cannot be empty."
        fi
    done

    SECRETS_OUTPUT="$(python scripts/gen_secrets.py --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD")"

    SECRET_KEY_LINE="$(echo "$SECRETS_OUTPUT" | grep '^SECRET_KEY=')"
    ENCRYPTION_KEY_LINE="$(echo "$SECRETS_OUTPUT" | grep '^ENCRYPTION_KEY=')"
    BOOTSTRAP_USERNAME_LINE="$(echo "$SECRETS_OUTPUT" | grep '^BOOTSTRAP_ADMIN_USERNAME=')"
    BOOTSTRAP_HASH_LINE="$(echo "$SECRETS_OUTPUT" | grep '^BOOTSTRAP_ADMIN_PASSWORD_HASH=')"

    # Escape sed-sensitive characters (&, /, \) in replacement values.
    escape_sed() { printf '%s' "$1" | sed -e 's/[&/\]/\\&/g'; }

    update_env_var() {
        local key="$1" line="$2" escaped
        escaped="$(escape_sed "$line")"
        if grep -q "^${key}=" .env; then
            sed -i.bak "s|^${key}=.*|${escaped}|" .env
        else
            echo "$line" >> .env
        fi
    }

    update_env_var "SECRET_KEY" "$SECRET_KEY_LINE"
    update_env_var "ENCRYPTION_KEY" "$ENCRYPTION_KEY_LINE"
    update_env_var "BOOTSTRAP_ADMIN_USERNAME" "$BOOTSTRAP_USERNAME_LINE"
    update_env_var "BOOTSTRAP_ADMIN_PASSWORD_HASH" "$BOOTSTRAP_HASH_LINE"
    rm -f .env.bak

    unset ADMIN_PASSWORD SECRETS_OUTPUT
    ok "Secrets generated and written to backend/.env"
else
    ok "Admin secrets already present in backend/.env — skipping generation"
fi

# ── 4. Backend: database init + content seed ────────────────────────
info "Initializing database"
python scripts/init_db.py
ok "Database ready"

info "Seeding initial content"
python scripts/seed_content.py
ok "Content seeded"

deactivate
cd "$ROOT_DIR"

# ── 5. Frontend: public site (production build) ─────────────────────
info "Building public site (npm install + build)"
npm install
npm run build
ok "Public site built to dist/"

# ── 6. Frontend: admin dashboard (production build) ──────────────────
info "Building admin dashboard (npm install + build)"
cd "$ADMIN_DIR"
npm install
npm run build
cd "$ROOT_DIR"
ok "Admin dashboard built to admin/dist/"

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "${GREEN}${BOLD}Perennia v2 is set up.${RESET}"
echo ""
echo "Everything runs behind a single port now — start the backend and"
echo "it serves the public site, the admin dashboard, and the API:"
echo ""
echo "  ${BOLD}cd backend && source venv/bin/activate && uvicorn app.main:app --port 8001${RESET}"
echo ""
echo "  Public site        http://localhost:8001/"
echo "  Admin dashboard     http://localhost:8001/admin"
echo "  API                 http://localhost:8001/api/... and /admin/api/..."
echo ""
echo "Run the backend test suite with:  cd backend && source venv/bin/activate && pytest -q"
echo ""
echo "${YELLOW}Rebuilding after frontend changes:${RESET} re-run this script, or just"
echo "  npm run build              (public site)"
echo "  cd admin && npm run build  (admin dashboard)"
echo ""
echo "${YELLOW}Prefer hot-reload dev servers instead?${RESET} They still work, on"
echo "separate ports, and proxy API calls to the backend:"
echo "  npm run dev              # http://localhost:5173"
echo "  cd admin && npm run dev  # http://localhost:5174"
echo ""
