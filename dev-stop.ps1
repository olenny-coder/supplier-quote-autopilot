<#
.SYNOPSIS
    Stop the local Supplier Quote Autopilot stack.

.DESCRIPTION
    Called by `dev.cmd stop`. Terminates everything belonging to this project and
    then verifies the ports actually came free.

    Two things make this harder than "kill the PID on the port":

    1. **A supervisor respawns the worker.** `uvicorn --reload` runs a supervisor
       process with a worker child, and the child is what holds the socket. Kill
       only the child and the supervisor immediately starts another one that
       re-binds the port — a stop that looks successful and leaves the port busy.

    2. **Windows outlive the services inside them.** Each service runs as
       `cmd /k npm run dev`, so when npm dies the `cmd /k` window stays open at a
       prompt. Repeated start/stop cycles accumulate orphaned trees that hold no
       port but clutter the desktop and make the next start's port check confusing.

    So: kill the port owners and their parents (which covers the supervisor), then
    sweep anything else whose command line points at this repository, then confirm
    the ports are free and say so.
#>

[CmdletBinding()]
param(
    [int[]] $Ports = @(8000, 5173, 5174),
    [string] $RepoRoot
)

$ErrorActionPreference = 'SilentlyContinue'

if (-not $RepoRoot) {
    $RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
}

# Resolve to a full path so the command-line match below is reliable. Windows
# process command lines contain the resolved path, not the 8.3 short name.
try {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
} catch {
    $RepoRoot = $RepoRoot.TrimEnd('\')
}

Write-Host ''
Write-Host '  Stopping the Supplier Quote Autopilot stack...'
Write-Host ''

$killed = 0

# ---------------------------------------------------------------------------
#  1. The port owners, and their parents.
# ---------------------------------------------------------------------------
foreach ($port in $Ports) {
    $owners = @(
        Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )

    foreach ($ownerPid in $owners) {
        if (-not $ownerPid -or $ownerPid -le 4) { continue }

        # The parent is the supervisor (uvicorn --reload) or the npm.cmd wrapper.
        # /T kills the whole tree, which is what stops the respawn.
        $parent = (Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue).ParentProcessId

        if ($parent -and $parent -gt 4) {
            & taskkill.exe /F /T /PID $parent 2>&1 | Out-Null
        }

        & taskkill.exe /F /T /PID $ownerPid 2>&1 | Out-Null

        Write-Host "        stopped the service on port $port" -ForegroundColor Gray
        $killed++
    }
}

Start-Sleep -Milliseconds 800

# ---------------------------------------------------------------------------
#  2. Anything else rooted in this repository.
# ---------------------------------------------------------------------------
$strays = @(
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -in @('node.exe', 'python.exe', 'cmd.exe', 'python3.exe') -and
        $_.CommandLine -and
        $_.CommandLine -like "*$RepoRoot*"
    }
)

foreach ($stray in $strays) {
    Stop-Process -Id $stray.ProcessId -Force -ErrorAction SilentlyContinue
    $killed++
}

if ($strays.Count -gt 0) {
    Write-Host "        cleared $($strays.Count) leftover process(es) from earlier runs" -ForegroundColor Gray
}

if ($killed -eq 0) {
    Write-Host '        nothing was running.' -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
#  3. Verify, rather than assume.
# ---------------------------------------------------------------------------
Start-Sleep -Milliseconds 900

$still = @()

foreach ($port in $Ports) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        $still += $port
    }
}

Write-Host ''

if ($still.Count -gt 0) {
    Write-Host "  WARNING: still listening on $($still -join ', ')." -ForegroundColor Yellow
    Write-Host '  Run "dev.cmd stop" again. If it persists, a process outside this' -ForegroundColor Yellow
    Write-Host '  repository holds the port - check with:' -ForegroundColor Yellow
    Write-Host "    netstat -ano | findstr `":$($still[0]) `"" -ForegroundColor Gray
} else {
    Write-Host '  Stopped. Ports 8000, 5173 and 5174 are free.' -ForegroundColor Green
}

Write-Host ''

exit 0
