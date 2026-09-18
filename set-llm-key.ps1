<#
.SYNOPSIS
    Set the LLM API key (Groq by default) in backend\.env, then verify it works.

.DESCRIPTION
    Prompts for a key, writes it into backend\.env without touching anything else,
    restarts the local stack, and sends one real request to confirm the key works.

    Three things this handles that a manual edit gets wrong:

      * A UTF-8 BOM. `Set-Content -Encoding UTF8` on Windows PowerShell 5.1 writes
        a byte-order mark, which corrupts the FIRST variable in the file. This
        writes UTF-8 without a BOM.

      * Retired model ids. Providers shut models down on a schedule and a dead id
        fails every request with `model_not_found`, which reads like a bad key. If
        LLM_MODEL is on the known-retired list this fixes it and says so.

      * A `.env` change does nothing until the API restarts, because settings are
        read once at process start and uvicorn's watcher only watches .py files.

.PARAMETER Key
    The API key. Omit to be prompted (input is masked).

.PARAMETER NoRestart
    Write the key but leave the running services alone.

.PARAMETER SkipVerify
    Do not run the probe request afterwards.

.EXAMPLE
    .\set-llm-key.ps1
    Prompt for the key, write it, restart, verify.

.EXAMPLE
    .\set-llm-key.ps1 -Key gsk_abc123 -NoRestart
    Write the key and stop.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\set-llm-key.ps1
    Same as the first, for a machine where scripts are blocked by policy.
#>

[CmdletBinding()]
param(
    [string] $Key,
    [string] $EnvFile,
    [switch] $NoRestart,
    [switch] $SkipVerify
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
#  Where things are
# ---------------------------------------------------------------------------
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if (-not $EnvFile) {
    $EnvFile = Join-Path $RepoRoot 'backend\.env'
}

$DevCmd = Join-Path $RepoRoot 'dev.cmd'

# ---------------------------------------------------------------------------
#  Model ids that providers have already shut down.
#
#  Source: https://console.groq.com/docs/deprecations
#  A retired id returns 404 model_not_found on every request. That looks like a
#  broken key, so it is worth catching here rather than in a support thread.
# ---------------------------------------------------------------------------
$RetiredModels = @{
    'llama-3.3-70b-versatile'                   = 'openai/gpt-oss-120b'
    'llama-3.1-8b-instant'                      = 'openai/gpt-oss-20b'
    'qwen/qwen3-32b'                            = 'openai/gpt-oss-120b'
    'meta-llama/llama-4-scout-17b-16e-instruct' = 'openai/gpt-oss-120b'
}

function Write-Head($text) {
    Write-Host ''
    Write-Host ('=' * 74) -ForegroundColor DarkGray
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ('=' * 74) -ForegroundColor DarkGray
    Write-Host ''
}

function Write-Ok($text)   { Write-Host "  [ok]   $text" -ForegroundColor Green }
function Write-Warn2($text){ Write-Host "  [warn] $text" -ForegroundColor Yellow }
function Write-Err2($text) { Write-Host "  [fail] $text" -ForegroundColor Red }
function Write-Info($text) { Write-Host "         $text" -ForegroundColor Gray }

Write-Head 'Set LLM API key'

# ---------------------------------------------------------------------------
#  Sanity: is this actually the repository?
# ---------------------------------------------------------------------------
if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Err2 "Not found: $EnvFile"
    Write-Info 'Run this from the repository root, or pass -EnvFile <path>.'
    Write-Info 'If the file does not exist yet, run "dev.cmd" once to create it.'
    exit 1
}

Write-Info "env file   $EnvFile"

# ---------------------------------------------------------------------------
#  Collect the key
# ---------------------------------------------------------------------------
if (-not $Key) {
    Write-Host '  Paste your Groq API key and press Enter. It will not be shown.'
    Write-Host '  Get one free at https://console.groq.com  ->  API Keys'
    Write-Host ''

    $secure = Read-Host '  API key' -AsSecureString

    # Convert the masked input back to plain text. The BSTR is freed right after,
    # so the key does not linger in unmanaged memory for the session.
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $Key = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    }
    finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

# Pasting through a terminal often drags in quotes or trailing whitespace.
$Key = ($Key -replace "[\r\n\t]", '').Trim().Trim('"').Trim("'").Trim()

if (-not $Key) {
    Write-Err2 'No key entered. Nothing changed.'
    exit 1
}

$preview = if ($Key.Length -gt 12) {
    $Key.Substring(0, 7) + '...' + $Key.Substring($Key.Length - 4)
} else {
    '(short key)'
}

