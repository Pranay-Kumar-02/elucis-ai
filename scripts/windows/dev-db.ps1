<#
.SYNOPSIS
  Start, stop or check the PostgreSQL server that runs inside WSL2.

.DESCRIPTION
  WSL shuts a distribution down shortly after its last Windows-side process exits, even
  when PostgreSQL is running inside it. "start" therefore launches PostgreSQL and keeps one
  hidden "sleep infinity" process attached, so the database stays up until "stop" (or a
  reboot). No global WSL settings are changed.

.EXAMPLE
  .\scripts\windows\dev-db.ps1 start
  .\scripts\windows\dev-db.ps1 status
  .\scripts\windows\dev-db.ps1 stop
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)][ValidateSet('start', 'stop', 'status')][string]$Action = 'status',
    [string]$Distro
)

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
if (-not $Distro) { $Distro = Get-WslDistro }
if (-not $Distro) { Write-Fail 'No Ubuntu distribution found in WSL.'; exit 1 }
$pidFile = Join-Path (Get-ReportDir) 'wsl-keepalive.pid'

function Get-KeepAlive {
    if (-not (Test-Path $pidFile)) { return $null }
    $id = [int](Get-Content $pidFile -Raw)
    Get-Process -Id $id -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq 'wsl' }
}

switch ($Action) {
    'start' {
        if (-not (Get-KeepAlive)) {
            $proc = Start-Process -FilePath 'wsl.exe' -WindowStyle Hidden -PassThru -ArgumentList @(
                '-d', $Distro, '-u', 'root', '--', 'bash', '-c',
                '"service postgresql start >/dev/null 2>&1; exec sleep infinity"')
            Set-Content -Path $pidFile -Value $proc.Id
        }
        foreach ($i in 1..20) {
            if (Test-TcpPort '127.0.0.1' 5432) { Write-Ok "PostgreSQL is up on 127.0.0.1:5432 (WSL '$Distro')."; exit 0 }
            Start-Sleep -Seconds 1
        }
        Write-Fail 'PostgreSQL did not become reachable on 127.0.0.1:5432 within 20 s.'
        exit 1
    }
    'stop' {
        [void](Invoke-Native 'wsl.exe' @('-d', $Distro, '-u', 'root', '--', 'service', 'postgresql', 'stop') -Quiet)
        $keep = Get-KeepAlive
        if ($keep) { Stop-Process -Id $keep.Id }
        if (Test-Path $pidFile) { Remove-Item $pidFile }
        Write-Ok 'PostgreSQL stopped.'
    }
    'status' {
        $up = Test-TcpPort '127.0.0.1' 5432
        $keep = [bool](Get-KeepAlive)
        if ($up) { Write-Ok "PostgreSQL reachable on 127.0.0.1:5432 (keep-alive running: $keep)." }
        else { Write-Warn "PostgreSQL not reachable on 127.0.0.1:5432 (keep-alive running: $keep)." }
    }
}
