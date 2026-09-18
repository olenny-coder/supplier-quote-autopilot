@echo off
REM ============================================================================
REM  Supplier Quote Autopilot - local development launcher
REM ============================================================================
REM
REM  Usage (from a plain Command Prompt, in this folder):
REM
REM      dev.cmd            start the API + buyer dashboard + supplier form
REM      dev.cmd open       restart nothing, just open the UI in your browser
REM      dev.cmd reset      wipe the database, re-seed the demo, then start
REM      dev.cmd seed       load the demo workspace (buyer, suppliers, RFQ, links)
REM      dev.cmd stop       stop whatever is listening on ports 8000/5173/5174
REM      dev.cmd links      print the test links for an already-running instance
REM
REM  What it starts:
REM      8000  FastAPI + Swagger UI
REM      5173  buyer dashboard   (Vite dev server)
REM      5174  supplier form     (Vite dev server)
REM
REM  When it finishes it OPENS THE BUYER DASHBOARD IN YOUR BROWSER and, if a
REM  supplier has not submitted yet, that supplier's form too. The app is a web UI
REM  at http://localhost:5173 - nothing appears on its own otherwise.
REM
REM  Each service opens in its own window so you can read its log and close it to
REM  stop it. This script itself returns immediately.
REM
REM  Everything runs on SQLite and logs email to the console, so no database, no
REM  mail account and no API key are needed. Nothing leaves this machine.
REM ============================================================================

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%~dp0"
set "API_URL=http://localhost:8000"
set "DASH_URL=http://localhost:5173"
set "FORM_URL=http://localhost:5174"

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=start"

REM ---------------------------------------------------------------------------
REM  stop - kill whatever holds our three ports
REM ---------------------------------------------------------------------------
if /i "%ACTION%"=="stop" goto :stop

REM ---------------------------------------------------------------------------
REM  links - just print the links for a running instance
REM ---------------------------------------------------------------------------
if /i "%ACTION%"=="links" goto :links

REM ---------------------------------------------------------------------------
REM  seed / reset
REM ---------------------------------------------------------------------------
if /i "%ACTION%"=="seed" goto :seed
if /i "%ACTION%"=="reset" goto :reset
if /i "%ACTION%"=="open" goto :open
if /i "%ACTION%"=="start" goto :start

echo.
echo   Unknown option: %ACTION%
echo.
echo   Usage: dev.cmd [start ^| open ^| reset ^| seed ^| stop ^| links]
echo.
exit /b 1


REM ===========================================================================
REM  START
REM ===========================================================================
:start

echo.
echo ============================================================================
echo   Supplier Quote Autopilot - starting local stack
echo ============================================================================
echo.

REM ---- prerequisites --------------------------------------------------------
where uv >nul 2>&1
if errorlevel 1 (
    echo   [X] 'uv' is not on PATH. Install it from https://docs.astral.sh/uv/
    echo       then open a NEW Command Prompt so PATH is picked up.
    goto :fail
)

where node >nul 2>&1
if errorlevel 1 (
    echo   [X] 'node' is not on PATH. Install Node 22 from https://nodejs.org/
    goto :fail
)

REM ---- backend env ----------------------------------------------------------
if not exist "backend\.env" (
    echo   [1/6] Creating backend\.env from backend\.env.dev
    REM .env.dev, not .env.example: the example documents every setting and points
    REM at PostgreSQL. This one is tuned to need nothing installed - SQLite,
    REM console email, no API key.
    copy /y "backend\.env.dev" "backend\.env" >nul
) else (
    echo   [1/6] backend\.env already exists - leaving it alone
)

REM ---- frontend env ---------------------------------------------------------
if not exist "frontend\.env" (
    echo   [2/6] Creating frontend\.env
    > "frontend\.env" echo VITE_API_URL=%API_URL%
) else (
    echo   [2/6] frontend\.env already exists
)

if not exist "public_form\.env" (
    > "public_form\.env" echo VITE_API_URL=%API_URL%
) else (
    echo         public_form\.env already exists
)

REM ---- ports ----------------------------------------------------------------
echo   [3/6] Checking ports
for %%P in (8000 5173 5174) do (
    call :checkport %%P
    if !errorlevel! EQU 1 (
        echo.
        echo   [X] Port %%P is already in use.
        echo       Something is probably still running from a previous session.
        echo       Run:   dev.cmd stop
        echo.
        goto :fail
    )
)

REM ---- python deps ----------------------------------------------------------
echo   [4/6] Syncing Python dependencies
pushd backend
call uv sync --all-groups --quiet
if errorlevel 1 (
    popd
    echo   [X] 'uv sync' failed. Scroll up for the reason.
    goto :fail
)
popd

REM ---- node deps ------------------------------------------------------------
echo   [5/6] Checking Node dependencies
if not exist "frontend\node_modules" (
    echo         installing the buyer dashboard (first run, ~30s)
    pushd frontend
    call npm install --silent
    if errorlevel 1 (
        popd
        echo   [X] 'npm install' failed in frontend\
        goto :fail
    )
    popd
)
if not exist "public_form\node_modules" (
    echo         installing the supplier form (first run, ~20s)
    pushd public_form
    call npm install --silent
    if errorlevel 1 (
        popd
        echo   [X] 'npm install' failed in public_form\
        goto :fail
    )
    popd
)

