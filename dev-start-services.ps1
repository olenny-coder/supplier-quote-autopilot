<#
.SYNOPSIS
    Launch the three local services, each in its own console window.

.DESCRIPTION
    Called by `dev.cmd start`. Returns immediately.

    Why this is a PowerShell script rather than three `start` lines in dev.cmd:

    cmd's `start` creates the child with the *parent's* stdout handle inherited. If
    dev.cmd is run with its output redirected or piped — `dev.cmd > log.txt`, or
    anything reading dev.cmd's stream — the long-lived service windows keep that
    handle open, the stream never reaches EOF, and the command appears to hang
    forever even though the services started fine.

    `Start-Process` creates each child as an independent process with its own
    console, so nothing of the caller's is inherited and dev.cmd always returns.
    The console title is set with the `title` builtin, which is also what makes the
    windows easy to recognise on the taskbar.
#>

[CmdletBinding()]
param(
    [string] $RepoRoot
)

$ErrorActionPreference = 'Stop'

if (-not $RepoRoot) {
    $RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
}

try {
    $RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
} catch {
    $RepoRoot = $RepoRoot.TrimEnd('\')
}

# Each service: a console title, its working directory, and the command to run.
$services = @(
    [pscustomobject]@{
        Title = 'SQA API :8000'
        Dir   = 'backend'
        Cmd   = 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload'
    }
    [pscustomobject]@{
        Title = 'SQA Dashboard :5173'
        Dir   = 'frontend'
        Cmd   = 'npm run dev'
    }
    [pscustomobject]@{
        Title = 'SQA Supplier Form :5174'
        Dir   = 'public_form'
        Cmd   = 'npm run dev'
    }
)

foreach ($service in $services) {
    $dir = Join-Path $RepoRoot $service.Dir

    if (-not (Test-Path -LiteralPath $dir)) {
        Write-Host "  [warn] skipping $($service.Title): $dir does not exist" -ForegroundColor Yellow
        continue
    }

    # `title` first so the window is identifiable while the service boots, then
    # change directory, then start the service. cmd's `&` chains regardless of the
    # previous command's success, which is what we want for `title`.
    $command = 'title {0} & cd /d "{1}" && {2}' -f $service.Title, $dir, $service.Cmd

    Start-Process -FilePath 'cmd.exe' `
                  -ArgumentList "/k $command" `
                  -WorkingDirectory $dir `
                  -WindowStyle Normal | Out-Null

    Write-Host "        started $($service.Title)" -ForegroundColor Gray
}

exit 0
