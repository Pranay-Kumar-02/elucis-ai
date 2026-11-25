<#
.SYNOPSIS
  Step 4 - pull and smoke-test the local models, including an Ollama restart test.

.DESCRIPTION
  1. Ollama must be running (the Ollama app).
  2. Pulls the two primary candidates if missing: qwen3:4b and qwen3-embedding:0.6b.
     qwen3:8b is NOT pulled (optional benchmark candidate only).
     -IncludeCandidates also pulls qwen3:4b-instruct for comparison (2.5 GB, see notes).
  3. Runs elucis-ollama-check: connectivity, generation, schema-constrained JSON, embeddings
     with the measured dimension, semantic sanity, GPU offload.
  4. Restarts Ollama and runs the quick check again to prove the models are still available.
  Expected registry digests (ollama.com library, checked 24 Nov 2026):
     qwen3:4b              359d7dd4bcda  (= qwen3:4b-thinking-2507-q4_K_M, 2.5 GB)
     qwen3:4b-instruct     0edcdef34593  (= qwen3:4b-instruct-2507-q4_K_M, 2.5 GB)

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\40-setup-ollama.ps1
#>
[CmdletBinding()]
param([switch]$IncludeCandidates, [switch]$SkipRestartTest)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$backend = Join-Path $root 'backend'
$base = 'http://127.0.0.1:11434'
$expected = @{ 'qwen3:4b' = '359d7dd4bcda'; 'qwen3:4b-instruct' = '0edcdef34593' }
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); models = [ordered]@{} }

function Wait-Ollama([int]$Seconds = 60) {
    foreach ($i in 1..$Seconds) {
        try { return (Invoke-RestMethod -Uri "$base/api/version" -TimeoutSec 3).version } catch { Start-Sleep -Seconds 1 }
    }
    return $null
}

Write-Step 'Ollama server'
$version = Wait-Ollama 5
if (-not $version) { Write-Fail 'Ollama is not running. Start the Ollama app, then run this again.'; exit 1 }
Write-Ok "Ollama $version at $base"
$report.ollama_version = $version
$report.gpu = Get-NativeOutput 'nvidia-smi' @('--query-gpu=name,memory.total,memory.free,driver_version', '--format=csv,noheader')
Write-Info "GPU: $($report.gpu)"

Write-Step 'Models'
$wanted = @('qwen3:4b', 'qwen3-embedding:0.6b')
if ($IncludeCandidates) { $wanted += 'qwen3:4b-instruct' }
foreach ($model in $wanted) {
    $tags = (Invoke-RestMethod -Uri "$base/api/tags" -TimeoutSec 15).models
    $present = $tags | Where-Object { $_.name -eq $model }
    if (-not $present) {
        Write-Info "Pulling $model ..."
        $code = Invoke-Native 'ollama' @('pull', $model)
        if ($code -ne 0) { Write-Fail "ollama pull $model failed (exit $code)"; exit 1 }
        $present = (Invoke-RestMethod -Uri "$base/api/tags" -TimeoutSec 15).models | Where-Object { $_.name -eq $model }
    }
    $digest = $present.digest.Substring(0, 12)
    $entry = [ordered]@{ digest = $digest; size_gb = [math]::Round($present.size / 1e9, 2);
        parameter_size = $present.details.parameter_size; quantization = $present.details.quantization_level }
    if ($expected.ContainsKey($model)) {
        $entry.expected_digest = $expected[$model]
        $entry.digest_matches_library = ($digest -eq $expected[$model])
        if (-not $entry.digest_matches_library) { Write-Warn "$model digest $digest differs from the library digest $($expected[$model]) seen on 24 Nov 2026 (the tag may have been updated)." }
    }
    $report.models[$model] = $entry
    Write-Ok "$model  digest $digest  $($entry.size_gb) GB  $($entry.quantization)"
}

Write-Step 'Smoke test (full)'
$full = Invoke-Native 'uv' @('run', '--frozen', 'elucis-ollama-check') -WorkingDirectory $backend
$report.full_check_exit = $full

if ($IncludeCandidates) {
    Write-Step 'Smoke test for comparison candidate qwen3:4b-instruct'
    $env:OLLAMA_CHAT_MODEL = 'qwen3:4b-instruct'
    $cand = Invoke-Native 'uv' @('run', '--frozen', 'elucis-ollama-check', '--report',
            (Join-Path $root '.setup-reports\ollama-check-qwen3-4b-instruct.json')) -WorkingDirectory $backend
    Remove-Item Env:OLLAMA_CHAT_MODEL
    $report.candidate_check_exit = $cand
}

if (-not $SkipRestartTest) {
    Write-Step 'Restart test: stop Ollama, start it again, re-check models'
    Get-Process -Name 'ollama app', 'ollama' -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 3
    $app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
    if (Test-Path $app) { Start-Process -FilePath $app } else { Start-Process -FilePath 'ollama' -ArgumentList 'serve' -WindowStyle Hidden }
    $after = Wait-Ollama 60
    $report.restart_ok = [bool]$after
    if (-not $after) { Write-Fail 'Ollama did not come back within 60 s.'; Save-Report 'ollama-setup' $report; exit 1 }
    Write-Ok "Ollama back up ($after)."
    $quick = Invoke-Native 'uv' @('run', '--frozen', 'elucis-ollama-check', '--quick') -WorkingDirectory $backend
    $report.after_restart_check_exit = $quick
}

Save-Report 'ollama-setup' $report
$failed = ($full -ne 0) -or ($report.Contains('after_restart_check_exit') -and $report.after_restart_check_exit -ne 0)
if ($failed) { Write-Fail 'Some model checks failed. See .setup-reports\ollama-check*.json'; exit 1 }
Write-Host ''
Write-Ok 'Models ready. Next: scripts\windows\90-verify.ps1'
