<#
.SYNOPSIS
  Run the FastAPI backend with auto-reload on http://127.0.0.1:8000 (docs: /api/v1/docs).
#>
[CmdletBinding()]
param([int]$Port = 8000)
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$backend = Join-Path (Get-ProjectRoot) 'backend'
Write-Step "API on http://127.0.0.1:$Port  (Ctrl+C to stop)"
exit (Invoke-Native 'uv' @('run', '--frozen', 'uvicorn', 'elucis.main:create_app', '--factory', '--reload',
        '--host', '127.0.0.1', '--port', "$Port") -WorkingDirectory $backend)
