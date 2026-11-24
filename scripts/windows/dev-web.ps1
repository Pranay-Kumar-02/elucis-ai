<#
.SYNOPSIS
  Run the React dev server on http://127.0.0.1:5173 (proxies /api to the backend on :8000).
#>
[CmdletBinding()]
param()
Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$frontend = Join-Path (Get-ProjectRoot) 'frontend'
Write-Step 'Frontend on http://127.0.0.1:5173  (Ctrl+C to stop)'
exit (Invoke-Native 'pnpm' @('dev') -WorkingDirectory $frontend)
