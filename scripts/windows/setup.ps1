<#
.SYNOPSIS
  One command for the whole first-time setup: steps 10, 20, 30, 40 and 90 in order.

.DESCRIPTION
  Stops at the first failing step and tells you which one. Each step can also be run on its
  own and is safe to re-run. A transcript is saved in .setup-reports\setup-<time>.log
  (it contains no secrets: the scripts never print them).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\setup.ps1
#>
[CmdletBinding()]
param([switch]$SkipModels)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$log = Join-Path (Get-ReportDir) ("setup-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
Start-Transcript -Path $log | Out-Null
try {
    $steps = @('10-check-prerequisites.ps1', '20-setup-project.ps1', '30-setup-database.ps1')
    if (-not $SkipModels) { $steps += '40-setup-ollama.ps1' }
    $steps += '90-verify.ps1'
    foreach ($step in $steps) {
        & (Join-Path $PSScriptRoot $step)
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Stopped at $step. Fix the problem above and run setup.ps1 again (finished steps are skipped quickly)."
            exit 1
        }
    }
    Write-Host ''
    Write-Ok 'Setup complete. Daily use: dev-db.ps1 start, dev-api.ps1, dev-worker.ps1, dev-web.ps1'
} finally {
    Stop-Transcript | Out-Null
}
