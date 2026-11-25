<#
.SYNOPSIS
  Step 3 - PostgreSQL 18.7 + pgvector 0.8.7 in WSL2 Ubuntu, roles, databases, migrations.

.DESCRIPTION
  Why WSL2: pgvector has no official Windows installer (a native build needs Visual Studio
  Build Tools); Docker Desktop is not installed and would cost several GB of RAM. Ubuntu on
  WSL2 is already on this machine, and the official PostgreSQL apt repository (PGDG) ships
  exactly postgresql-18 18.7 and postgresql-18-pgvector 0.8.7. No Windows admin rights are
  needed: commands run as root inside WSL (wsl -u root), which does not ask for a password.

  Steps: install/configure (database\wsl\install-postgres.sh) -> keep WSL running in the
  background (dev-db.ps1 start) -> check Windows can reach 127.0.0.1:5432 -> alembic upgrade
  head -> elucis-db-check (vector column, HNSW index, cosine query, full-text search).
  Passwords come from .env and are piped to WSL on stdin, never shown or put on a command line.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\30-setup-database.ps1
#>
[CmdletBinding()]
param([string]$Distro)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$backend = Join-Path $root 'backend'
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); approach = 'WSL2 Ubuntu + PGDG packages' }

Write-Step 'Reading database credentials from .env'
$envValues = Read-DotEnv (Join-Path $root '.env')
$owner = Get-UrlPassword $envValues['DATABASE_MIGRATION_URL']
$api = Get-UrlPassword $envValues['DATABASE_URL']
$worker = Get-UrlPassword $envValues['DATABASE_WORKER_URL']
if (-not ($owner -and $api -and $worker) -or ($owner, $api, $worker) -contains 'CHANGE_ME') {
    Write-Fail '.env is missing or still has CHANGE_ME passwords. Run 20-setup-project.ps1 first.'
    exit 1
}
Write-Ok 'Credentials found (not shown).'

Write-Step 'WSL distribution'
if (-not $Distro) { $Distro = Get-WslDistro }
if (-not $Distro) { Write-Fail 'No Ubuntu distribution found in WSL. Install with: wsl --install -d Ubuntu'; exit 1 }
Write-Ok "Using '$Distro'"
$report.distro = $Distro

Write-Step 'Installing PostgreSQL 18.7 + pgvector 0.8.7 (first run downloads ~60 MB)'
$reportRel = '.setup-reports/postgres-wsl.json'
[void](Get-ReportDir)
$secrets = "$owner`n$api`n$worker`n"
$previous = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$secrets | & wsl.exe -d $Distro -u root --cd $root -- bash database/wsl/install-postgres.sh $reportRel 2>&1 |
    ForEach-Object { Write-Host "    $_" }
$code = $LASTEXITCODE
$ErrorActionPreference = $previous
Remove-Variable secrets
if ($code -ne 0) { Write-Fail "PostgreSQL installation failed (exit $code). See the messages above."; exit 1 }
$wslReport = Join-Path $root '.setup-reports\postgres-wsl.json'
if (Test-Path $wslReport) { $report.wsl = Get-Content $wslReport -Raw | ConvertFrom-Json }
Write-Ok 'PostgreSQL configured inside WSL.'

Write-Step 'Starting the database in the background'
& (Join-Path $PSScriptRoot 'dev-db.ps1') start -Distro $Distro
$reachable = $false
foreach ($i in 1..20) {
    if (Test-TcpPort '127.0.0.1' 5432) { $reachable = $true; break }
    Start-Sleep -Seconds 1
}
$report.windows_can_reach_5432 = $reachable
if (-not $reachable) {
    Write-Fail 'Windows cannot reach 127.0.0.1:5432. Check WSL localhost forwarding (wsl --status).'
    Save-Report 'database-setup' $report
    exit 1
}
Write-Ok 'Windows reaches PostgreSQL on 127.0.0.1:5432.'

Write-Step 'Applying migrations (alembic upgrade head, role app_owner)'
$code = Invoke-Native 'uv' @('run', '--frozen', 'alembic', 'upgrade', 'head') -WorkingDirectory $backend
$report.alembic_upgrade_exit = $code
if ($code -ne 0) { Write-Fail 'alembic upgrade failed.'; Save-Report 'database-setup' $report; exit 1 }
$current = Get-NativeOutput 'uv' @('run', '--frozen', '--directory', $backend, 'alembic', 'current')
$report.alembic_current = $current
Write-Ok "Migration state: $current"

Write-Step 'Verifying connection, pgvector and vector search (elucis-db-check)'
$code = Invoke-Native 'uv' @('run', '--frozen', 'elucis-db-check', '--role', 'api') -WorkingDirectory $backend
$report.db_check_exit = $code
Save-Report 'database-setup' $report
if ($code -ne 0) { Write-Fail 'Database check failed. See .setup-reports\db-check.json'; exit 1 }
Write-Host ''
Write-Ok 'Database ready. Next: scripts\windows\40-setup-ollama.ps1'
