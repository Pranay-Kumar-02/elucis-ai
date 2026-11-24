<#
.SYNOPSIS
  Read-only network diagnostics for package downloads (PyPI, npm, GitHub, Ollama registry).

.DESCRIPTION
  Changes nothing. For each host the project downloads from, it records:
    * DNS resolution through Windows' configured DNS servers,
    * DNS resolution asking public resolvers directly (Cloudflare 1.1.1.1, Google 8.8.8.8),
    * a TCP connection to port 443 and an HTTPS request.
  It also records which network adapters are up and which DNS servers they use, proxy
  settings (names and on/off only), and any hosts-file lines that mention these hosts.
  Output: .setup-reports\network-diagnostics.json

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\diag-network.ps1
#>
[CmdletBinding()]
param()

Import-Module (Join-Path $PSScriptRoot 'lib\Common.psm1') -Force
$hosts = @(
    'files.pythonhosted.org',   # Python wheels (uv sync)
    'pypi.org',                 # Python index
    'registry.npmjs.org',       # npm packages (pnpm install)
    'github.com',               # uv-managed Python builds, tools
    'registry.ollama.ai'        # model downloads (ollama pull)
)
$report = [ordered]@{ generated_at = (Get-Date).ToString('o'); hosts = @() }

function Resolve-Name([string]$Name, [string]$Server) {
    $started = Get-Date
    try {
        if (Get-Command Resolve-DnsName -ErrorAction SilentlyContinue) {
            $params = @{ Name = $Name; DnsOnly = $true; QuickTimeout = $true; ErrorAction = 'Stop' }
            if ($Server) { $params.Server = $Server }
            $answers = Resolve-DnsName @params | Where-Object { $_.Type -in 'A', 'AAAA' } | ForEach-Object { $_.IPAddress }
        } elseif (-not $Server) {
            $answers = [System.Net.Dns]::GetHostAddresses($Name) | ForEach-Object { $_.IPAddressToString }
        } else {
            return [ordered]@{ ok = $null; error = 'Resolve-DnsName not available' }
        }
        $list = @($answers | Select-Object -Unique)
        return [ordered]@{ ok = ($list.Count -gt 0); addresses = $list; ms = [int]((Get-Date) - $started).TotalMilliseconds }
    } catch {
        return [ordered]@{ ok = $false; error = $_.Exception.Message; ms = [int]((Get-Date) - $started).TotalMilliseconds }
    }
}

Write-Step 'Network adapters and DNS servers'
$adapters = @()
if (Get-Command Get-NetAdapter -ErrorAction SilentlyContinue) {
    foreach ($a in Get-NetAdapter | Where-Object Status -eq 'Up') {
        $dns = @(Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue |
                ForEach-Object { $_.ServerAddresses } | Where-Object { $_ })
        $metric = (Get-NetIPInterface -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).InterfaceMetric
        $adapters += [ordered]@{ name = $a.Name; description = $a.InterfaceDescription; ipv4_metric = $metric; dns_servers = $dns }
        Write-Info ("{0,-28} metric {1,-4} DNS: {2}" -f $a.Name, $metric, ($(if ($dns) { $dns -join ', ' } else { '(none)' })))
    }
}
$report.adapters = $adapters
$report.default_route_adapter = $(try {
        (Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop | Sort-Object RouteMetric | Select-Object -First 1).InterfaceAlias
    } catch { $null })

Write-Step 'Proxy settings (on/off only)'
$inet = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings' -ErrorAction SilentlyContinue
$report.proxy = [ordered]@{
    user_proxy_enabled = [bool]($inet -and $inet.PSObject.Properties.Name -contains 'ProxyEnable' -and $inet.ProxyEnable -eq 1)
    pac_script_set = [bool]($inet -and $inet.PSObject.Properties.Name -contains 'AutoConfigURL')
    winhttp = (Get-NativeOutput 'netsh' @('winhttp', 'show', 'proxy')) -replace '\s+', ' '
    env_http_proxy_set = [bool](Test-Path Env:HTTP_PROXY)
    env_https_proxy_set = [bool](Test-Path Env:HTTPS_PROXY)
}
Write-Info "User proxy enabled: $($report.proxy.user_proxy_enabled); PAC script: $($report.proxy.pac_script_set)"

