<#
.SYNOPSIS
  Run the app locally as it is today: FastAPI backend + React frontend, no database setup.

.DESCRIPTION
  Changes NO system-level software. It only creates the project's own dependency folders
  if they are missing (backend\.venv via uv, frontend\node_modules via pnpm), both inside
  this project folder, from the committed lockfiles.

  Then it opens two PowerShell windows (backend on :8000, frontend on :5173), checks that
  both answer, checks that the frontend reaches the backend through its /api proxy, writes
  .setup-reports\run-local.json, opens the project in VS Code and the app in your browser.

  Known limits of this run (shown honestly in the app):
    * No PostgreSQL yet and no .env -> database checks report "not configured".
    * qwen3:4b is not pulled yet -> model runtime reports "model not pulled".
    * Node.js 22.20.0 is below the project's minimum 22.22.0 (React Router 8). For this run
      only, pnpm's engine check is relaxed with a command-line flag; no file is changed.
      React Router runs inside the browser bundle, so the Node version does not affect it
      at runtime; Vite 8 itself supports Node 22.12+.

  Stop the app by closing the two windows (or Ctrl+C in each).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\run-local.ps1
#>
[CmdletBinding()]
param([switch]$NoBrowser, [switch]$NoVSCode)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); project_root = $root; steps = [ordered]@{}; endpoints = @() }

function Stop-WithReport([string]$Message) {
    Write-Fail $Message
    $report.result = "failed: $Message"
    Save-Report 'run-local' $report
    exit 1
}

function Start-Window([string]$Command, [string]$Directory) {
    # -EncodedCommand avoids Windows PowerShell 5.1 argument-quoting problems with spaces.
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($Command))
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $Directory -PassThru `
        -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded)
}

Write-Step 'Tool versions (read only)'
$report.versions = [ordered]@{
    uv = Get-NativeOutput 'uv' @('--version')
    node = Get-NativeOutput 'node' @('--version')
    pnpm = Get-NativeOutput 'pnpm' @('--version')
}
foreach ($k in $report.versions.Keys) { Write-Info ("{0,-5} {1}" -f $k, $report.versions[$k]) }
if (-not $report.versions.uv) { Stop-WithReport 'uv not found on PATH.' }
if (-not $report.versions.node -or -not $report.versions.pnpm) { Stop-WithReport 'node or pnpm not found on PATH.' }

foreach ($port in 8000, 5173) {
    if (Test-TcpPort '127.0.0.1' $port) { Stop-WithReport "Port $port is already in use. Close whatever is using it (maybe an earlier run) and try again." }
}

Write-Step 'Backend environment (backend\.venv, project-local)'
if (Test-Path (Join-Path $backend '.venv\Scripts\python.exe')) {
    Write-Ok 'backend\.venv exists.'
} else {
    Write-Info 'Creating backend\.venv from uv.lock (uses the uv-managed Python 3.12 already on this PC) ...'
    $code = Invoke-Native 'uv' @('sync', '--frozen', '--no-python-downloads') -WorkingDirectory $backend
    if ($code -ne 0) { Stop-WithReport "uv sync failed (exit $code). Messages above show why." }
    Write-Ok 'backend\.venv created.'
}
$report.steps.python = Get-NativeOutput (Join-Path $backend '.venv\Scripts\python.exe') @('--version')
Write-Info "Python in venv: $($report.steps.python)"

Write-Step 'Frontend dependencies (frontend\node_modules, project-local)'
if (Test-Path (Join-Path $frontend 'node_modules\vite\bin\vite.js')) {
    Write-Ok 'frontend\node_modules exists.'
} else {
    Write-Info 'Installing from pnpm-lock.yaml (engine check relaxed for this run only) ...'
    $code = Invoke-Native 'pnpm' @('install', '--frozen-lockfile', '--config.engine-strict=false') -WorkingDirectory $frontend
    if ($code -ne 0) { Stop-WithReport "pnpm install failed (exit $code). Messages above show why." }
    Write-Ok 'frontend\node_modules installed.'
}

Write-Step 'Starting the backend (new window, port 8000)'
# Dev endpoints on for this run; no .env and no database yet, so DB checks say "not configured".
$apiCommand = @"
`$host.UI.RawUI.WindowTitle = 'Copilot API :8000'
Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
`$env:APP_ENV = 'development'
`$env:ENABLE_DEV_ENDPOINTS = 'true'
`$env:PYTHONUTF8 = '1'
uv run --no-sync uvicorn copilot.main:create_app --factory --host 127.0.0.1 --port 8000
"@
$api = Start-Window $apiCommand $backend
$report.steps.backend_pid = $api.Id

Write-Step 'Starting the frontend (new window, port 5173)'
$webCommand = @"
`$host.UI.RawUI.WindowTitle = 'Copilot Web :5173'
node ./node_modules/vite/bin/vite.js
"@
$web = Start-Window $webCommand $frontend
$report.steps.frontend_pid = $web.Id

