<#
.SYNOPSIS
  Step 5 - run every automated check and write one summary report.

.DESCRIPTION
  Backend : ruff format --check, ruff check, mypy (strict), pytest (unit + database tests)
  Frontend: tsc (strict), ESLint, Prettier --check, Vitest, production build
  Live    : starts the API for a moment and calls /api/v1/health and /api/v1/health/database
  Results : .setup-reports\verify.json and verify.md (pass/fail counts per check).
  Needs the database running (dev-db.ps1 start) for the database tests and live checks.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\90-verify.ps1
#>
[CmdletBinding()]
param()

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$reports = Get-ReportDir
$checks = New-Object System.Collections.ArrayList

function Add-Result([string]$Name, [int]$Exit, [hashtable]$Extra = @{}) {
    $entry = [ordered]@{ name = $Name; ok = ($Exit -eq 0); exit_code = $Exit }
    foreach ($k in $Extra.Keys) { $entry[$k] = $Extra[$k] }
    [void]$checks.Add($entry)
    if ($Exit -eq 0) { Write-Ok $Name } else { Write-Fail "$Name (exit $Exit)" }
}

function Read-JUnit([string]$Path) {
    if (-not (Test-Path $Path)) { return @{} }
    [xml]$xml = Get-Content $Path -Raw
    $suites = @($xml.SelectNodes('//testsuite'))
    $sum = { param($attr) ($suites | ForEach-Object { [int]($_.GetAttribute($attr) -replace '^$', '0') } | Measure-Object -Sum).Sum }
    $tests = & $sum 'tests'; $failures = & $sum 'failures'; $errors = & $sum 'errors'; $skipped = & $sum 'skipped'
    @{ tests = $tests; passed = $tests - $failures - $errors - $skipped; failed = $failures + $errors; skipped = $skipped }
}

Write-Step 'Backend'
Add-Result 'ruff format --check' (Invoke-Native 'uv' @('run', '--frozen', 'ruff', 'format', '--check', 'src', 'tests', 'migrations') -WorkingDirectory $backend)
Add-Result 'ruff check' (Invoke-Native 'uv' @('run', '--frozen', 'ruff', 'check', 'src', 'tests', 'migrations') -WorkingDirectory $backend)
Add-Result 'mypy --strict' (Invoke-Native 'uv' @('run', '--frozen', 'mypy') -WorkingDirectory $backend)
$junit = Join-Path $reports 'pytest.xml'
$code = Invoke-Native 'uv' @('run', '--frozen', 'pytest', '-q', "--junitxml=$junit", '--cov', '--cov-report=term') -WorkingDirectory $backend
Add-Result 'pytest' $code (Read-JUnit $junit)

Write-Step 'Frontend'
Add-Result 'tsc --strict (typecheck)' (Invoke-Native 'pnpm' @('run', 'typecheck') -WorkingDirectory $frontend)
Add-Result 'eslint' (Invoke-Native 'pnpm' @('run', 'lint') -WorkingDirectory $frontend)
Add-Result 'prettier --check' (Invoke-Native 'pnpm' @('run', 'format:check') -WorkingDirectory $frontend)
$vjunit = Join-Path $reports 'vitest.xml'
$code = Invoke-Native 'pnpm' @('exec', 'vitest', 'run', '--reporter=default', '--reporter=junit', "--outputFile.junit=$vjunit") -WorkingDirectory $frontend
Add-Result 'vitest' $code (Read-JUnit $vjunit)
Add-Result 'vite build (production)' (Invoke-Native 'pnpm' @('run', 'build') -WorkingDirectory $frontend)

Write-Step 'Live API check'
$apiLog = Join-Path $reports 'verify-api.log'
$api = Start-Process -FilePath 'uv' -ArgumentList @('run', '--frozen', 'uvicorn', 'elucis.main:create_app', '--factory', '--port', '8765') `
    -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput $apiLog -RedirectStandardError "$apiLog.err"
try {
    $live = $null
    foreach ($i in 1..30) {
        try { $live = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/api/v1/health/live' -TimeoutSec 2; break } catch { Start-Sleep -Seconds 1 }
    }
    Add-Result 'API starts (GET /api/v1/health/live)' ($(if ($live -and $live.status -eq 'ok') { 0 } else { 1 }))
    foreach ($path in @('/api/v1/health', '/api/v1/health/database', '/api/v1/health/model-runtime')) {
        try {
            $r = Invoke-WebRequest -Uri "http://127.0.0.1:8765$path" -UseBasicParsing -TimeoutSec 10
            $status = $r.StatusCode; $body = $r.Content
        } catch [System.Net.WebException] {
            $status = [int]$_.Exception.Response.StatusCode
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $body = $reader.ReadToEnd()
        }
        Add-Result "GET $path -> $status" ($(if ($status -eq 200) { 0 } else { 1 })) @{ body = ($body | ConvertFrom-Json) }
    }
} finally {
    if ($api -and -not $api.HasExited) {
        # uv starts uvicorn as a child process; stop the whole tree.
        [void](Invoke-Native 'taskkill' @('/PID', "$($api.Id)", '/T', '/F') -Quiet)
    }
}

$passed = @($checks | Where-Object { $_.ok }).Count
$summary = [ordered]@{
    generated_at = (Get-Date).ToString('o'); passed = $passed; failed = $checks.Count - $passed; checks = $checks
}
Save-Report 'verify' $summary

$md = New-Object System.Collections.Generic.List[string]
$md.Add('# Verification summary'); $md.Add(''); $md.Add("Generated: $($summary.generated_at)"); $md.Add('')
$md.Add('| Check | Result | Details |'); $md.Add('|---|---|---|')
foreach ($c in $checks) {
    $details = if ($c.Contains('tests')) { "$($c.passed) passed, $($c.failed) failed, $($c.skipped) skipped of $($c.tests)" } else { '' }
    $md.Add("| $($c.name) | $(if ($c.ok) { 'PASS' } else { 'FAIL' }) | $details |")
}
Write-Utf8NoBom (Join-Path $reports 'verify.md') (($md -join "`n") + "`n")

Write-Host ''
if ($summary.failed -gt 0) { Write-Fail "$($summary.failed) of $($checks.Count) checks failed. See .setup-reports\verify.md"; exit 1 }
Write-Ok "All $($checks.Count) checks passed. Summary: .setup-reports\verify.md"