Write-Step 'Hosts file'
$hostsFile = if ($env:SystemRoot) { Join-Path $env:SystemRoot 'System32\drivers\etc\hosts' } else { '/etc/hosts' }
$report.hosts_file_matches = @()
if (Test-Path $hostsFile) {
    $report.hosts_file_matches = @(Get-Content $hostsFile | Where-Object { $_ -notmatch '^\s*#' -and $_ -match 'pythonhosted|pypi|npmjs|github|ollama' })
}
Write-Info "Matching lines: $($report.hosts_file_matches.Count)"

Write-Step 'Hosts used for downloads'
foreach ($name in $hosts) {
    $entry = [ordered]@{ host = $name }
    $entry.system_dns = Resolve-Name $name $null
    $entry.via_1_1_1_1 = Resolve-Name $name '1.1.1.1'
    $entry.via_8_8_8_8 = Resolve-Name $name '8.8.8.8'
    $ip = $null
    foreach ($r in @($entry.system_dns, $entry.via_1_1_1_1, $entry.via_8_8_8_8)) {
        if ($r.ok) { $ip = $r.addresses | Where-Object { $_ -notmatch ':' } | Select-Object -First 1; if ($ip) { break } }
    }
    $entry.tcp_443 = if ($ip) { Test-TcpPort $ip 443 3000 } else { $null }
    try {
        $resp = Invoke-WebRequest -Uri "https://$name/" -Method Head -UseBasicParsing -TimeoutSec 10 -MaximumRedirection 0 -ErrorAction Stop
        $entry.https = "HTTP $([int]$resp.StatusCode)"
    } catch {
        $entry.https = if ($_.Exception.Response) { "HTTP $([int]$_.Exception.Response.StatusCode)" } else { "error: $($_.Exception.Message)" }
    }
    $report.hosts += $entry
    $sys = if ($entry.system_dns.ok) { 'OK' } else { 'FAIL' }
    $pub = if ($entry.via_1_1_1_1.ok -or $entry.via_8_8_8_8.ok) { 'OK' } else { 'FAIL' }
    $line = "{0,-24} system DNS {1,-4} public DNS {2,-4} tcp443 {3,-5} https {4}" -f $name, $sys, $pub, $entry.tcp_443, $entry.https
    if ($sys -eq 'OK' -and $entry.https -like 'HTTP *') { Write-Ok $line } else { Write-Warn $line }
}

# A one-line conclusion to make the report easy to act on.
$failing = @($report.hosts | Where-Object { -not $_.system_dns.ok })
$names = ($failing | ForEach-Object { $_.host }) -join ', '
$publicFixes = @($failing | Where-Object { $_.via_1_1_1_1.ok -or $_.via_8_8_8_8.ok })
$publicDead = @($failing | Where-Object { $_.via_1_1_1_1.ok -eq $false -and $_.via_8_8_8_8.ok -eq $false })
$report.conclusion = if ($failing.Count -eq 0) {
    'System DNS resolves every host now; the earlier failure was most likely a temporary network or DNS drop. Re-running is safe.'
} elseif ($publicFixes.Count -eq $failing.Count) {
    "Windows' DNS servers fail for: $names, while public resolvers answer. The configured DNS server (router, VPN or a virtual adapter) is the problem."
} elseif ($failing.Count -eq $report.hosts.Count -and $publicDead.Count -eq $failing.Count) {
    'No resolver answers for any host: no working internet connection, or DNS traffic is blocked on this network.'
} else {
    "Resolution fails for: $names. Other hosts work, so these names are blocked or filtered on this network."
}
Write-Host ''
Write-Info $report.conclusion
Save-Report 'network-diagnostics' $report
