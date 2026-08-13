@echo off
setlocal enabledelayedexpansion
title Perennia v2 Installer

REM ============================================================
REM  Perennia v2 - one-shot installer for Windows.
REM
REM  Fully unattended: no typing required anywhere in this script.
REM  Sets up the FastAPI backend (venv, deps, .env, secrets, DB,
REM  seed data), builds both frontends (public site + admin
REM  dashboard) as static production bundles, then starts the app
REM  and opens it in your browser. The backend serves everything
REM  itself - public site at /, admin dashboard at /admin, API at
REM  /api and /admin/api - so the whole app runs behind one port.
REM
REM  Safe to re-run: every step is idempotent and picks up where
REM  it left off.
REM
REM  This window will stay open the whole time, including if
REM  something goes wrong, so you can read what happened. It will
REM  wait for a keypress before closing either way.
REM
REM      installer.bat
REM ============================================================

set "ROOT_DIR=%~dp0"
set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "ADMIN_DIR=%ROOT_DIR%\admin"
set "VENV_PY=%BACKEND_DIR%\venv\Scripts\python.exe"
set "CREDENTIALS_FILE=%ROOT_DIR%\ADMIN_CREDENTIALS.txt"
set "GENERATED_NEW_CREDS=0"

echo ============================================================
echo   Perennia v2 - Installer
echo ============================================================
echo.
echo This sets up everything automatically - no typing needed.
echo It can take several minutes on the first run, especially the
echo "installing Python packages" and "npm install" steps. If the
echo screen looks idle during those, that's normal - just wait.
echo.

call :check_prereqs
if errorlevel 1 goto :fail

call :setup_backend_venv
if errorlevel 1 goto :fail

call :setup_env_and_secrets
if errorlevel 1 goto :fail

call :init_database
if errorlevel 1 goto :fail

call :build_public_site
if errorlevel 1 goto :fail

call :build_admin_dashboard
if errorlevel 1 goto :fail

goto :success


REM ============================================================
REM  Steps (called in order above). Each returns errorlevel 0 on
REM  success, 1 on failure with an explanatory message already
REM  printed - the caller just checks errorlevel and stops.
REM ============================================================

:check_prereqs
echo ==^> Checking prerequisites
echo.

where python >nul 2>nul
if errorlevel 1 (
    where py >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] Python was not found on PATH.
        echo         Install Python 3.10 or newer from https://python.org/downloads/
        echo         IMPORTANT: on the first installer screen, check the box that says
        echo         "Add python.exe to PATH" - it's unchecked by default.
        exit /b 1
    )
    set "PYTHON_BIN=py"
) else (
    set "PYTHON_BIN=python"
)
for /f "delims=" %%v in ('!PYTHON_BIN! --version 2^>^&1') do echo   Found %%v (!PYTHON_BIN!)

where node >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Node.js was not found on PATH.
    echo         Install the LTS version from https://nodejs.org/ and re-run this installer.
    exit /b 1
)
for /f "delims=" %%v in ('node --version') do echo   Found Node %%v

where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found on PATH. It normally installs together with Node.js -
    echo         try reinstalling Node.js from https://nodejs.org/
    exit /b 1
)
for /f "delims=" %%v in ('npm --version') do echo   Found npm %%v

echo.
exit /b 0


:setup_backend_venv
echo ==^> Setting up backend (Python virtual environment)
echo     This installs several Python packages and can take a few
echo     minutes the first time - you should see package names
echo     scrolling by below. Please wait for it to finish.
echo.
cd /d "%BACKEND_DIR%" || (echo [ERROR] Could not find %BACKEND_DIR% & exit /b 1)

if not exist "venv\" (
    !PYTHON_BIN! -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create the virtual environment.
        echo         Make sure Python's "venv" module is available ^(it ships with
        echo         standard Python installs^) and that you have write access to
        echo         this folder, then re-run this installer.
        exit /b 1
    )
    echo   Created virtual environment at backend\venv
) else (
    echo   Virtual environment already exists
)

if not exist "%VENV_PY%" (
    echo [ERROR] The virtual environment looks incomplete - %VENV_PY% is missing.
    echo         Delete the backend\venv folder and re-run this installer.
    exit /b 1
)

echo.
echo   Upgrading pip...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] Could not upgrade pip - continuing anyway, this usually isn't fatal.
)

echo.
echo   Installing backend dependencies ^(this is the slow step - please wait^)...
"%VENV_PY%" -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo [ERROR] Failed to install backend Python dependencies. Scroll up for the
    echo         actual pip error. Common causes: no internet connection, or an
    echo         outdated pip. Re-run this installer after fixing the issue.
    exit /b 1
)
echo   Backend Python dependencies installed

cd /d "%ROOT_DIR%"
exit /b 0


:setup_env_and_secrets
echo.
echo ==^> Configuring backend environment
cd /d "%BACKEND_DIR%" || exit /b 1

if exist ".env" goto :env_exists
copy /y ".env.example" ".env" >nul
echo   Created backend\.env from .env.example
goto :env_ready
:env_exists
echo   backend\.env already exists - leaving its settings untouched
:env_ready

set "NEEDS_SECRETS=0"
findstr /r /c:"^SECRET_KEY=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"
findstr /r /c:"^ENCRYPTION_KEY=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"
findstr /r /c:"^BOOTSTRAP_ADMIN_PASSWORD_HASH=..*" .env >nul 2>nul || set "NEEDS_SECRETS=1"

if not "!NEEDS_SECRETS!"=="1" (
    echo   Admin login already configured in backend\.env - skipping
    cd /d "%ROOT_DIR%"
    exit /b 0
)

echo   No admin login configured yet - generating one automatically...

