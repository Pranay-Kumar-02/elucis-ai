# Shared helpers for the Windows setup scripts. Windows PowerShell 5.1 compatible.
# Rules every script follows: never print a secret, never delete user files, record results
# in .setup-reports\<step>.json, and stop with a clear message when something fails.

Set-StrictMode -Version 2.0

$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$script:ReportDir = Join-Path $script:ProjectRoot '.setup-reports'

function Get-ProjectRoot { $script:ProjectRoot }
function Get-ReportDir {
    if (-not (Test-Path $script:ReportDir)) { New-Item -ItemType Directory -Path $script:ReportDir | Out-Null }
    $script:ReportDir
}

function Write-Step([string]$Text) { Write-Host ''; Write-Host "==> $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "  [OK]   $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "  [WARN] $Text" -ForegroundColor Yellow }
function Write-Fail([string]$Text) { Write-Host "  [FAIL] $Text" -ForegroundColor Red }
function Write-Info([string]$Text) { Write-Host "         $Text" }

function Initialize-Session {
    # PYTHONPATH is set on this machine; it would leak other packages into the project venv.
    if (Test-Path Env:PYTHONPATH) {
        Remove-Item Env:PYTHONPATH
        Write-Info 'PYTHONPATH cleared for this session only (it would leak into the project venv).'
    }
    $env:PYTHONUTF8 = '1'
    $env:UV_NO_PROGRESS = '1'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
}

function Invoke-Native {
    <#
      Runs a native command, streams its output, returns the exit code.
      Windows PowerShell 5.1 turns stderr lines into errors under ErrorActionPreference=Stop,
      so this helper always runs with Continue and judges success by the exit code only.
    #>
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $script:ProjectRoot,
        [switch]$Quiet
    )
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Push-Location $WorkingDirectory
    try {
        if ($Quiet) {
            & $FilePath @ArgumentList 2>&1 | Out-Null
        } else {
            & $FilePath @ArgumentList 2>&1 | ForEach-Object { Write-Host "    $_" }
        }
        return $LASTEXITCODE
    } finally {
        Pop-Location
        $ErrorActionPreference = $previous
    }
}

function Get-NativeOutput {
    param([Parameter(Mandatory)][string]$FilePath, [string[]]$ArgumentList = @())
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $FilePath @ArgumentList 2>&1 | ForEach-Object { "$_" }
        return (($out -join "`n") -replace "`0", '').Trim()
    } catch {
        return $null
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-CommandExists([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function New-Secret([int]$Bytes = 32) {
    # URL-safe random string (no characters that need escaping in a connection URL).
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($buffer) } finally { $rng.Dispose() }
    ([Convert]::ToBase64String($buffer)).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in [System.IO.File]::ReadAllLines($Path)) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $key, $value = $line -split '=', 2
        $value = ($value -replace '\s+#.*$', '').Trim()
        $values[$key.Trim()] = $value
    }
    $values
}

function Write-Utf8NoBom([string]$Path, [string]$Content) {
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Get-UrlPassword([string]$Url) {
    if ($Url -match '^[a-z0-9+]+://[^:/@]+:([^@]+)@') { return $Matches[1] }
    return $null
}

function Save-Report([string]$Name, $Data) {
    $path = Join-Path (Get-ReportDir) "$Name.json"
    Write-Utf8NoBom $path ($Data | ConvertTo-Json -Depth 8)
    Write-Info "Report: .setup-reports\$Name.json"
}

function Get-WslDistro {
    if (-not (Test-CommandExists 'wsl')) { return $null }
    $list = Get-NativeOutput 'wsl' @('--list', '--quiet')
    if (-not $list) { return $null }
    $names = @($list -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    foreach ($preferred in @('Ubuntu', 'Ubuntu-26.04', 'Ubuntu-24.04', 'Ubuntu-22.04')) {
        if ($names -contains $preferred) { return $preferred }
    }
    $ubuntu = $names | Where-Object { $_ -like 'Ubuntu*' } | Select-Object -First 1
    return $ubuntu
}

function Test-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutMs = 1500) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $task = $client.ConnectAsync($HostName, $Port)
        return ($task.Wait($TimeoutMs) -and $client.Connected)
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-OneDrivePath([string]$Path) {
    foreach ($root in @($env:OneDrive, $env:OneDriveConsumer, $env:OneDriveCommercial)) {
        if ($root -and $Path.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { return $true }
    }
    return $false
}

Export-ModuleMember -Function *