Write-Step 'Waiting for both servers'
$apiUp = $false; $webUp = $false
foreach ($i in 1..60) {
    if (-not $apiUp) { $apiUp = Test-TcpPort '127.0.0.1' 8000 }
    if (-not $webUp) { $webUp = Test-TcpPort '127.0.0.1' 5173 }
    if ($apiUp -and $webUp) { break }
    Start-Sleep -Seconds 1
}
$report.steps.backend_listening = $apiUp
$report.steps.frontend_listening = $webUp
if ($apiUp) { Write-Ok 'Backend listening on 127.0.0.1:8000' } else { Write-Fail 'Backend did not start within 60 s - look at the "Copilot API :8000" window.' }
if ($webUp) { Write-Ok 'Frontend listening on 127.0.0.1:5173' } else { Write-Fail 'Frontend did not start within 60 s - look at the "Copilot Web :5173" window.' }

Write-Step 'Endpoint checks (direct to backend, and through the frontend proxy)'
$targets = @(
    'http://127.0.0.1:8000/api/v1/health/live',
    'http://127.0.0.1:8000/api/v1/health',
    'http://127.0.0.1:8000/api/v1/health/database',
    'http://127.0.0.1:8000/api/v1/health/model-runtime',
    'http://127.0.0.1:8000/api/v1/dev/sources/adapters',
    'http://127.0.0.1:5173/api/v1/health',
    'http://127.0.0.1:5173/'
)
foreach ($url in $targets) {
    $status = 0; $body = $null
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
        $status = [int]$r.StatusCode; $body = $r.Content
    } catch {
        # Non-2xx responses: WebException (PowerShell 5.1) or HttpResponseException (7.x).
        $resp = $_.Exception.Response
        if ($resp) {
            $status = [int]$resp.StatusCode
            $body = if ($_.ErrorDetails) { $_.ErrorDetails.Message } else { '' }
        } else {
            $body = $_.Exception.Message
        }
    }
    $summary = if ($body -and $body.TrimStart().StartsWith('{')) { $body } elseif ($body) { $body.Substring(0, [Math]::Min(120, $body.Length)) } else { '' }
    $report.endpoints += [ordered]@{ url = $url; status = $status; body = $summary }
    $line = "{0}  {1}" -f $status, $url
    if ($status -ge 200 -and $status -lt 300) { Write-Ok $line } elseif ($status -eq 503) { Write-Warn "$line  (dependency not ready - expected today)" } else { Write-Fail $line }
}

$report.result = if ($apiUp -and $webUp) { 'running' } else { 'partial' }
Save-Report 'run-local' $report

if (-not $NoVSCode -and (Test-CommandExists 'code')) {
    Write-Step 'Opening the project in VS Code'
    Start-Process -FilePath 'code' -ArgumentList @("`"$root`"") -WindowStyle Hidden
}
if (-not $NoBrowser -and $webUp) {
    Write-Step 'Opening http://127.0.0.1:5173 in your browser'
    Start-Process 'http://127.0.0.1:5173/'
}

Write-Host ''
Write-Ok 'App running. Backend docs: http://127.0.0.1:8000/api/v1/docs'
Write-Info 'Stop it by closing the "Copilot API :8000" and "Copilot Web :5173" windows.'
