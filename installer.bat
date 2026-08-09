@echo off
REM ============================================================
REM  Perennia v2 - one-shot installer for Windows.
REM
REM  Sets up the FastAPI backend (venv, deps, .env, secrets, DB,
REM  seed data) and builds both frontends (public site + admin
REM  dashboard) as static production bundles. The backend serves
REM  everything itself - public site at /, admin dashboard at
REM  /admin, API at /api and /admin/api - so the whole app runs
REM  behind a single port with no separate dev servers needed.
REM  Safe to re-run: every step it performs is idempotent.
REM
REM      installer.bat
REM ============================================================

setlocal enabledelayedexpansion
set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "ADMIN_DIR=%ROOT_DIR%\admin"

echo ==^> Checking prerequisites

where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [ERROR] Python 3 is required but was not found on PATH. Install Python 3.10+ and re-run.
        exit /b 1
    )
    set "PYTHON_BIN=py"
) else (
    set "PYTHON_BIN=python"
)
echo   Found Python: !PYTHON_BIN!

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is required but was not found on PATH. Install Node 16+ and re-run.
    exit /b 1
)
for /f "delims=" %%v in ('node --version') do echo   Found Node %%v

where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] npm is required but was not found on PATH.
    exit /b 1
)
for /f "delims=" %%v in ('npm --version') do echo   Found npm %%v

REM ── Backend: venv + dependencies ─────────────────────────────
echo.
echo ==^> Setting up backend (Python virtual environment)
cd /d "%BACKEND_DIR%"

if not exist "venv\" (
    !PYTHON_BIN! -m venv venv
    echo   Created virtual environment at backend\venv
) else (
    echo   Virtual environment already exists
)

call venv\Scripts\activate.bat

python -m pip install --quiet --upgrade pip
pip install --quiet -r requirements-dev.txt
echo   Backend Python dependencies installed

REM ── Backend: .env + secrets ──────────────────────────────────
echo.
echo ==^> Configuring backend environment

if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo   Created backend\.env from .env.example
) else (
    echo   backend\.env already exists - leaving it untouched
)

set "NEEDS_SECRETS=0"
findstr /r /c:"^SECRET_KEY=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"
findstr /r /c:"^ENCRYPTION_KEY=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"
findstr /r /c:"^BOOTSTRAP_ADMIN_PASSWORD_HASH=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"

if "!NEEDS_SECRETS!"=="1" (
    echo.
    echo No admin secrets found yet in backend\.env - let's generate them.

    set "ADMIN_USERNAME="
    set /p ADMIN_USERNAME="Bootstrap admin username [admin]: "
    if "!ADMIN_USERNAME!"=="" set "ADMIN_USERNAME=admin"

    set "ADMIN_PASSWORD="
    :askpassword
    echo NOTE: this Command Prompt does not hide typed characters.
    set /p ADMIN_PASSWORD="Bootstrap admin password (min 12 chars recommended): "
    if "!ADMIN_PASSWORD!"=="" (
        echo Password cannot be empty.
        goto askpassword
    )

    python scripts\gen_secrets.py --username "!ADMIN_USERNAME!" --password "!ADMIN_PASSWORD!" > "%TEMP%\perennia_secrets.txt"

    for /f "usebackq tokens=1,* delims==" %%A in ("%TEMP%\perennia_secrets.txt") do (
        if "%%A"=="SECRET_KEY" set "SECRET_KEY_VAL=%%B"
        if "%%A"=="ENCRYPTION_KEY" set "ENCRYPTION_KEY_VAL=%%B"
        if "%%A"=="BOOTSTRAP_ADMIN_USERNAME" set "BOOTSTRAP_USERNAME_VAL=%%B"
        if "%%A"=="BOOTSTRAP_ADMIN_PASSWORD_HASH" set "BOOTSTRAP_HASH_VAL=%%B"
    )
    del "%TEMP%\perennia_secrets.txt"

    powershell -NoProfile -Command ^
        "$path = '.env';" ^
        "$content = Get-Content -Path $path;" ^
        "function Set-EnvVar($content, $key, $value) {" ^
        "  $pattern = '^' + [regex]::Escape($key) + '=';" ^
        "  if ($content -match $pattern) {" ^
        "    return $content -replace ($pattern + '.*'), ($key + '=' + $value)" ^
        "  } else {" ^
        "    return $content + ($key + '=' + $value)" ^
        "  }" ^
        "}" ^
        "$content = Set-EnvVar $content 'SECRET_KEY' '!SECRET_KEY_VAL!';" ^
        "$content = Set-EnvVar $content 'ENCRYPTION_KEY' '!ENCRYPTION_KEY_VAL!';" ^
        "$content = Set-EnvVar $content 'BOOTSTRAP_ADMIN_USERNAME' '!BOOTSTRAP_USERNAME_VAL!';" ^
        "$content = Set-EnvVar $content 'BOOTSTRAP_ADMIN_PASSWORD_HASH' '!BOOTSTRAP_HASH_VAL!';" ^
        "Set-Content -Path $path -Value $content"

    set "ADMIN_PASSWORD="
    echo   Secrets generated and written to backend\.env
) else (
    echo   Admin secrets already present in backend\.env - skipping generation
)

REM ── Backend: database init + content seed ────────────────────
echo.
echo ==^> Initializing database
python scripts\init_db.py
if %errorlevel% neq 0 exit /b 1
echo   Database ready

echo.
echo ==^> Seeding initial content
python scripts\seed_content.py
if %errorlevel% neq 0 exit /b 1
echo   Content seeded

call venv\Scripts\deactivate.bat
cd /d "%ROOT_DIR%"

REM ── Frontend: public site (production build) ───────────────────
echo.
echo ==^> Building public site (npm install + build)
call npm install
if %errorlevel% neq 0 exit /b 1
call npm run build
if %errorlevel% neq 0 exit /b 1
echo   Public site built to dist\

REM ── Frontend: admin dashboard (production build) ────────────────
echo.
echo ==^> Building admin dashboard (npm install + build)
cd /d "%ADMIN_DIR%"
call npm install
if %errorlevel% neq 0 exit /b 1
call npm run build
if %errorlevel% neq 0 exit /b 1
cd /d "%ROOT_DIR%"
echo   Admin dashboard built to admin\dist\

REM ── Done ────────────────────────────────────────────────────
echo.
echo Perennia v2 is set up.
echo.
echo Everything runs behind a single port now - start the backend and
echo it serves the public site, the admin dashboard, and the API:
echo.
echo   cd backend ^&^& venv\Scripts\activate.bat ^&^& uvicorn app.main:app --port 8001
echo.
echo   Public site        http://localhost:8001/
echo   Admin dashboard    http://localhost:8001/admin
echo   API                http://localhost:8001/api/... and /admin/api/...
echo.
echo Run the backend test suite with:  cd backend ^&^& venv\Scripts\activate.bat ^&^& pytest -q
echo.
echo Rebuilding after frontend changes: re-run this script, or just
echo   npm run build              (public site)
echo   cd admin ^&^& npm run build  (admin dashboard)
echo.
echo Prefer hot-reload dev servers instead? They still work, on
echo separate ports, and proxy API calls to the backend:
echo   npm run dev              (http://localhost:5173)
echo   cd admin ^&^& npm run dev  (http://localhost:5174)
echo.

endlocal