Write-Host ''
Write-Info "key        $preview  ($($Key.Length) characters)"

if ($Key -notlike 'gsk_*') {
    Write-Warn2 'This does not start with "gsk_", which is what Groq keys look like.'
    Write-Info  'That is fine for OpenRouter (sk-or-...) or Gemini (AIza...), but if you'
    Write-Info  'meant to use Groq, check you copied the whole key.'
}

# ---------------------------------------------------------------------------
#  Read the env file, preserving everything and the original line endings
# ---------------------------------------------------------------------------
$raw = Get-Content -LiteralPath $EnvFile -Raw

if ($null -eq $raw) { $raw = '' }

$hadTrailingNewline = $raw.EndsWith("`n")
$lines = @($raw -split "`r?`n")
if ($hadTrailingNewline -and $lines.Count -gt 0) {
    # The split leaves a trailing empty element for the final newline; drop it and
    # re-add the newline on write so we do not accumulate blank lines on re-runs.
    $lines = $lines[0..($lines.Count - 2)]
}

$keyWritten  = $false
$modelFixed  = $false
$modelBefore = $null

for ($i = 0; $i -lt $lines.Count; $i++) {
    $line = $lines[$i]

    if ($line -match '^\s*LLM_API_KEY\s*=') {
        $lines[$i] = "LLM_API_KEY=$Key"
        $keyWritten = $true
        continue
    }

    if ($line -match '^\s*LLM_MODEL\s*=\s*(.+?)\s*$') {
        $modelBefore = $Matches[1].Trim()

        if ($RetiredModels.ContainsKey($modelBefore)) {
            $replacement = $RetiredModels[$modelBefore]
            $lines[$i] = "LLM_MODEL=$replacement"
            $modelFixed = $true
        }
    }
}

if (-not $keyWritten) {
    $lines += "LLM_API_KEY=$Key"
}

# ---------------------------------------------------------------------------
#  Write it back: UTF-8 with NO byte-order mark.
#
#  PS 5.1's `Set-Content -Encoding UTF8` emits a BOM, and a BOM turns the first
#  variable in the file into "\ufeffDATABASE_URL", which the settings loader then
#  cannot match. Writing bytes explicitly avoids that entirely.
# ---------------------------------------------------------------------------
$text = ($lines -join "`r`n")
if ($hadTrailingNewline -or $text.Length -gt 0) { $text += "`r`n" }

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

# A backup costs nothing and this file is the only place the key lives.
$backup = "$EnvFile.bak"
Copy-Item -LiteralPath $EnvFile -Destination $backup -Force
[System.IO.File]::WriteAllText($EnvFile, $text, $utf8NoBom)

Write-Ok "LLM_API_KEY written to $EnvFile"
Write-Info "backup kept at $backup"

if ($modelFixed) {
    Write-Host ''
    Write-Warn2 "LLM_MODEL was a RETIRED model id: $modelBefore"
    Write-Info  "Changed to: $($RetiredModels[$modelBefore])"
    Write-Info  'A retired id fails every request with "model_not_found", which looks'
    Write-Info  'exactly like a bad key. Current list:'
    Write-Info  'https://console.groq.com/docs/models'
}

# ---------------------------------------------------------------------------
#  Restart, because a .env change is invisible to a running process
# ---------------------------------------------------------------------------
if (-not $NoRestart) {
    if (Test-Path -LiteralPath $DevCmd) {
        Write-Host ''
        Write-Info 'Restarting the API so it picks the key up...'
        Write-Info '(settings are read once at startup, so uvicorn will not reload on a .env change)'

        & cmd.exe /c "`"$DevCmd`" stop" | Out-Null
        Start-Sleep -Seconds 2

        Write-Host ''
        Write-Host '  Starting the stack again. Browser tabs will open.' -ForegroundColor Gray
        Write-Host ''
        & cmd.exe /c "`"$DevCmd`""
    }
    else {
        Write-Warn2 "dev.cmd not found at $DevCmd - restart the API yourself."
    }
}
else {
    Write-Host ''
    Write-Warn2 'Services not restarted (-NoRestart). The key is not live until you do:'
    Write-Info  'dev.cmd stop'
    Write-Info  'dev.cmd'
}

# ---------------------------------------------------------------------------
#  Verify with a real request
# ---------------------------------------------------------------------------
if (-not $SkipVerify -and -not $NoRestart -and (Test-Path -LiteralPath $DevCmd)) {
    Write-Host ''
    & cmd.exe /c "`"$DevCmd`" llm"
}
elseif (-not $SkipVerify) {
    Write-Host ''
    Write-Info 'Verify with:  dev.cmd llm'
}

exit 0