REM ---- database -------------------------------------------------------------
echo   [6/6] Preparing the database
if not exist "backend\var\dev.db" (
    echo         no database yet - loading the demo workspace
    pushd backend
    REM --run-scheduler drafts the two reminders the demo scenario calls for, so
    REM the dashboard has something waiting under Follow-ups on first load.
    call uv run python -m scripts.seed_demo --run-scheduler
    popd
) else (
    echo         backend\var\dev.db already exists - keeping your data
    echo         (run "dev.cmd reset" to rebuild it from scratch^)
)

REM ---- launch ---------------------------------------------------------------
echo.
echo   Starting services in separate windows...

start "SQA API  :8000"            cmd /k "cd /d "%ROOT%backend"     && uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start "SQA Dashboard :5173"       cmd /k "cd /d "%ROOT%frontend"    && npm run dev"
start "SQA Supplier Form :5174"   cmd /k "cd /d "%ROOT%public_form" && npm run dev"

echo   Started. Close those windows to stop the services, or run: dev.cmd stop
goto :links


REM ===========================================================================
REM  OPEN  - reload the UI in the browser without restarting anything
REM ===========================================================================
:open
pushd backend
call uv run python -m scripts.show_links --timeout 10 --open
popd
exit /b 0


REM ===========================================================================
REM  SEED / RESET
REM ===========================================================================
:seed
echo.
echo   Loading the demo workspace...
pushd backend
call uv run python -m scripts.seed_demo --run-scheduler
popd
echo.
echo   Done. Run "dev.cmd" to start the app, or "dev.cmd links" if it is running.
exit /b 0

:reset
echo.
echo   This deletes backend\var\dev.db and rebuilds the demo data.
set /p CONFIRM="  Type y to continue: "
if /i not "%CONFIRM%"=="y" (
    echo   Cancelled.
    exit /b 0
)
if exist "backend\var\dev.db" del /q "backend\var\dev.db"
pushd backend
call uv run python -m scripts.seed_demo --run-scheduler
popd
echo.
echo   Done. Start the app with: dev.cmd
exit /b 0


REM ===========================================================================
REM  LINKS
REM ===========================================================================
:links
pushd backend
REM Short timeout when invoked as `dev.cmd links`, so asking for links on a
REM stopped instance fails fast. `dev.cmd start` legitimately waits for boot, and
REM opens the browser once it is up.
if /i "%ACTION%"=="links" (
    call uv run python -m scripts.show_links --timeout 8
) else (
    call uv run python -m scripts.show_links --open
)
popd
exit /b 0


REM ===========================================================================
REM  STOP
REM ===========================================================================
:stop
echo.
echo   Stopping anything on ports 8000, 5173 and 5174...

REM Why this delegates to PowerShell instead of looping over `netstat` in cmd:
REM `uvicorn --reload` runs as a supervisor process with a worker child, and the
REM child is what holds the socket. Killing just the listener leaves the
REM supervisor alive, and it immediately respawns a worker that re-binds the port
REM -- so a naive stop looks like it worked and then the port is busy again.
REM This walks one level up (supervisor / npm.cmd wrapper) and terminates the
REM whole tree, then re-checks that the ports actually came free.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8000, 5173, 5174;" ^
  "$killed = 0;" ^
  "foreach ($port in $ports) {" ^
  "  $owners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique);" ^
  "  foreach ($ownerPid in $owners) {" ^
  "    if (-not $ownerPid -or $ownerPid -le 4) { continue };" ^
  "    $parent = (Get-CimInstance Win32_Process -Filter ('ProcessId=' + $ownerPid) -ErrorAction SilentlyContinue).ParentProcessId;" ^
  "    if ($parent -and $parent -gt 4) {" ^
  "      taskkill /F /T /PID $parent 2>&1 | Out-Null;" ^
  "    }" ^
  "    taskkill /F /T /PID $ownerPid 2>&1 | Out-Null;" ^
  "    Write-Host ('        stopped the service on port ' + $port);" ^
  "    $killed++;" ^
  "  }" ^
  "}" ^
  "if ($killed -eq 0) { Write-Host '        nothing was listening.' };" ^
  "Start-Sleep -Milliseconds 700;" ^
  "$still = @();" ^
  "foreach ($port in $ports) { if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) { $still += $port } };" ^
  "if ($still.Count -gt 0) { Write-Host ('        WARNING: still listening on ' + ($still -join ', ') + ' - run dev.cmd stop again') }"

echo.
echo   Done. You can close any SQA service windows that are still open.
echo.
exit /b 0


REM ===========================================================================
REM  HELPERS
REM ===========================================================================
:checkport
REM  Returns errorlevel 1 when something is already listening on %1.
netstat -ano | findstr ":%1 " | findstr LISTENING >nul 2>&1
if errorlevel 1 (exit /b 0) else (exit /b 1)

:fail
echo.
echo   Startup aborted. Nothing was started.
echo.
exit /b 1
