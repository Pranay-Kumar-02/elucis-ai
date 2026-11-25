<#
.SYNOPSIS
  Run the background worker (polls the PostgreSQL job queue; idles until the jobs table exists).
#>
[CmdletBinding()]
param()
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
Initialize-Session
$backend = Join-Path (Get-ProjectRoot) 'backend'
Write-Step 'Worker (Ctrl+C to stop after the current job)'
exit (Invoke-Native 'uv' @('run', '--frozen', 'elucis-worker') -WorkingDirectory $backend)
