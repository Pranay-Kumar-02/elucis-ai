<#
.SYNOPSIS
  Step 2 - create .env with random secrets, install pinned backend and frontend dependencies.

.DESCRIPTION
  * .env is created from .env.example only if it does not exist. Every CHANGE_ME value gets
    a fresh random secret. Values are never printed. The file is limited to your user account.
  * Backend: uv sync --frozen (exact versions and hashes from backend/uv.lock) into backend\.venv.
  * Frontend: pnpm install --frozen-lockfile (exact versions from frontend/pnpm-lock.yaml).
  * Adds VS Code workspace settings (.vscode\) from scripts\windows\templates if missing.
  * Records installed versions in .setup-reports\versions.json.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\20-setup-project.ps1
#>
[CmdletBinding()]
param()

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); steps = [ordered]@{} }

# ------------------------------------------------------------------ .env
Write-Step 'Environment file (.env)'
$envPath = Join-Path $root '.env'
$examplePath = Join-Path $root '.env.example'

function Resolve-EnvValue([string]$Key, [string]$Value, [hashtable]$Passwords) {
    # Fills CHANGE_ME: database URLs get the password of their role, other secrets a new value.
    switch -Regex ($Key) {
        '^(DATABASE_URL|TEST_DATABASE_API_URL)$' { return $Value.Replace('CHANGE_ME', $Passwords.api) }
        '^(DATABASE_WORKER_URL|TEST_DATABASE_WORKER_URL)$' { return $Value.Replace('CHANGE_ME', $Passwords.worker) }
        '^(DATABASE_MIGRATION_URL|TEST_DATABASE_URL)$' { return $Value.Replace('CHANGE_ME', $Passwords.owner) }
        default { if ($Value -eq 'CHANGE_ME') { return New-Secret 48 } }
    }
    return $Value
}

if (Test-Path $envPath) {
    # Add keys that newer versions of .env.example introduced, reusing the role passwords
    # already in .env so the database roles keep working. Existing lines are never changed.
    $current = Read-DotEnv $envPath
    $passwords = @{
        owner = Get-UrlPassword $current['DATABASE_MIGRATION_URL']
        api = Get-UrlPassword $current['DATABASE_URL']
        worker = Get-UrlPassword $current['DATABASE_WORKER_URL']
    }
    $added = @()
    foreach ($line in [System.IO.File]::ReadAllLines($examplePath)) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $key, $value = $line -split '=', 2
        $key = $key.Trim()
        if ($current.ContainsKey($key)) { continue }
        $value = Resolve-EnvValue $key (($value -replace '\s+#.*$', '').Trim()) $passwords
        if ($value -match 'CHANGE_ME') { Write-Warn "$key needs a value in .env (no matching password found)."; continue }
        [System.IO.File]::AppendAllText($envPath, "$key=$value`n", (New-Object System.Text.UTF8Encoding($false)))
        $added += $key
    }
    if ($added) { Write-Ok ".env already exists; added new keys (values not shown): $($added -join ', ')" }
    else { Write-Ok '.env already exists; left unchanged.' }
    $report.steps.env = if ($added) { "kept existing, added $($added.Count) keys" } else { 'kept existing' }
} else {
    $passwords = @{ owner = New-Secret 24; api = New-Secret 24; worker = New-Secret 24 }
    $lines = foreach ($line in [System.IO.File]::ReadAllLines($examplePath)) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { $line; continue }
        $key, $value = $line -split '=', 2
        $value = Resolve-EnvValue $key (($value -replace '\s+#.*$', '').Trim()) $passwords
        "$key=$value"
    }
    Write-Utf8NoBom $envPath (($lines -join "`n") + "`n")
    # Restrict the file to the current user (removes inherited permissions).
    [void](Invoke-Native 'icacls' @($envPath, '/inheritance:r', '/grant:r', "$($env:USERNAME):(R,W)") -Quiet)
    Write-Ok '.env created with random secrets (not shown). Access limited to your account.'
    $report.steps.env = 'created'
}

# ------------------------------------------------------------------ VS Code settings
$vscode = Join-Path $root '.vscode'
if (-not (Test-Path (Join-Path $vscode 'settings.json'))) {
    New-Item -ItemType Directory -Force -Path $vscode | Out-Null
    Copy-Item (Join-Path $PSScriptRoot 'templates\vscode\*.json') $vscode
    Write-Ok 'VS Code workspace settings and recommended extensions added (.vscode\).'
}

# ------------------------------------------------------------------ backend
Write-Step 'Backend dependencies (uv sync --frozen)'
$code = Invoke-Native 'uv' @('sync', '--frozen') -WorkingDirectory $backend
if ($code -ne 0) { Write-Fail "uv sync failed (exit $code)"; exit 1 }
Write-Ok 'backend\.venv ready with locked versions.'
$report.steps.backend = 'ok'

# ------------------------------------------------------------------ frontend
Write-Step 'Frontend dependencies (pnpm install --frozen-lockfile)'
$code = Invoke-Native 'pnpm' @('install', '--frozen-lockfile') -WorkingDirectory $frontend
if ($code -ne 0) { Write-Fail "pnpm install failed (exit $code)"; exit 1 }
Write-Ok 'frontend\node_modules ready with locked versions.'
$report.steps.frontend = 'ok'

# ------------------------------------------------------------------ versions
Write-Step 'Recording versions'
$py = Join-Path $backend '.venv\Scripts\python.exe'
$pyPackages = Get-NativeOutput 'uv' @('pip', 'list', '--format', 'json', '--python', $py)
$nodePackages = Get-NativeOutput 'pnpm' @('--dir', $frontend, 'list', '--depth', '0', '--json')
$versions = [ordered]@{
    generated_at = (Get-Date).ToString('o')
    python = Get-NativeOutput $py @('--version')
    uv = Get-NativeOutput 'uv' @('--version')
    node = Get-NativeOutput 'node' @('--version')
    pnpm = Get-NativeOutput 'pnpm' @('--version')
    git = Get-NativeOutput 'git' @('--version')
    python_packages = $(try { $pyPackages | ConvertFrom-Json } catch { $pyPackages })
    node_packages = $(try { ($nodePackages | ConvertFrom-Json) } catch { $nodePackages })
}
Save-Report 'versions' $versions
Save-Report 'project-setup' $report
Write-Host ''
Write-Ok 'Project dependencies installed. Next: scripts\windows\30-setup-database.ps1'
