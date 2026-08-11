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

    # --write-env patches backend/.env directly in Python rather than
    # round-tripping the generated secret through shell text-parsing
    # (sed/grep) — avoids an entire class of quoting bugs if a
    # generated key or the password itself contains a shell-special
    # character.
    python scripts/gen_secrets.py --username "$ADMIN_USERNAME" --password "$ADMIN_PASSWORD" --write-env .env
    unset ADMIN_PASSWORD
    ok "Secrets generated and written to backend/.env"
else
    ok "Admin secrets already present in backend/.env — skipping generation"
fi

# ── 3b. Backend: database connection ────────────────────────────────
info "Configuring database connection"

CURRENT_DB_URL="$(grep -m1 '^DATABASE_URL=' .env | cut -d= -f2-)"
if [ -z "$CURRENT_DB_URL" ] || [[ "$CURRENT_DB_URL" == sqlite:* ]]; then
    echo ""
    echo "Current DATABASE_URL: ${CURRENT_DB_URL:-<unset, defaults to sqlite>}"
    read -r -p "Configure MySQL instead of SQLite? [y/N]: " USE_MYSQL
    if [[ "$USE_MYSQL" =~ ^[Yy]$ ]]; then
        read -r -p "MySQL host [localhost]: " DB_HOST
        DB_HOST="${DB_HOST:-localhost}"
        read -r -p "MySQL port [3306]: " DB_PORT
        DB_PORT="${DB_PORT:-3306}"
        read -r -p "MySQL username: " DB_USER
        read -r -s -p "MySQL password: " DB_PASS
        echo ""
        read -r -p "MySQL database name: " DB_NAME

        # Built by a short-lived Python process, not shell string
        # interpolation: the password is passed through the environment
        # (never appears in a command line or in bash history), and
        # urllib.parse.quote percent-encodes any URL-special character
        # (@, #, :, /, etc.) so the DB_URL can't be silently mis-parsed —
        # the same reasoning gen_secrets.py's _set_env_var uses to avoid
        # shell-quoting bugs with generated secrets.
        DB_HOST="$DB_HOST" DB_PORT="$DB_PORT" DB_USER="$DB_USER" DB_PASS="$DB_PASS" DB_NAME="$DB_NAME" "$PYTHON_BIN" <<'PYEOF'
import os
import re
from pathlib import Path
from urllib.parse import quote

url = "mysql+pymysql://{}:{}@{}:{}/{}".format(
    quote(os.environ["DB_USER"], safe=""),
    quote(os.environ["DB_PASS"], safe=""),
    os.environ["DB_HOST"],
    os.environ["DB_PORT"],
    quote(os.environ["DB_NAME"], safe=""),
)
p = Path(".env")
content = p.read_text()
content = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={url}", content, count=1, flags=re.MULTILINE)
p.write_text(content)
print(f"DATABASE_URL set to mysql+pymysql://{os.environ['DB_USER']}:***@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}")
PYEOF
        unset DB_PASS
        ok "backend/.env updated with MySQL connection"
    else
        ok "Keeping SQLite for local dev"
    fi
else
    ok "DATABASE_URL already configured (${CURRENT_DB_URL%%://*}://...) — leaving untouched"
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

# ── 7. Process manager (pm2) ─────────────────────────────────────────
PM2_ATTACHED=false
if command -v pm2 >/dev/null 2>&1; then
    info "Starting backend under pm2"

    # Regenerated every run so it always reflects the current HOST/PORT
    # in backend/.env — edits made directly to this file won't survive
    # a re-run of install.sh.
    cat > "$ROOT_DIR/ecosystem.config.cjs" <<'JSEOF'
const fs = require("fs");
const path = require("path");

const envPath = path.join(__dirname, "backend", ".env");
let host = "127.0.0.1";
let port = "8001";
if (fs.existsSync(envPath)) {
  const env = fs.readFileSync(envPath, "utf8");
  const hostMatch = env.match(/^HOST=(.*)$/m);
  const portMatch = env.match(/^PORT=(.*)$/m);
  if (hostMatch && hostMatch[1].trim()) host = hostMatch[1].trim();
  if (portMatch && portMatch[1].trim()) port = portMatch[1].trim();
}

module.exports = {
  apps: [
    {
      name: "perennia-backend",
      cwd: path.join(__dirname, "backend"),
      script: path.join(__dirname, "backend", "venv", "bin", "uvicorn"),
      args: `app.main:app --host ${host} --port ${port}`,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
JSEOF

    if pm2 describe perennia-backend >/dev/null 2>&1; then
        pm2 restart perennia-backend --update-env
        ok "pm2: restarted existing 'perennia-backend' process"
    else
        pm2 start "$ROOT_DIR/ecosystem.config.cjs"
        ok "pm2: started 'perennia-backend'"
    fi
    pm2 save
    ok "pm2 process list saved"
    PM2_ATTACHED=true
else
    warn "pm2 not found on PATH — skipping process manager step."
    warn "Install it with: npm install -g pm2, then re-run this script."
fi

# ── Done ─────────────────────────────────────────────────────────────
echo ""
echo "${GREEN}${BOLD}Perennia v2 is set up.${RESET}"
echo ""
if [ "$PM2_ATTACHED" = true ]; then
    echo "The backend is running under pm2 as 'perennia-backend'."
    echo "  ${BOLD}pm2 status${RESET}                 — check it's up"
    echo "  ${BOLD}pm2 logs perennia-backend${RESET}   — tail logs"
    echo "  ${BOLD}pm2 restart perennia-backend${RESET} — restart after config changes"
else
    echo "Everything runs behind a single port — start the backend and it"
    echo "serves the public site, the admin dashboard, and the API:"
    echo ""
    echo "  ${BOLD}cd backend && source venv/bin/activate && uvicorn app.main:app --port 8001${RESET}"
fi
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