REM Generate the random password via a temp .ps1 FILE rather than an
REM inline -Command string - a one-liner packed with parentheses and
REM pipes, embedded inside backticks, embedded inside this batch
REM script, is exactly the kind of thing cmd.exe's parser can misread.
REM Writing it out as plain lines (no pipes, no parens inside an open
REM block) sidesteps that risk entirely.
set "GENPW_SCRIPT=%TEMP%\perennia_genpw_%RANDOM%.ps1"
> "%GENPW_SCRIPT%" echo $chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
>> "%GENPW_SCRIPT%" echo $pw = ''
>> "%GENPW_SCRIPT%" echo for ($i=0; $i -lt 20; $i++) { $pw += $chars[(Get-Random -Maximum $chars.Length)] }
>> "%GENPW_SCRIPT%" echo Write-Output $pw

set "GEN_PASSWORD="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%GENPW_SCRIPT%"`) do set "GEN_PASSWORD=%%P"
del "%GENPW_SCRIPT%" >nul 2>nul

if "!GEN_PASSWORD!"=="" (
    echo [ERROR] Could not generate a random password ^(PowerShell may be unavailable or blocked^).
    echo         You can set one up manually instead: open a Command Prompt in the
    echo         backend folder and run: venv\Scripts\python scripts\gen_secrets.py
    exit /b 1
)

"%VENV_PY%" scripts\gen_secrets.py --username admin --password "!GEN_PASSWORD!" --write-env ".env"
if errorlevel 1 (
    echo [ERROR] Failed to generate secrets. See the error above.
    exit /b 1
)

set "GEN_USERNAME=admin"
set "GENERATED_NEW_CREDS=1"
echo   Admin login generated and saved into backend\.env

cd /d "%ROOT_DIR%"
exit /b 0


:init_database
echo.
echo ==^> Setting up the database
cd /d "%BACKEND_DIR%" || exit /b 1

"%VENV_PY%" scripts\init_db.py
if errorlevel 1 (
    echo [ERROR] Database setup failed. See the error above.
    exit /b 1
)
echo   Database ready

echo.
echo ==^> Seeding initial content ^(sample pages, FAQ, text^)
"%VENV_PY%" scripts\seed_content.py
if errorlevel 1 (
    echo [ERROR] Content seeding failed. See the error above.
    exit /b 1
)
echo   Content seeded

cd /d "%ROOT_DIR%"
exit /b 0


:build_public_site
echo.
echo ==^> Building the public site ^(npm install + build^)
echo     This can take a few minutes the first time - please wait.
cd /d "%ROOT_DIR%" || exit /b 1

call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed for the public site. See the error above.
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo [ERROR] Building the public site failed. See the error above.
    exit /b 1
)
echo   Public site built to dist\
exit /b 0


:build_admin_dashboard
echo.
echo ==^> Building the admin dashboard ^(npm install + build^)
cd /d "%ADMIN_DIR%" || (echo [ERROR] Could not find %ADMIN_DIR% & exit /b 1)

call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed for the admin dashboard. See the error above.
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo [ERROR] Building the admin dashboard failed. See the error above.
    exit /b 1
)
echo   Admin dashboard built to admin\dist\

cd /d "%ROOT_DIR%"
exit /b 0


REM ============================================================
REM  Outcomes
REM ============================================================

:fail
echo.
echo ============================================================
echo   INSTALL DID NOT FINISH
echo ============================================================
echo.
echo Scroll up to see the [ERROR] message explaining what went wrong.
echo.
echo This installer is safe to re-run after fixing the problem - it
echo will skip any steps that already completed successfully.
echo.
echo Most common causes:
echo   - Python not installed, or not added to PATH
echo   - Node.js not installed
echo   - No internet connection during the download steps
echo.
pause
endlocal
exit /b 1


:success
if "!GENERATED_NEW_CREDS!"=="1" (
    (
        echo Perennia v2 - admin login
        echo Generated automatically by installer.bat
        echo.
        echo   URL:      http://localhost:8001/admin
        echo   Username: !GEN_USERNAME!
        echo   Password: !GEN_PASSWORD!
        echo.
        echo Keep this somewhere safe, then feel free to delete this file.
    ) > "%CREDENTIALS_FILE%"
)

echo.
echo ============================================================
echo   Perennia v2 is set up
echo ============================================================
echo.

if "!GENERATED_NEW_CREDS!"=="1" (
    echo   Admin login ^(also saved to ADMIN_CREDENTIALS.txt in this folder^):
    echo.
    echo     URL:      http://localhost:8001/admin
    echo     Username: !GEN_USERNAME!
    echo     Password: !GEN_PASSWORD!
    echo.
) else (
    echo   Using the admin login already configured in backend\.env.
    echo   Forgot the password? Delete backend\.env and re-run this
    echo   installer to generate a fresh one.
    echo.
)

echo   Public site        http://localhost:8001/
echo   Admin dashboard    http://localhost:8001/admin
echo.
echo Starting the server in a new window now...
echo.

start "Perennia Server" cmd /k call "%ROOT_DIR%\start_server.bat"

timeout /t 3 /nobreak >nul
start "" "http://localhost:8001/"

echo A new "Perennia Server" window is now running the app - leave it
echo open while you use the site. Close that window to stop the server.
echo Next time, you can just double-click start_server.bat to run it
echo again without going through this whole installer.
echo.
echo Run the backend test suite any time with:
echo   cd backend ^&^& venv\Scripts\activate.bat ^&^& pytest -q
echo.
echo Rebuilding after making changes: re-run this installer, or just
echo   npm run build              ^(public site^)
echo   cd admin ^&^& npm run build  ^(admin dashboard^)
echo.
pause
endlocal
exit /b 0
