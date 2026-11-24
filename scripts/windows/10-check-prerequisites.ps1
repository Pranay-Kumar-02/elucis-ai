<#
.SYNOPSIS
  Step 1 - check (and, with your consent, upgrade) the tools this project needs.

.DESCRIPTION
  Required: uv, Python 3.12 (uv-managed), Node.js >= 22.22.0, pnpm, Git, WSL2 with Ubuntu,
  Ollama. Installs nothing silently. The only change it can make is upgrading Node.js
  through winget, and only after you type "y"; Windows then asks for administrator approval.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\10-check-prerequisites.ps1
#>
[CmdletBinding()]
param([switch]$NoPrompt)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$root = Get-ProjectRoot
$results = [ordered]@{ generated_at = (Get-Date).ToString('o'); checks = @() }
$blocking = 0

function Add-Check([string]$Name, [bool]$Ok, [string]$Found, [string]$Need, [string]$Fix = '') {
    $script:results.checks += [ordered]@{ name = $Name; ok = $Ok; found = $Found; required = $Need; fix = $Fix }
    if ($Ok) { Write-Ok "$Name : $Found" } else { Write-Fail "$Name : $Found (need $Need)"; if ($Fix) { Write-Info $Fix } }
    if (-not $Ok) { $script:blocking++ }
}

Write-Step 'Project location'
$inOneDrive = Test-OneDrivePath $root
if ($inOneDrive) {
    Write-Warn "The project is inside OneDrive: $root"
    Write-Info 'OneDrive syncs .venv and node_modules (tens of thousands of files) and can lock'
    Write-Info 'them during installs. Recommended: move the folder to C:\dev\ before step 2.'
} else {
    Write-Ok "Project folder: $root"
}
$results.project_in_onedrive = $inOneDrive

Write-Step 'Python toolchain'
$uv = Get-NativeOutput 'uv' @('--version')
Add-Check 'uv' ([bool]$uv) ($(if ($uv) { $uv } else { 'not found' })) '>= 0.9' 'Install: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
if ($uv) {
    $py = Get-NativeOutput 'uv' @('python', 'find', '--managed-python', '3.12')
    if (-not $py -or $py -match 'error') {
        Write-Info 'Installing a uv-managed CPython 3.12 (per-user, no admin) ...'
        [void](Invoke-Native 'uv' @('python', 'install', '3.12'))
        $py = Get-NativeOutput 'uv' @('python', 'find', '--managed-python', '3.12')
    }
    $pyVersion = if ($py -and (Test-Path $py)) { Get-NativeOutput $py @('--version') } else { $null }
    Add-Check 'Python 3.12 (uv-managed)' ([bool]$pyVersion) ($(if ($pyVersion) { $pyVersion } else { 'not found' })) '3.12.x'
}

Write-Step 'Node.js toolchain'
$nodeRaw = Get-NativeOutput 'node' @('--version')
$nodeOk = $false
if ($nodeRaw -match '^v(\d+)\.(\d+)\.(\d+)') {
    $nodeVersion = [version]"$($Matches[1]).$($Matches[2]).$($Matches[3])"
    $nodeOk = $nodeVersion -ge [version]'22.22.0'
}
if (-not $nodeOk) {
    Write-Warn "Node.js $nodeRaw is older than 22.22.0 (React Router 8 requires it; newer"
    Write-Info 'releases also carry security fixes). Upgrade to the current Node.js LTS with:'
    Write-Info '  winget install --id OpenJS.NodeJS.LTS --exact --source winget'
    if (-not $NoPrompt -and (Test-CommandExists 'winget')) {
        $answer = Read-Host '  Upgrade Node.js now with winget? Windows will ask for admin approval [y/N]'
        if ($answer -match '^(y|yes)$') {
            [void](Invoke-Native 'winget' @('install', '--id', 'OpenJS.NodeJS.LTS', '--exact', '--source', 'winget',
                    '--accept-package-agreements', '--accept-source-agreements'))
            $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
            $nodeRaw = Get-NativeOutput 'node' @('--version')
            if ($nodeRaw -match '^v(\d+)\.(\d+)\.(\d+)') {
                $nodeOk = ([version]"$($Matches[1]).$($Matches[2]).$($Matches[3])") -ge [version]'22.22.0'
            }
        }
    }
}
Add-Check 'Node.js' $nodeOk ($(if ($nodeRaw) { $nodeRaw } else { 'not found' })) '>= 22.22.0' 'winget install --id OpenJS.NodeJS.LTS --exact --source winget  (then open a new PowerShell window)'
$pnpm = Get-NativeOutput 'pnpm' @('--version')
Add-Check 'pnpm' ([bool]$pnpm) ($(if ($pnpm) { $pnpm } else { 'not found' })) '12.x (project pins 12.16.1)' 'npm install -g pnpm@12.16.1'

Write-Step 'Other tools'
$git = Get-NativeOutput 'git' @('--version')
Add-Check 'Git' ([bool]$git) ($(if ($git) { $git } else { 'not found' })) 'any recent'
$distro = Get-WslDistro
Add-Check 'WSL2 Ubuntu (for PostgreSQL)' ([bool]$distro) ($(if ($distro) { "distribution '$distro'" } else { 'not found' })) 'Ubuntu on WSL2' 'wsl --install -d Ubuntu  (admin, then reboot)'
$ollama = $null
try { $ollama = (Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/version' -TimeoutSec 5).version } catch { }
Add-Check 'Ollama server' ([bool]$ollama) ($(if ($ollama) { "running, version $ollama" } else { 'not reachable' })) 'running' 'Start the Ollama app from the Start menu'

$os = Get-CimInstance Win32_OperatingSystem
$freeGb = [math]::Round($os.FreePhysicalMemory * 1KB / 1GB, 1)
if ($freeGb -lt 4) {
    Write-Warn "Only $freeGb GB RAM free. Close browsers/IDEs you do not need before model tests."
}
$results.ram_free_gb = $freeGb
$results.blocking_problems = $blocking
Save-Report 'prerequisites' $results

if ($blocking -gt 0) {
    Write-Host ''
    Write-Fail "$blocking prerequisite(s) missing. Fix them, open a NEW PowerShell window and run this again."
    exit 1
}
Write-Host ''
Write-Ok 'All prerequisites present. Next: scripts\windows\20-setup-project.ps1'
